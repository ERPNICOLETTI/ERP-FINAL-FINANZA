"""Saneamiento conservador y repetible de la base productiva.

No descarta evidencia: toda fila retirada de una tabla activa se conserva como
JSON en ``core_saneamiento_archivo`` y además se crea un backup SQLite antes de
la primera modificación.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "erp_nicoletti.db"
BACKUP_DIR = ROOT / "backups"
PAYWAY_LEGACY_HASH = "f6e735a1541f7fecce6a91bf45043bfa93da2939da087a5891cba56be2a37f6b"
PAYWAY_LEGACY_PATH = (
    ROOT
    / "modulo_tarjetas/crudos_tarjetas/PAYWAY_CSV/2026/07/"
      "Movimientos_Presentados_en_pesos_Delimitado_por_comas.csv"
).as_posix()


def _connection(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _backup(source: sqlite3.Connection) -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"erp_nicoletti_pre_saneamiento_{stamp}.db"
    with sqlite3.connect(target) as destination:
        source.backup(destination)
    with sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True) as check:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            target.unlink(missing_ok=True)
            raise RuntimeError("El backup no superó PRAGMA integrity_check")
    return target


def _archive(conn: sqlite3.Connection, table: str, where: str, params: tuple, reason: str) -> int:
    rows = conn.execute(f'SELECT * FROM "{table}" WHERE {where}', params).fetchall()
    for row in rows:
        conn.execute(
            """INSERT OR IGNORE INTO core_saneamiento_archivo
               (tabla_origen, fila_id, motivo, payload_json)
               VALUES (?, ?, ?, ?)""",
            (table, row["id"], reason, json.dumps(dict(row), ensure_ascii=False, default=str)),
        )
    return len(rows)


def main() -> None:
    conn = _connection(DB_PATH)
    backup_path = _backup(conn)
    counts: dict[str, int] = {}
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS core_saneamiento_archivo (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   tabla_origen TEXT NOT NULL,
                   fila_id INTEGER NOT NULL,
                   motivo TEXT NOT NULL,
                   payload_json TEXT NOT NULL,
                   archivado_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   UNIQUE(tabla_origen, fila_id)
               )"""
        )

        # El RAW 68 contiene las 500 líneas Galicia y las descripciones de los
        # 498 movimientos productivos. El 66 ya no existe: fue un vínculo roto.
        raw68 = conn.execute(
            "SELECT contenido_raw FROM core_staging_raw WHERE id=68"
        ).fetchone()
        affected = conn.execute(
            "SELECT id, descripcion FROM bancos_movimientos WHERE raw_ingesta_id=66"
        ).fetchall()
        if len(affected) not in (0, 498) or raw68 is None:
            raise RuntimeError("No coincide la precondición del linaje Galicia 66 -> 68")
        if any((row["descripcion"] or "") not in raw68["contenido_raw"] for row in affected):
            raise RuntimeError("Hay movimientos del RAW 66 que no aparecen en el RAW 68")
        counts["linaje_bancario_reparado"] = conn.execute(
            "UPDATE bancos_movimientos SET raw_ingesta_id=68 WHERE raw_ingesta_id=66"
        ).rowcount

        # Retirar sólo el circuito PAYWAY legacy roto. Patagonia 365 permanece;
        # las tablas Payway normalizadas son la autoridad actual.
        legacy_parent_ids = [
            row[0] for row in conn.execute(
                "SELECT id FROM tarjetas_liquidaciones WHERE fuente='PAYWAY'"
            )
        ]
        parent_marks = ",".join("?" for _ in legacy_parent_ids) or "NULL"
        detail_where = (
            "NOT EXISTS (SELECT 1 FROM tarjetas_liquidaciones l "
            "WHERE l.id=tarjetas_liquidaciones_detalles.liquidacion_id)"
        )
        detail_params: tuple = ()
        if legacy_parent_ids:
            detail_where += f" OR liquidacion_id IN ({parent_marks})"
            detail_params = tuple(legacy_parent_ids)
        counts["detalles_legacy_archivados"] = _archive(
            conn, "tarjetas_liquidaciones_detalles", detail_where, detail_params,
            "PAYWAY_LEGACY_HUERFANO_O_DUPLICADO",
        )
        conn.execute(f"DELETE FROM tarjetas_liquidaciones_detalles WHERE {detail_where}", detail_params)
        counts["cabeceras_legacy_archivadas"] = _archive(
            conn, "tarjetas_liquidaciones", "fuente='PAYWAY'", (), "PAYWAY_LEGACY_DUPLICADO",
        )
        conn.execute("DELETE FROM tarjetas_liquidaciones WHERE fuente='PAYWAY'")

        counts["logs_huerfanos_archivados"] = _archive(
            conn,
            "core_staging_logs",
            "NOT EXISTS (SELECT 1 FROM core_staging_raw r WHERE r.id=core_staging_logs.staging_id)",
            (),
            "LOG_SIN_RAW_PADRE",
        )
        conn.execute(
            "DELETE FROM core_staging_logs WHERE NOT EXISTS "
            "(SELECT 1 FROM core_staging_raw r WHERE r.id=core_staging_logs.staging_id)"
        )

        # Completar la migración monetaria y de fechas de los movimientos legacy.
        counts["importes_centavos_completados"] = conn.execute(
            "UPDATE bancos_movimientos SET importe_centavos=round(importe*100) "
            "WHERE importe_centavos IS NULL AND importe IS NOT NULL"
        ).rowcount
        counts["saldos_centavos_completados"] = conn.execute(
            "UPDATE bancos_movimientos SET saldo_centavos=round(saldo*100) "
            "WHERE saldo_centavos IS NULL AND saldo IS NOT NULL"
        ).rowcount
        counts["fechas_bancarias_normalizadas"] = conn.execute(
            """UPDATE bancos_movimientos
               SET fecha=substr(fecha,7,4)||'-'||substr(fecha,4,2)||'-'||substr(fecha,1,2)
               WHERE fecha GLOB '[0-9][0-9]/[0-9][0-9]/[0-9][0-9][0-9][0-9]'"""
        ).rowcount
        counts["rutas_resumenes_normalizadas"] = conn.execute(
            "UPDATE bancos_resumenes_mensuales SET path_archivo=replace(path_archivo, char(92), '/') "
            "WHERE instr(path_archivo, char(92))>0"
        ).rowcount
        if not Path(PAYWAY_LEGACY_PATH).exists():
            raise RuntimeError("No existe el archivo físico Payway legacy validado")
        counts["rutas_payway_legacy_reparadas"] = conn.execute(
            "UPDATE tarjetas_payway SET path_archivo=? WHERE hash_archivo=?",
            (PAYWAY_LEGACY_PATH, PAYWAY_LEGACY_HASH),
        ).rowcount

        # Actualmente no hay hashes RAW repetidos; convertir esa verdad auditada
        # en una garantía de esquema impide futuras duplicaciones físicas.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_core_staging_raw_hash "
            "ON core_staging_raw(hash_sha256)"
        )
        conn.commit()

        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_errors = list(conn.execute("PRAGMA foreign_key_check"))
        if integrity != "ok" or fk_errors:
            raise RuntimeError(f"Verificación final falló: integrity={integrity}, fk={len(fk_errors)}")
        print(json.dumps({"backup": backup_path.as_posix(), **counts, "integrity": integrity,
                          "foreign_key_errors": 0}, ensure_ascii=False, indent=2))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
