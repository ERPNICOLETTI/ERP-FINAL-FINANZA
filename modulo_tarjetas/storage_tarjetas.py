import sqlite3
import json
import os
import logging

# STORAGE TARJETAS - v4.0 GOLDEN MASTER 💳🧱🧠⚖️
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


def init_db_tarjetas():
    """Crea las tablas del dominio Tarjetas con diseño híbrido v4.0."""
    conn = get_db_connection()
    print("[TARJETAS] Construyendo tablas Golden Master (Hibrido)...")

    # ── Liquidaciones (Cabecera) ───────────────────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarjetas_liquidaciones (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fuente          TEXT,
            marca           TEXT,
            tipo            TEXT DEFAULT 'MENSUAL', -- DIARIA o MENSUAL
            fecha_liquidacion TEXT,
            periodo         TEXT,
            establecimiento TEXT,
            total_bruto     REAL DEFAULT 0,
            costo_arancel   REAL DEFAULT 0,
            costo_financiero REAL DEFAULT 0,
            iva_21          REAL DEFAULT 0,
            iva_105         REAL DEFAULT 0,
            retenciones     REAL DEFAULT 0,
            total_neto      REAL DEFAULT 0,
            path_archivo    TEXT, -- [NUEVO v4.0]
            hash_archivo    TEXT,
            metadata_cruda  TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Liquidaciones (Detalle línea por línea) ────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarjetas_liquidaciones_detalles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            liquidacion_id  INTEGER,
            fecha           TEXT,
            descripcion     TEXT,
            monto_bruto     REAL DEFAULT 0,
            arancel         REAL DEFAULT 0,
            financiero      REAL DEFAULT 0,
            iva             REAL DEFAULT 0,
            retenciones     REAL DEFAULT 0,
            monto_neto      REAL DEFAULT 0,
            metadata_cruda  TEXT DEFAULT '{}',
            FOREIGN KEY(liquidacion_id) REFERENCES tarjetas_liquidaciones(id)
        )
    ''')

    # ── Payway Records (Cupones / Ventas Individuales) ──────────────
    # Reemplaza permanentemente a 'cupones_tarjetas'
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarjetas_payway (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fuente          TEXT,
            fecha_compra    TEXT,
            fecha_pago      TEXT,
            lote            TEXT,
            cupon           TEXT,
            marca           TEXT,
            monto_bruto     REAL DEFAULT 0,
            matching_tx_id  INTEGER, -- Relación con bancos_movimientos
            path_archivo    TEXT, -- [v4.0]
            hash_archivo    TEXT,
            metadata_cruda  TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fecha_compra, cupon, lote, marca, monto_bruto)
        )
    ''')

    # Payway ELT v1: importes exactos en centavos y linaje hasta el raw.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarjetas_payway_resumenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_ingesta_id INTEGER NOT NULL,
            fecha_emision TEXT NOT NULL,
            periodo TEXT NOT NULL,
            numero_resumen TEXT NOT NULL,
            pagador_codigo TEXT NOT NULL,
            pagador_nombre TEXT,
            establecimiento TEXT NOT NULL,
            marca TEXT NOT NULL,
            bruto_centavos INTEGER NOT NULL,
            descuentos_centavos INTEGER NOT NULL,
            neto_centavos INTEGER NOT NULL,
            path_archivo TEXT NOT NULL,
            hash_archivo TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(establecimiento, pagador_codigo, numero_resumen, fecha_emision),
            FOREIGN KEY(raw_ingesta_id) REFERENCES core_staging_raw(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarjetas_payway_resumen_dias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resumen_id INTEGER NOT NULL,
            raw_ingesta_id INTEGER NOT NULL,
            numero_linea INTEGER NOT NULL,
            fecha_pago TEXT NOT NULL,
            bruto_centavos INTEGER NOT NULL,
            descuentos_centavos INTEGER NOT NULL,
            neto_centavos INTEGER NOT NULL,
            liquidaciones_json TEXT NOT NULL DEFAULT '[]',
            UNIQUE(resumen_id, numero_linea),
            FOREIGN KEY(resumen_id) REFERENCES tarjetas_payway_resumenes(id) ON DELETE CASCADE,
            FOREIGN KEY(raw_ingesta_id) REFERENCES core_staging_raw(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarjetas_payway_resumen_conceptos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resumen_id INTEGER NOT NULL,
            raw_ingesta_id INTEGER NOT NULL,
            numero_linea INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            importe_centavos INTEGER NOT NULL,
            UNIQUE(resumen_id, numero_linea),
            FOREIGN KEY(resumen_id) REFERENCES tarjetas_payway_resumenes(id) ON DELETE CASCADE,
            FOREIGN KEY(raw_ingesta_id) REFERENCES core_staging_raw(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarjetas_payway_movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_ingesta_id INTEGER NOT NULL,
            numero_linea INTEGER NOT NULL,
            fecha_compra TEXT NOT NULL,
            fecha_presentacion TEXT NOT NULL,
            fecha_pago TEXT NOT NULL,
            tipo TEXT,
            lote TEXT NOT NULL,
            cupon TEXT NOT NULL,
            marca TEXT NOT NULL,
            establecimiento TEXT NOT NULL,
            bruto_centavos INTEGER NOT NULL,
            detalle TEXT,
            tarjeta_enmascarada TEXT,
            cuotas INTEGER NOT NULL DEFAULT 0,
            modalidad TEXT,
            autorizacion TEXT,
            operacion_asociada TEXT,
            path_archivo TEXT NOT NULL,
            hash_archivo TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(establecimiento, fecha_compra, lote, cupon, marca, bruto_centavos),
            FOREIGN KEY(raw_ingesta_id) REFERENCES core_staging_raw(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarjetas_patagonia_resumenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_ingesta_id INTEGER NOT NULL,
            periodo TEXT NOT NULL,
            numero_resumen TEXT NOT NULL,
            comercio TEXT NOT NULL,
            comercio_id TEXT,
            cuit TEXT NOT NULL,
            bruto_centavos INTEGER NOT NULL,
            arancel_centavos INTEGER NOT NULL,
            financiero_centavos INTEGER NOT NULL,
            otros_cargos_centavos INTEGER NOT NULL,
            promociones_centavos INTEGER NOT NULL,
            iva_ri_centavos INTEGER NOT NULL,
            retencion_iva_centavos INTEGER NOT NULL,
            retencion_ganancias_centavos INTEGER NOT NULL,
            retencion_iibb_centavos INTEGER NOT NULL,
            neto_centavos INTEGER NOT NULL,
            path_archivo TEXT NOT NULL,
            hash_archivo TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(comercio, numero_resumen, periodo),
            FOREIGN KEY(raw_ingesta_id) REFERENCES core_staging_raw(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarjetas_patagonia_liquidaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resumen_id INTEGER NOT NULL,
            raw_ingesta_id INTEGER NOT NULL,
            numero_linea INTEGER NOT NULL,
            numero_liquidacion TEXT NOT NULL,
            fecha_pago TEXT NOT NULL,
            fecha_presentacion TEXT NOT NULL,
            bruto_centavos INTEGER NOT NULL,
            arancel_centavos INTEGER NOT NULL,
            financiero_centavos INTEGER NOT NULL,
            otras_deducciones_centavos INTEGER NOT NULL,
            deducciones_impositivas_centavos INTEGER NOT NULL,
            neto_centavos INTEGER NOT NULL,
            UNIQUE(resumen_id, numero_liquidacion),
            FOREIGN KEY(resumen_id) REFERENCES tarjetas_patagonia_resumenes(id) ON DELETE CASCADE,
            FOREIGN KEY(raw_ingesta_id) REFERENCES core_staging_raw(id)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_payway_resumen_periodo ON tarjetas_payway_resumenes(periodo, marca, pagador_codigo)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_payway_mov_fecha ON tarjetas_payway_movimientos(fecha_compra, establecimiento)')
    conn.execute('DROP VIEW IF EXISTS vw_payway_conciliacion_diaria')
    conn.execute('''
        CREATE VIEW vw_payway_conciliacion_diaria AS
        WITH movimientos AS (
            SELECT fecha_pago,
                   CASE WHEN upper(marca) LIKE '%VISA%' THEN 'VISA'
                        WHEN upper(marca) LIKE '%MASTER%' THEN 'MASTERCARD'
                        ELSE upper(marca) END AS marca,
                   ltrim(establecimiento, '0') AS establecimiento_normalizado,
                   COUNT(*) AS movimientos,
                   SUM(bruto_centavos) AS cobrado_centavos
            FROM tarjetas_payway_movimientos
            GROUP BY fecha_pago, 2, 3
        ), liquidado AS (
            SELECT d.fecha_pago, r.marca, ltrim(r.establecimiento, '0') AS establecimiento_normalizado,
                   COUNT(DISTINCT r.id) AS resumenes,
                   group_concat(DISTINCT r.pagador_codigo) AS pagadores,
                   SUM(d.bruto_centavos) AS liquidado_bruto_centavos,
                   SUM(d.descuentos_centavos) AS descuentos_centavos,
                   SUM(d.neto_centavos) AS neto_centavos
            FROM tarjetas_payway_resumen_dias d
            JOIN tarjetas_payway_resumenes r ON r.id=d.resumen_id
            GROUP BY d.fecha_pago, r.marca, 3
        ), claves AS (
            SELECT fecha_pago, marca, establecimiento_normalizado FROM movimientos
            UNION
            SELECT fecha_pago, marca, establecimiento_normalizado FROM liquidado
        )
        SELECT c.fecha_pago, c.marca, c.establecimiento_normalizado AS establecimiento,
               COALESCE(m.movimientos, 0) AS movimientos,
               COALESCE(m.cobrado_centavos, 0) AS cobrado_centavos,
               COALESCE(l.resumenes, 0) AS resumenes,
               COALESCE(l.pagadores, '') AS pagadores,
               COALESCE(l.liquidado_bruto_centavos, 0) AS liquidado_bruto_centavos,
               COALESCE(l.descuentos_centavos, 0) AS descuentos_centavos,
               COALESCE(l.neto_centavos, 0) AS neto_centavos,
               COALESCE(l.liquidado_bruto_centavos, 0) - COALESCE(m.cobrado_centavos, 0) AS diferencia_centavos,
               CASE WHEN m.fecha_pago IS NULL THEN 'FALTA_MOVIMIENTOS'
                    WHEN l.fecha_pago IS NULL THEN 'NO_LIQUIDADO'
                    WHEN m.cobrado_centavos = l.liquidado_bruto_centavos THEN 'CONCILIADO'
                    ELSE 'DIFERENCIA' END AS estado
        FROM claves c
        LEFT JOIN movimientos m USING(fecha_pago, marca, establecimiento_normalizado)
        LEFT JOIN liquidado l USING(fecha_pago, marca, establecimiento_normalizado)
    ''')

    conn.commit()
    conn.close()


def _upsert_raw(conn, *, name, digest, source_type, parser_version, raw_content, row_count):
    row = conn.execute("SELECT id FROM core_staging_raw WHERE hash_sha256 = ?", (digest,)).fetchone()
    if row:
        raw_id = row['id']
        conn.execute('''UPDATE core_staging_raw SET tipo_fuente=?, formato_raw=?, parser_version=?,
                        filas_leidas=?, estado='PENDIENTE', mensaje_error=NULL, fecha_procesado=NULL WHERE id=?''',
                     (source_type, source_type, parser_version, row_count, raw_id))
        return raw_id
    cursor = conn.execute('''INSERT INTO core_staging_raw
        (nombre_archivo, hash_sha256, modulo, tipo_fuente, formato_raw, parser_version,
         contenido_raw, filas_leidas, estado)
        VALUES (?, ?, 'tarjetas', ?, ?, ?, ?, ?, 'PENDIENTE')''',
        (name, digest, source_type, source_type, parser_version, raw_content, row_count))
    return cursor.lastrowid


def ingest_payway_resumen(data: dict) -> tuple[int, int]:
    """Raw + resumen + dias + conceptos en una sola transaccion."""
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        raw_id = _upsert_raw(conn, name=os.path.basename(data['path_archivo']), digest=data['hash_sha256'],
                             source_type='PDF', parser_version=data['parser_version'], raw_content=data['contenido_raw'],
                             row_count=len(data['dias']))
        cursor = conn.execute('''INSERT INTO tarjetas_payway_resumenes
            (raw_ingesta_id, fecha_emision, periodo, numero_resumen, pagador_codigo, pagador_nombre,
             establecimiento, marca, bruto_centavos, descuentos_centavos, neto_centavos, path_archivo, hash_archivo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(establecimiento, pagador_codigo, numero_resumen, fecha_emision) DO UPDATE SET
              raw_ingesta_id=excluded.raw_ingesta_id, pagador_nombre=excluded.pagador_nombre,
              bruto_centavos=excluded.bruto_centavos, descuentos_centavos=excluded.descuentos_centavos,
              neto_centavos=excluded.neto_centavos, path_archivo=excluded.path_archivo,
              hash_archivo=excluded.hash_archivo, updated_at=CURRENT_TIMESTAMP
            RETURNING id''', (raw_id, data['fecha_emision'], data['periodo'], data['numero_resumen'],
              data['pagador_codigo'], data['pagador_nombre'], data['establecimiento'], data['marca'],
              data['bruto_centavos'], data['descuentos_centavos'], data['neto_centavos'],
              data['path_archivo'], data['hash_sha256']))
        summary_id = cursor.fetchone()[0]
        conn.execute('DELETE FROM tarjetas_payway_resumen_dias WHERE resumen_id=?', (summary_id,))
        conn.execute('DELETE FROM tarjetas_payway_resumen_conceptos WHERE resumen_id=?', (summary_id,))
        conn.executemany('''INSERT INTO tarjetas_payway_resumen_dias
            (resumen_id, raw_ingesta_id, numero_linea, fecha_pago, bruto_centavos, descuentos_centavos, neto_centavos, liquidaciones_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', [(summary_id, raw_id, d['numero_linea'], d['fecha_pago'],
              d['bruto_centavos'], d['descuentos_centavos'], d['neto_centavos'], json.dumps(d['liquidaciones'])) for d in data['dias']])
        conn.executemany('''INSERT INTO tarjetas_payway_resumen_conceptos
            (resumen_id, raw_ingesta_id, numero_linea, categoria, descripcion, importe_centavos)
            VALUES (?, ?, ?, ?, ?, ?)''', [(summary_id, raw_id, n, c['categoria'], c['descripcion'], c['importe_centavos'])
              for n, c in enumerate(data['conceptos'], start=1)])
        conn.execute("UPDATE core_staging_raw SET estado='PROCESADO', fecha_procesado=datetime('now','localtime') WHERE id=?", (raw_id,))
        conn.execute("INSERT INTO core_staging_logs(staging_id, resultado, detalles) VALUES (?, 'OK', ?)",
                     (raw_id, f"Resumen Payway {data['numero_resumen']}"))
        conn.commit()
        return summary_id, raw_id
    except Exception as exc:
        conn.rollback()
        logger.exception("Error en ingesta ELT de resumen Payway")
        raise
    finally:
        conn.close()


def ingest_payway_movimientos(data: dict) -> tuple[int, int]:
    """Raw + movimientos en una sola transaccion, sin SQL fuera del repositorio."""
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        rows = data['movimientos']
        raw_id = _upsert_raw(conn, name=os.path.basename(data['path_archivo']), digest=data['hash_sha256'],
                             source_type='CSV', parser_version=data['parser_version'], raw_content=data['contenido_raw'],
                             row_count=len(rows))
        conn.execute('DELETE FROM tarjetas_payway_movimientos WHERE hash_archivo=?', (data['hash_sha256'],))
        before = conn.total_changes
        conn.executemany('''INSERT INTO tarjetas_payway_movimientos
            (raw_ingesta_id, numero_linea, fecha_compra, fecha_presentacion, fecha_pago, tipo, lote, cupon,
             marca, establecimiento, bruto_centavos, detalle, tarjeta_enmascarada, cuotas, modalidad,
             autorizacion, operacion_asociada, path_archivo, hash_archivo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(establecimiento, fecha_compra, lote, cupon, marca, bruto_centavos) DO UPDATE SET
              raw_ingesta_id=excluded.raw_ingesta_id, numero_linea=excluded.numero_linea,
              fecha_presentacion=excluded.fecha_presentacion, fecha_pago=excluded.fecha_pago,
              tipo=excluded.tipo, detalle=excluded.detalle, tarjeta_enmascarada=excluded.tarjeta_enmascarada,
              cuotas=excluded.cuotas, modalidad=excluded.modalidad, autorizacion=excluded.autorizacion,
              operacion_asociada=excluded.operacion_asociada, path_archivo=excluded.path_archivo,
              hash_archivo=excluded.hash_archivo''', [(raw_id, r['numero_linea'], r['fecha_compra'], r['fecha_presentacion'],
              r['fecha_pago'], r['tipo'], r['lote'], r['cupon'], r['marca'], r['establecimiento'], r['bruto_centavos'],
              r['detalle'], r['tarjeta_enmascarada'], r['cuotas'], r['modalidad'], r['autorizacion'],
              r['operacion_asociada'], data['path_archivo'], data['hash_sha256']) for r in rows])
        conn.execute("UPDATE core_staging_raw SET estado='PROCESADO', fecha_procesado=datetime('now','localtime') WHERE id=?", (raw_id,))
        conn.execute("INSERT INTO core_staging_logs(staging_id, resultado, detalles) VALUES (?, 'OK', ?)",
                     (raw_id, f"{len(rows)} movimientos Payway"))
        conn.commit()
        return len(rows), raw_id
    except Exception:
        conn.rollback()
        logger.exception("Error en ingesta ELT de movimientos Payway")
        raise
    finally:
        conn.close()


def ingest_patagonia_resumen(data: dict) -> tuple[int, int]:
    """Raw + cabecera + liquidaciones Patagonia 365 en una transacción."""
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        rows = data['liquidaciones']
        raw_id = _upsert_raw(conn, name=data['nombre_archivo'], digest=data['hash_sha256'],
                             source_type='PDF_PATAGONIA365_LIQUIDACION_VENTAS', parser_version=data['parser_version'],
                             raw_content=data['contenido_raw'], row_count=len(rows))
        cursor = conn.execute('''INSERT INTO tarjetas_patagonia_resumenes
            (raw_ingesta_id, periodo, numero_resumen, comercio, comercio_id, cuit, bruto_centavos,
             arancel_centavos, financiero_centavos, otros_cargos_centavos, promociones_centavos,
             iva_ri_centavos, retencion_iva_centavos, retencion_ganancias_centavos,
             retencion_iibb_centavos, neto_centavos, path_archivo, hash_archivo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(comercio, numero_resumen, periodo) DO UPDATE SET
              raw_ingesta_id=excluded.raw_ingesta_id, comercio_id=excluded.comercio_id, cuit=excluded.cuit,
              bruto_centavos=excluded.bruto_centavos, arancel_centavos=excluded.arancel_centavos,
              financiero_centavos=excluded.financiero_centavos,
              otros_cargos_centavos=excluded.otros_cargos_centavos,
              promociones_centavos=excluded.promociones_centavos, iva_ri_centavos=excluded.iva_ri_centavos,
              retencion_iva_centavos=excluded.retencion_iva_centavos,
              retencion_ganancias_centavos=excluded.retencion_ganancias_centavos,
              retencion_iibb_centavos=excluded.retencion_iibb_centavos, neto_centavos=excluded.neto_centavos,
              path_archivo=excluded.path_archivo, hash_archivo=excluded.hash_archivo,
              updated_at=CURRENT_TIMESTAMP RETURNING id''',
            (raw_id, data['periodo'], data['numero_resumen'], data['comercio'], data['comercio_id'], data['cuit'],
             data['bruto_centavos'], data['arancel_centavos'], data['financiero_centavos'],
             data['otros_cargos_centavos'], data['promociones_centavos'], data['iva_ri_centavos'],
             data['retencion_iva_centavos'], data['retencion_ganancias_centavos'],
             data['retencion_iibb_centavos'], data['neto_centavos'], data['path_archivo'], data['hash_sha256']))
        summary_id = cursor.fetchone()[0]
        conn.execute('DELETE FROM tarjetas_patagonia_liquidaciones WHERE resumen_id=?', (summary_id,))
        conn.executemany('''INSERT INTO tarjetas_patagonia_liquidaciones
            (resumen_id, raw_ingesta_id, numero_linea, numero_liquidacion, fecha_pago, fecha_presentacion,
             bruto_centavos, arancel_centavos, financiero_centavos, otras_deducciones_centavos,
             deducciones_impositivas_centavos, neto_centavos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            [(summary_id, raw_id, number, row['numero_liquidacion'], row['fecha_pago'], row['fecha_presentacion'],
              row['bruto_centavos'], row['arancel_centavos'], row['financiero_centavos'],
              row['otras_deducciones_centavos'], row['deducciones_impositivas_centavos'], row['neto_centavos'])
             for number, row in enumerate(rows, start=1)])

        # Compatibilidad con pantallas históricas: una sola cabecera exacta, derivada de centavos.
        legacy = {
            'fuente': 'PATAGONIA365', 'marca': 'PATAGONIA 365', 'tipo': 'MENSUAL',
            'fecha_liquidacion': f"{data['periodo']}-01", 'periodo': data['periodo'],
            'establecimiento': data['comercio'], 'total_bruto': data['bruto_centavos'] / 100,
            'costo_arancel': data['arancel_centavos'] / 100,
            'costo_financiero': data['financiero_centavos'] / 100, 'iva_21': data['iva_ri_centavos'] / 100,
            'iva_105': 0, 'retenciones': (data['retencion_iva_centavos']
                + data['retencion_ganancias_centavos'] + data['retencion_iibb_centavos']) / 100,
            'total_neto': data['neto_centavos'] / 100, 'hash_archivo': data['hash_sha256'],
            'path_archivo': data['path_archivo'], 'metadata_cruda': data['contenido_raw'],
        }
        existing = conn.execute("SELECT id FROM tarjetas_liquidaciones WHERE hash_archivo=?", (data['hash_sha256'],)).fetchone()
        values = (legacy['fuente'], legacy['marca'], legacy['tipo'], legacy['fecha_liquidacion'], legacy['periodo'],
                  legacy['establecimiento'], legacy['total_bruto'], legacy['costo_arancel'], legacy['costo_financiero'],
                  legacy['iva_21'], legacy['iva_105'], legacy['retenciones'], legacy['total_neto'],
                  legacy['hash_archivo'], legacy['path_archivo'], legacy['metadata_cruda'])
        if existing:
            conn.execute('''UPDATE tarjetas_liquidaciones SET fuente=?, marca=?, tipo=?, fecha_liquidacion=?,
                periodo=?, establecimiento=?, total_bruto=?, costo_arancel=?, costo_financiero=?, iva_21=?,
                iva_105=?, retenciones=?, total_neto=?, hash_archivo=?, path_archivo=?, metadata_cruda=? WHERE id=?''',
                values + (existing['id'],))
            legacy_id = existing['id']
        else:
            legacy_id = conn.execute('''INSERT INTO tarjetas_liquidaciones
                (fuente, marca, tipo, fecha_liquidacion, periodo, establecimiento, total_bruto, costo_arancel,
                 costo_financiero, iva_21, iva_105, retenciones, total_neto, hash_archivo, path_archivo, metadata_cruda)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', values).lastrowid
        conn.execute('DELETE FROM tarjetas_liquidaciones_detalles WHERE liquidacion_id=?', (legacy_id,))
        conn.executemany('''INSERT INTO tarjetas_liquidaciones_detalles
            (liquidacion_id, fecha, descripcion, monto_bruto, arancel, financiero, iva, retenciones, monto_neto, metadata_cruda)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            [(legacy_id, row['fecha_pago'], f"Liquidación {row['numero_liquidacion']}", row['bruto_centavos'] / 100,
              row['arancel_centavos'] / 100, row['financiero_centavos'] / 100,
              row['deducciones_impositivas_centavos'] / 100, row['otras_deducciones_centavos'] / 100,
              row['neto_centavos'] / 100, json.dumps(row, ensure_ascii=False)) for row in rows])
        conn.execute("UPDATE core_staging_raw SET estado='PROCESADO', fecha_procesado=datetime('now','localtime') WHERE id=?", (raw_id,))
        conn.execute("INSERT INTO core_staging_logs(staging_id, resultado, detalles) VALUES (?, 'OK', ?)",
                     (raw_id, f"Resumen Patagonia 365 {data['numero_resumen']} con {len(rows)} liquidaciones"))
        conn.commit()
        return summary_id, raw_id
    except Exception:
        conn.rollback()
        logger.exception('Error en ingesta ELT Patagonia 365')
        raise
    finally:
        conn.close()


def update_patagonia_path(hash_archivo: str, new_path: str):
    safe_path = str(new_path).replace('\\', '/')
    conn = get_db_connection()
    try:
        conn.execute('UPDATE tarjetas_patagonia_resumenes SET path_archivo=? WHERE hash_archivo=?', (safe_path, hash_archivo))
        conn.execute('UPDATE tarjetas_liquidaciones SET path_archivo=? WHERE hash_archivo=?', (safe_path, hash_archivo))
        conn.commit()
    finally:
        conn.close()


def update_payway_path(hash_archivo: str, new_path: str):
    safe_path = str(new_path).replace('\\', '/')
    conn = get_db_connection()
    try:
        conn.execute('UPDATE tarjetas_payway_resumenes SET path_archivo=? WHERE hash_archivo=?', (safe_path, hash_archivo))
        conn.execute('UPDATE tarjetas_payway_movimientos SET path_archivo=? WHERE hash_archivo=?', (safe_path, hash_archivo))
        conn.commit()
    finally:
        conn.close()


def get_payway_conciliacion(fecha_desde: str, fecha_hasta: str) -> dict:
    conn = get_db_connection()
    try:
        rows = [dict(row) for row in conn.execute('''
            SELECT * FROM vw_payway_conciliacion_diaria
            WHERE fecha_pago BETWEEN ? AND ?
            ORDER BY fecha_pago, marca, establecimiento
        ''', (fecha_desde, fecha_hasta)).fetchall()]
        totals = {
            'dias': len(rows),
            'conciliados': sum(row['estado'] == 'CONCILIADO' for row in rows),
            'cobrado_centavos': sum(row['cobrado_centavos'] for row in rows),
            'liquidado_bruto_centavos': sum(row['liquidado_bruto_centavos'] for row in rows),
            'descuentos_centavos': sum(row['descuentos_centavos'] for row in rows),
            'neto_centavos': sum(row['neto_centavos'] for row in rows),
            'diferencia_centavos': sum(row['diferencia_centavos'] for row in rows),
        }
        totals['estado'] = 'CONCILIADO' if rows and totals['conciliados'] == len(rows) else 'INCOMPLETO'
        return {'desde': fecha_desde, 'hasta': fecha_hasta, 'totales': totals, 'filas': rows}
    finally:
        conn.close()


def save_liquidacion(data: dict):
    """Persistencia híbrida v4.0 de cabecera de liquidación."""
    conn = get_db_connection()
    try:
        columnas_duras = {
            'fuente', 'marca', 'tipo', 'fecha_liquidacion', 'periodo',
            'establecimiento', 'total_bruto', 'costo_arancel', 'costo_financiero',
            'iva_21', 'iva_105', 'retenciones', 'total_neto', 'hash_archivo', 'path_archivo'
        }
        metadata = {k: v for k, v in data.items() if k not in columnas_duras}

        cursor = conn.execute('''
            INSERT OR IGNORE INTO tarjetas_liquidaciones (
                fuente, marca, tipo, fecha_liquidacion, periodo, establecimiento,
                total_bruto, costo_arancel, costo_financiero, iva_21, iva_105,
                retenciones, total_neto, hash_archivo, path_archivo, metadata_cruda
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('fuente', 'DESCONOCIDA').upper(),
            data.get('marca'), data.get('tipo', 'MENSUAL').upper(),
            data.get('fecha_liquidacion'), data.get('periodo'),
            data.get('establecimiento'),
            data.get('total_bruto', 0), data.get('costo_arancel', 0),
            data.get('costo_financiero', 0), data.get('iva_21', 0),
            data.get('iva_105', 0), data.get('retenciones', 0),
            data.get('total_neto', 0), data.get('hash_archivo'),
            data.get('path_archivo'),
            json.dumps(metadata, ensure_ascii=False, default=str)
        ))

        last_id = cursor.lastrowid
        if last_id == 0 or last_id is None:
            res = conn.execute(
                "SELECT id FROM tarjetas_liquidaciones WHERE hash_archivo = ?",
                (data.get('hash_archivo'),)
            ).fetchone()
            if res:
                last_id = res['id']

        conn.commit()
        return last_id
    except Exception as e:
        logger.warning(f"Error guardando liquidación: {e}")
        return None
    finally:
        conn.close()


def save_tarjetas_payway(lista_cupones: list, hash_archivo: str = None):
    """Persistencia masiva de registros de Payway v4.0."""
    conn = get_db_connection()
    try:
        agregados = 0
        for c in lista_cupones:
            columnas_duras = {
                'fuente', 'fecha_compra', 'fecha_pago', 'lote',
                'cupon', 'marca', 'monto_bruto', 'hash_archivo', 'path_archivo', 'matching_tx_id'
            }
            metadata = {k: v for k, v in c.items() if k not in columnas_duras}

            try:
                conn.execute('''
                    INSERT OR IGNORE INTO tarjetas_payway (
                        fuente, fecha_compra, fecha_pago, lote, cupon,
                        marca, monto_bruto, hash_archivo, path_archivo, 
                        matching_tx_id, metadata_cruda
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    c.get('fuente', 'PAYWAY'), c.get('fecha_compra'),
                    c.get('fecha_pago'), c.get('lote'), c.get('cupon'),
                    c.get('marca'), c.get('monto_bruto', 0),
                    c.get('hash_archivo', hash_archivo),
                    c.get('path_archivo'),
                    c.get('matching_tx_id'),
                    json.dumps(metadata, ensure_ascii=False, default=str)
                ))
                agregados += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
        return agregados
    except Exception as e:
        logger.warning(f"Error guardando tarjetas_payway: {e}")
        return 0
    finally:
        conn.close()


def update_record_path(record_id, new_path, table="tarjetas_payway"):
    """Actualiza la ruta física del archivo tras el archivado legal v4.0."""
    conn = get_db_connection()
    try:
        # Validación básica de tabla para evitar inyecciones
        if table not in ["tarjetas_payway", "tarjetas_liquidaciones"]:
            raise ValueError(f"Tabla no permitida: {table}")
            
        conn.execute(f"UPDATE {table} SET path_archivo = ? WHERE id = ?", (new_path, record_id))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error actualizando path en {table}: {e}")
    finally:
        conn.close()


def get_resumen_tarjetas(anio=None):
    """Estadísticas consolidadas v4.0."""
    conn = get_db_connection()
    cur = conn.cursor()
    params = [f"{anio}%"] if anio else []
    
    # 1. Ventas por Posnet
    q_ventas = "SELECT COUNT(*), SUM(monto_bruto) FROM tarjetas_payway"
    if anio: q_ventas += " WHERE fecha_compra LIKE ?"
    res_v = cur.execute(q_ventas, params).fetchone()

    # 2. Liquidaciones Consolidadas
    q_liq = """
        SELECT fuente, tipo, COUNT(*), SUM(total_bruto), SUM(total_neto), 
               SUM(costo_arancel + costo_financiero + retenciones + iva_21 + iva_105) 
        FROM tarjetas_liquidaciones
    """
    if anio: q_liq += " WHERE (fecha_liquidacion LIKE ? OR periodo LIKE ?)"
    
    p_liq = [f"{anio}%", f"{anio}%"] if anio else []
    res_l = cur.execute(q_liq + " GROUP BY fuente, tipo", p_liq).fetchall()
    
    conn.close()
    
    return {
        "ventas_posnet": {"total_count": res_v[0] or 0, "monto_bruto": res_v[1] or 0.0},
        "liquidaciones": [
            {
                "fuente": r[0], "tipo": r[1], "cantidad": r[2],
                "bruto": r[3] or 0.0, "neto": r[4] or 0.0, "gastos": r[5] or 0.0
            } for r in res_l
        ]
    }


def get_cupon_detalle(cupon_id):
    """Busca detalle de un cupón v4.0."""
    conn = get_db_connection()
    cur = conn.cursor()
    q_pad = str(cupon_id).zfill(8)
    row = cur.execute("""
        SELECT * FROM tarjetas_payway 
        WHERE cupon = ? OR cupon LIKE ? OR id = ?
    """, (q_pad, f"%{cupon_id}", cupon_id)).fetchone()
    conn.close()
    
    if row:
        res = dict(row)
        try:
            res['metadata_cruda'] = json.loads(res['metadata_cruda'])
        except:
            pass
        return res
    return None

def save_liquidacion_detalles(liq_id, detalles):
    """Guarda los lotes diarios de liquidación de Payway detallados."""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM tarjetas_liquidaciones_detalles WHERE liquidacion_id = ?", (liq_id,))
        for d in detalles:
            conn.execute("""
                INSERT INTO tarjetas_liquidaciones_detalles (
                    liquidacion_id, fecha, descripcion, monto_bruto, arancel, financiero, iva, retenciones, monto_neto
                ) VALUES (?, ?, ?, ?, ?, 0.0, 0.0, 0.0, ?)
            """, (liq_id, d['fecha_pago'], f"Liq Nro {d['nro_liq']} - Lote {d['lote']}", d['bruto'], d['descuentos'], d['neto']))
        conn.commit()
    except Exception as e:
        print(f"Error guardando detalles de liquidación: {e}")
    finally:
        conn.close()
