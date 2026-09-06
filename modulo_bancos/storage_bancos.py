import sqlite3
import json
import os
import logging
import re
from collections import defaultdict, deque
from datetime import datetime
from modulo_gastos.storage_gastos import init_db_gastos, get_cuentas, save_cuenta, delete_cuenta

# STORAGE BANCOS - v4.0 GOLDEN MASTER 🏦🧱🧠⚖️
# Diseño Híbrido: Columnas Duras + metadata_cruda (JSON) + path_archivo

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _fecha_iso(fecha):
    """Normaliza las dos representaciones históricas usadas por los extractos."""
    value = str(fecha or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Fecha bancaria inválida: {fecha!r}")


def _asegurar_esquema_movimientos(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(bancos_movimientos)")}
    if "numero_linea" not in columns:
        conn.execute("ALTER TABLE bancos_movimientos ADD COLUMN numero_linea INTEGER")
    if "moneda" not in columns:
        conn.execute("ALTER TABLE bancos_movimientos ADD COLUMN moneda TEXT DEFAULT 'ARS'")
    if "gasto_tipo_id" not in columns:
        conn.execute("ALTER TABLE bancos_movimientos ADD COLUMN gasto_tipo_id INTEGER REFERENCES gastos_tipos(id)")
    if "importe_centavos" not in columns:
        conn.execute("ALTER TABLE bancos_movimientos ADD COLUMN importe_centavos INTEGER")
    if "saldo_centavos" not in columns:
        conn.execute("ALTER TABLE bancos_movimientos ADD COLUMN saldo_centavos INTEGER")

    # Este índice confundía movimientos gemelos legítimos con duplicados y,
    # además, no impedía solapamientos entre dos extractos anuales distintos.
    conn.execute("DROP INDEX IF EXISTS idx_bancos_movimientos_unique")
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bancos_movimientos_raw_linea
        ON bancos_movimientos(raw_ingesta_id, numero_linea)
        WHERE raw_ingesta_id IS NOT NULL AND numero_linea IS NOT NULL
    """)


def guardar_extracto_hipotecario(
    *, nombre_archivo, hash_sha256, contenido_raw, movimientos, cuenta,
    moneda, parser_version="v6.3.0", reconstruir=False
):
    """Persiste un extracto Hipotecario sin duplicar períodos solapados.

    El RAW es inmutable. En producción, el extracto más reciente reemplaza sólo
    el intervalo de fechas que cubre para esa cuenta, preservando categorías y
    saldos previamente conocidos cuando el archivo nuevo no informa saldo.
    """
    if not movimientos:
        raise ValueError("El extracto Hipotecario no contiene movimientos")

    prepared = []
    for line_number, mov in enumerate(movimientos, start=1):
        item = dict(mov)
        item["fecha_iso"] = _fecha_iso(item.get("fecha"))
        item["numero_linea"] = line_number
        prepared.append(item)

    fecha_desde = min(item["fecha_iso"] for item in prepared)
    fecha_hasta = max(item["fecha_iso"] for item in prepared)
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _asegurar_esquema_movimientos(conn)

        staging = conn.execute(
            "SELECT id, estado FROM core_staging_raw WHERE hash_sha256 = ?",
            (hash_sha256,),
        ).fetchone()
        if staging:
            staging_id = staging["id"]
            if not reconstruir:
                conn.rollback()
                return False, {"staging_id": staging_id, "motivo": "HASH_EXISTENTE"}
        else:
            cursor = conn.execute("""
                INSERT INTO core_staging_raw (
                    nombre_archivo, hash_sha256, modulo, tipo_fuente,
                    formato_raw, parser_version, contenido_raw, filas_leidas,
                    estado, fecha_ingesta
                ) VALUES (?, ?, 'bancos', 'HIPOTECARIO_EXCEL', 'MARKDOWN', ?, ?, ?, 'PENDIENTE', datetime('now','localtime'))
            """, (nombre_archivo, hash_sha256, parser_version, contenido_raw, len(prepared)))
            staging_id = cursor.lastrowid

        fecha_expr = """CASE
            WHEN fecha GLOB '??/??/????*' THEN substr(fecha,7,4)||'-'||substr(fecha,4,2)||'-'||substr(fecha,1,2)
            ELSE substr(fecha,1,10) END"""
        old_rows = conn.execute(f"""
            SELECT b.fecha, b.descripcion, b.importe, b.saldo, b.categoria, b.gasto_tipo_id, b.raw_ingesta_id,
                   (SELECT tipo FROM categorias_maestras c WHERE c.nombre=b.categoria) AS categoria_tipo
            FROM bancos_movimientos b
            WHERE cuenta = ? AND ({fecha_expr}) BETWEEN ? AND ?
            ORDER BY id
        """, (cuenta, fecha_desde, fecha_hasta)).fetchall()

        memory = defaultdict(deque)
        for row in old_rows:
            key = (_fecha_iso(row["fecha"]), row["descripcion"], round(row["importe"] or 0, 2))
            known_balance = row["saldo"]
            if known_balance == 0 and row["raw_ingesta_id"] == staging_id:
                known_balance = None
            remembered_category = row["categoria"]
            if (row["importe"] or 0) > 0 and row["categoria_tipo"] == "EGRESO":
                remembered_category = None
            elif (row["importe"] or 0) < 0 and row["categoria_tipo"] == "INGRESO":
                remembered_category = None
            memory[key].append({
                "categoria": remembered_category,
                "gasto_tipo_id": row["gasto_tipo_id"],
                "saldo": known_balance,
            })

        conn.execute(f"""
            DELETE FROM bancos_movimientos
            WHERE cuenta = ? AND ({fecha_expr}) BETWEEN ? AND ?
        """, (cuenta, fecha_desde, fecha_hasta))

        category_rules = []
        for row in conn.execute("SELECT nombre, tipo, palabras_clave FROM categorias_maestras"):
            for keyword in (row["palabras_clave"] or "").split(","):
                keyword = keyword.strip().lower()
                if keyword:
                    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", re.IGNORECASE)
                    category_rules.append((pattern, row["nombre"], row["tipo"]))

        for item in prepared:
            key = (item["fecha_iso"], item["descripcion"], round(item.get("importe") or 0, 2))
            remembered = memory[key].popleft() if memory[key] else None
            category = remembered["categoria"] if remembered else None
            if not category or category == "SIN_CATEGORIZAR":
                description = item["descripcion"].lower()
                amount = item.get("importe") or 0
                allowed_types = {"INGRESO", "OTRO"} if amount > 0 else {"EGRESO", "OTRO"}
                category = next((
                    name for pattern, name, category_type in category_rules
                    if category_type in allowed_types and pattern.search(description)
                ), None)
            category = category or item.get("categoria") or "SIN_CATEGORIZAR"
            gasto_tipo_id = remembered["gasto_tipo_id"] if remembered and remembered["categoria"] else None

            saldo = item.get("saldo")
            if saldo is None and remembered and remembered["saldo"] is not None:
                saldo = remembered["saldo"]

            conn.execute("""
                INSERT INTO bancos_movimientos (
                    fecha, cuenta, banco, descripcion, importe, saldo, categoria,
                    gasto_tipo_id, raw_ingesta_id, entidad, numero_linea, moneda
                ) VALUES (?, ?, 'HIPOTECARIO', ?, ?, ?, ?, ?, ?, 'JOA', ?, ?)
            """, (
                item["fecha"], cuenta, item["descripcion"], item.get("importe", 0),
                saldo, category, gasto_tipo_id, staging_id, item["numero_linea"], moneda,
            ))

        conn.execute("""
            UPDATE core_staging_raw
            SET parser_version=?, filas_leidas=?, estado='PROCESADO',
                fecha_procesado=datetime('now','localtime'), mensaje_error=NULL
            WHERE id=?
        """, (parser_version, len(prepared), staging_id))
        conn.commit()
        return True, {
            "staging_id": staging_id,
            "filas": len(prepared),
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "moneda": moneda,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def iniciar_staging_documento(*, nombre_archivo, hash_sha256, modulo,
                              tipo_fuente, formato_raw, parser_version,
                              contenido_raw, reprocesar=False):
    """Crea un RAW inmutable o devuelve su ID existente de forma idempotente."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, estado FROM core_staging_raw WHERE hash_sha256=?",
            (hash_sha256,),
        ).fetchone()
        if row:
            return row["id"], bool(reprocesar)
        cursor = conn.execute("""
            INSERT INTO core_staging_raw (
                nombre_archivo, hash_sha256, modulo, tipo_fuente, formato_raw,
                parser_version, contenido_raw, filas_leidas, estado, fecha_ingesta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'PENDIENTE', datetime('now','localtime'))
        """, (
            nombre_archivo, hash_sha256, modulo, tipo_fuente, formato_raw,
            parser_version, contenido_raw,
        ))
        conn.commit()
        return cursor.lastrowid, True
    finally:
        conn.close()


def guardar_extracto_cuenta_corriente(
    parsed, *, staging_id, parser_version, reconstruir=False
):
    """Persiste cabecera y movimientos de una cuenta corriente conciliada."""
    summary = dict(parsed["resumen"])
    movements = [dict(item) for item in parsed["movimientos"]]
    if not summary.get("conciliado"):
        raise ValueError("El extracto de cuenta corriente no concilia")
    if not movements:
        raise ValueError("El extracto de cuenta corriente no contiene movimientos")

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _asegurar_esquema_movimientos(conn)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bancos_extractos_resumenes (
                id                              INTEGER PRIMARY KEY AUTOINCREMENT,
                banco                           TEXT NOT NULL,
                entidad                         TEXT NOT NULL,
                tipo_cuenta                     TEXT NOT NULL,
                numero_cuenta                   TEXT NOT NULL,
                cbu                             TEXT,
                cuit_titular                    TEXT,
                condicion_iva_impresa           TEXT,
                iva_computable_segun_leyenda    INTEGER,
                documento_clave                 TEXT UNIQUE NOT NULL,
                fecha_desde                     TEXT NOT NULL,
                fecha_hasta                     TEXT NOT NULL,
                saldo_inicial_centavos          INTEGER NOT NULL,
                creditos_centavos               INTEGER NOT NULL,
                debitos_centavos                INTEGER NOT NULL,
                saldo_final_centavos            INTEGER NOT NULL,
                intereses_centavos              INTEGER NOT NULL DEFAULT 0,
                iva_intereses_centavos           INTEGER NOT NULL DEFAULT 0,
                sellos_centavos                 INTEGER NOT NULL DEFAULT 0,
                impuesto_ley_25413_centavos      INTEGER NOT NULL DEFAULT 0,
                promedio_saldos_deudores_centavos INTEGER,
                costo_saldos_deudores_centavos  INTEGER,
                acuerdo_limite_centavos         INTEGER,
                acuerdo_tna_milesimas           INTEGER,
                acuerdo_vencimiento             TEXT,
                diferencia_centavos             INTEGER NOT NULL,
                conciliado                      INTEGER NOT NULL,
                raw_ingesta_id                  INTEGER UNIQUE NOT NULL,
                parser_version                  TEXT NOT NULL,
                created_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        raw = conn.execute("SELECT id FROM core_staging_raw WHERE id=?", (staging_id,)).fetchone()
        if not raw:
            raise ValueError("El extracto no posee una entrada previa en core_staging_raw")
        existing = conn.execute(
            "SELECT * FROM bancos_extractos_resumenes WHERE documento_clave=?",
            (summary["documento_clave"],),
        ).fetchone()
        if existing and existing["raw_ingesta_id"] != staging_id:
            conn.rollback()
            return False, {
                "motivo": "EXTRACTO_EXISTENTE", "resumen_id": existing["id"],
                "raw_canonico_id": existing["raw_ingesta_id"],
            }
        if existing and not reconstruir:
            conn.rollback()
            return False, {
                "motivo": "EXTRACTO_EXISTENTE", "resumen_id": existing["id"],
                "raw_canonico_id": staging_id,
            }

        columns = [
            "banco", "entidad", "tipo_cuenta", "numero_cuenta", "cbu", "cuit_titular",
            "condicion_iva_impresa", "iva_computable_segun_leyenda", "documento_clave",
            "fecha_desde", "fecha_hasta", "saldo_inicial_centavos", "creditos_centavos",
            "debitos_centavos", "saldo_final_centavos", "intereses_centavos",
            "iva_intereses_centavos", "sellos_centavos", "impuesto_ley_25413_centavos",
            "promedio_saldos_deudores_centavos", "costo_saldos_deudores_centavos",
            "acuerdo_limite_centavos", "acuerdo_tna_milesimas", "acuerdo_vencimiento",
            "diferencia_centavos", "conciliado",
        ]
        values = [summary.get(column) for column in columns]
        values[columns.index("iva_computable_segun_leyenda")] = int(
            bool(summary["iva_computable_segun_leyenda"])
        )
        values[columns.index("conciliado")] = int(bool(summary["conciliado"]))
        if existing:
            conn.execute(
                f"UPDATE bancos_extractos_resumenes SET "
                f"{', '.join(f'{column}=?' for column in columns)}, parser_version=?, "
                "updated_at=datetime('now','localtime') WHERE id=?",
                (*values, parser_version, existing["id"]),
            )
            summary_id = existing["id"]
        else:
            cursor = conn.execute(
                f"INSERT INTO bancos_extractos_resumenes "
                f"({', '.join(columns + ['raw_ingesta_id', 'parser_version'])}) "
                f"VALUES ({', '.join('?' for _ in columns + ['raw_ingesta_id', 'parser_version'])})",
                (*values, staging_id, parser_version),
            )
            summary_id = cursor.lastrowid

        old_rows = {
            row["numero_linea"]: row for row in conn.execute(
                "SELECT * FROM bancos_movimientos WHERE raw_ingesta_id=? ORDER BY numero_linea",
                (staging_id,),
            ).fetchall()
        }
        used = set()
        inserted = 0
        updated = 0
        for movement in movements:
            line_number = int(movement["numero_linea"])
            old = old_rows.get(line_number)
            params = (
                summary["banco"], summary["numero_cuenta"], movement["fecha"],
                movement["descripcion"], movement["tipo_movimiento"],
                movement["importe_centavos"] / 100, movement["saldo_centavos"] / 100,
                old["categoria"] if old else "SIN_CATEGORIZAR",
                staging_id, old["gasto_tipo_id"] if old else None, summary["entidad"],
                line_number, "ARS", movement["importe_centavos"], movement["saldo_centavos"],
                json.dumps({
                    "linea_documento": movement.get("linea_documento"),
                    "credito_centavos": movement.get("credito_centavos", 0),
                    "debito_centavos": movement.get("debito_centavos", 0),
                    "resumen_id": summary_id,
                }, ensure_ascii=False, sort_keys=True),
            )
            if old:
                conn.execute('''
                    UPDATE bancos_movimientos SET
                        banco=?, cuenta=?, fecha=?, descripcion=?, tipo_movimiento=?, importe=?,
                        saldo=?, categoria=?, raw_ingesta_id=?, gasto_tipo_id=?, entidad=?,
                        numero_linea=?, moneda=?, importe_centavos=?, saldo_centavos=?, metadata_cruda=?
                    WHERE id=?
                ''', (*params, old["id"]))
                used.add(line_number)
                updated += 1
            else:
                conn.execute('''
                    INSERT INTO bancos_movimientos (
                        banco, cuenta, fecha, descripcion, tipo_movimiento, importe, saldo,
                        categoria, raw_ingesta_id, gasto_tipo_id, entidad, numero_linea,
                        moneda, importe_centavos, saldo_centavos, metadata_cruda
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', params)
                inserted += 1
        stale = set(old_rows) - used
        if stale:
            raise ValueError(
                f"El reproceso dejaría {len(stale)} movimientos previos sin equivalencia"
            )
        conn.execute('''
            UPDATE core_staging_raw SET parser_version=?, filas_leidas=?, estado='PROCESADO',
                fecha_procesado=datetime('now','localtime'), mensaje_error=NULL WHERE id=?
        ''', (parser_version, len(movements), staging_id))
        conn.execute('''
            INSERT INTO core_staging_logs(staging_id, resultado, detalles)
            VALUES (?, 'PROCESADO', ?)
        ''', (staging_id, f"Cuenta corriente conciliada: {len(movements)} movimientos"))
        conn.commit()
        return True, {
            "resumen_id": summary_id, "staging_id": staging_id,
            "movimientos": len(movements), "actualizados": updated,
            "agregados": inserted, "conciliado": True,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_staging_por_hash(hash_sha256):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, estado, parser_version FROM core_staging_raw WHERE hash_sha256=?",
            (hash_sha256,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def finalizar_staging_documento(
    staging_id, filas_leidas, *, error=None, preservar_estado=False
):
    conn = get_db_connection()
    try:
        if error:
            if not preservar_estado:
                conn.execute("""
                    UPDATE core_staging_raw SET estado='ERROR', mensaje_error=? WHERE id=?
                """, (str(error), staging_id))
            resultado = "ERROR"
        else:
            conn.execute("""
                UPDATE core_staging_raw
                SET estado='PROCESADO', filas_leidas=?, fecha_procesado=datetime('now','localtime'), mensaje_error=NULL
                WHERE id=?
            """, (filas_leidas, staging_id))
            resultado = "PROCESADO"
        conn.execute("""
            INSERT INTO core_staging_logs(staging_id, resultado, detalles)
            VALUES (?, ?, ?)
        """, (staging_id, resultado, str(error) if error else f"{filas_leidas} filas"))
        conn.commit()
    finally:
        conn.close()


def marcar_staging_duplicado(staging_id, *, raw_canonico_id, filas_leidas=0):
    """Cierra un RAW físico distinto que representa el mismo documento comercial."""
    conn = get_db_connection()
    try:
        detalle = f"Mismo resumen comercial que RAW #{raw_canonico_id}; sin duplicar producción"
        conn.execute("""
            UPDATE core_staging_raw
            SET estado='DUPLICADO', filas_leidas=?, fecha_procesado=datetime('now','localtime'),
                mensaje_error=NULL
            WHERE id=?
        """, (filas_leidas, staging_id))
        conn.execute("""
            INSERT INTO core_staging_logs(staging_id, resultado, detalles)
            VALUES (?, 'DUPLICADO', ?)
        """, (staging_id, detalle))
        conn.commit()
    finally:
        conn.close()


def init_db_bancos():
    """Crea las tablas del dominio Bancos con diseño híbrido v4.0."""
    init_db_gastos()
    conn = get_db_connection()
    print("[BANCOS] Construyendo tablas Golden Master (Híbrido)...")

    # [CAUTION] Si ya existe, se intentará migrar o recrear. 
    # El usuario ha solicitado una limpieza pre-test.
    # conn.execute('DROP TABLE IF EXISTS bancos_movimientos')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bancos_movimientos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            banco           TEXT,
            cuenta          TEXT,
            fecha           TEXT,
            descripcion     TEXT,
            tipo_movimiento TEXT,
            importe         REAL DEFAULT 0,
            saldo           REAL,
            categoria       TEXT DEFAULT 'SIN_CATEGORIZAR',
            path_archivo    TEXT, -- [NUEVO v4.0]
            hash_archivo    TEXT,
            metadata_cruda  TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            raw_ingesta_id  INTEGER,
            gasto_tipo_id   INTEGER REFERENCES gastos_tipos(id),
            entidad         TEXT DEFAULT 'LDK'
        )
    ''')
    
    # [NUEVO] Tabla para Metadatos de Archivo (Evitar redundancia)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bancos_archivos_metadata (
            hash_archivo TEXT PRIMARY KEY,
            banco TEXT,
            metadata_global TEXT,
            fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    _asegurar_esquema_movimientos(conn)

    conn.commit()
    conn.close()


def save_movimiento_banco(lista_movimientos: list, hash_archivo: str, metadatos_archivo: dict = None):
    """
    Inyecta movimientos bancarios usando el patrón Repositorio.
    Si se proveen metadatos de archivo, se guardan en una tabla separada para no repetir por fila.
    """
    conn = get_db_connection()
    agregados = 0
    last_id = None
    try:
        # --- AUTO-CATEGORIZACIÓN BASADA EN APRENDIZAJE PREVIO ---
        cursor_cat = conn.execute("SELECT nombre, palabras_clave FROM categorias_maestras")
        cat_rules = []
        for row in cursor_cat.fetchall():
            kws = [k.strip().lower() for k in (row['palabras_clave'] or '').split(',') if k.strip()]
            cat_rules.append({
                "nombre": row['nombre'],
                "keywords": kws
            })

        for b in lista_movimientos:
            # Si no tiene categoría o es la de por defecto, clasificamos
            current_cat = b.get('categoria', 'SIN_CATEGORIZAR')
            if current_cat in (None, '', 'SIN_CATEGORIZAR'):
                desc_lower = (b.get('descripcion') or '').strip().lower()
                matched_cat = None
                for rule in cat_rules:
                    for kw in rule['keywords']:
                        if kw in desc_lower:
                            matched_cat = rule['nombre']
                            break
                    if matched_cat:
                        break
                if matched_cat:
                    b['categoria'] = matched_cat
                else:
                    b['categoria'] = 'SIN_CATEGORIZAR'

            columnas_duras = {
                'banco', 'cuenta', 'fecha', 'descripcion',
                'tipo_movimiento', 'importe', 'saldo', 'categoria', 'hash_archivo', 'path_archivo'
            }
            metadata = {k: v for k, v in b.items() if k not in columnas_duras}

            try:
                cursor = conn.execute('''
                    INSERT OR IGNORE INTO bancos_movimientos (
                        banco, cuenta, fecha, descripcion, tipo_movimiento,
                        importe, saldo, categoria, hash_archivo, path_archivo, metadata_cruda
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    b.get('banco'), b.get('cuenta', 'SIN_ASIGNAR'),
                    b.get('fecha'), b.get('descripcion'),
                    b.get('tipo_movimiento', b.get('codigo_movimiento', 'MOV')),
                    b.get('importe', 0), b.get('saldo'),
                    b.get('categoria', 'SIN_CATEGORIZAR'),
                    b.get('hash_archivo', hash_archivo),
                    b.get('path_archivo'),
                    json.dumps(metadata, ensure_ascii=False, default=str)
                ))
                
                if cursor.rowcount > 0:
                    agregados += 1
                    last_id = cursor.lastrowid
                
                # Fallback on IGNORE
                if (cursor.rowcount == 0 or cursor.rowcount is None) and last_id is None:
                    res = conn.execute('''
                        SELECT id FROM bancos_movimientos 
                        WHERE banco = ? AND cuenta = ? AND fecha = ? AND descripcion = ? AND importe = ? AND saldo = ?
                    ''', (b.get('banco'), b.get('cuenta', 'SIN_ASIGNAR'), b.get('fecha'), b.get('descripcion'), b.get('importe', 0), b.get('saldo'))).fetchone()
                    if res: row_id = res['id']
                    
            except Exception as e:
                print(f"Error al guardar movimiento en base de datos: {e}")
                
        # Guardar metadatos del archivo una sola vez
        if metadatos_archivo and agregados > 0:
            conn.execute('''
                INSERT OR IGNORE INTO bancos_archivos_metadata (hash_archivo, banco, metadata_global)
                VALUES (?, ?, ?)
            ''', (
                hash_archivo,
                lista_movimientos[0].get('banco', 'DESCONOCIDO') if lista_movimientos else 'DESCONOCIDO',
                json.dumps(metadatos_archivo, ensure_ascii=False, default=str)
            ))
            
        conn.commit()
        return agregados, last_id
    except Exception as e:
        print(f"Error masivo en inyección bancaria: {e}")
        return 0, None
    finally:
        conn.close()


def update_record_path(record_id, new_path):
    """Actualiza la ruta física del archivo tras el archivado legal v4.0."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE bancos_movimientos SET path_archivo = ? WHERE id = ?", (new_path, record_id))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error actualizando path en bancos_movimientos: {e}")
    finally:
        conn.close()


def registrar_archivo_bancario(hash_archivo, banco, new_path, raw_ingesta_id=None):
    """Relaciona por hash un documento bancario con su crudo físico."""
    safe_path = str(new_path).replace('\\', '/')
    metadata = json.dumps({"path_archivo": safe_path, "raw_ingesta_id": raw_ingesta_id}, ensure_ascii=False)
    conn = get_db_connection()
    try:
        conn.execute('''INSERT INTO bancos_archivos_metadata(hash_archivo,banco,metadata_global)
                        VALUES (?,?,?) ON CONFLICT(hash_archivo) DO UPDATE SET
                        banco=excluded.banco, metadata_global=excluded.metadata_global''',
                     (hash_archivo, banco, metadata))
        conn.commit()
    finally:
        conn.close()


def registrar_archivo_tarjeta(hash_archivo, banco, new_path, raw_ingesta_id=None):
    """Alias compatible para el archivado de resúmenes de tarjeta."""
    registrar_archivo_bancario(hash_archivo, banco, new_path, raw_ingesta_id)


def get_sueldos(anio):
    """Consulta especializada v4.0 para detectar haberes/sueldos."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT fecha, descripcion, importe
            FROM bancos_movimientos
            WHERE (descripcion LIKE ? OR descripcion LIKE ?)
            AND fecha LIKE ?
            ORDER BY fecha DESC
        """, ("%SUELDOS%", "%PINO SUB SA%", f"%{anio}%")).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ==========================================
# REPOSITORIO DE CUENTAS MAESTRAS [NUEVO v1.0] (Importado de modulo_gastos)
# ==========================================
