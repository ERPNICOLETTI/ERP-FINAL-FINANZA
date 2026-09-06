import sqlite3
import json
import os
import logging
import re

# STORAGE COMPRAS - v4.5 GOLDEN MASTER 🧾🧱🧠⚖️
# Diseño Híbrido: Columnas Duras + meta_json (JSON) + path_archivo

def sanitize_path_db(path):
    """Leyes de la Bóveda v5.2: Normalización universal y limpieza de ruido binario."""
    if not path: return None
    # 1. Normalización total a diagonales web (/)
    p = str(path).replace('\\', '/')
    # 2. Eliminación de caracteres no imprimibles o ruido binario (como nulos \0)
    p = "".join([c for c in p if 31 < ord(c) < 127 or ord(c) > 160])
    # 3. Quitar duplicación de barras y espacios extra
    p = re.sub(r'/+', '/', p)
    # 4. Asegurar que las rutas absolutas de Windows retengan su formato C:/
    p = p.replace(':/', '://').replace('://', ':/')
    return p.strip()

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


def _ensure_column(conn, table, column, definition):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db_compras():
    """Crea las tablas del dominio Compras con diseño híbrido v4.5."""
    conn = get_db_connection()
    print("🧱 [COMPRAS] Construyendo tablas Golden Master v4.5 (Híbrido)...")

    # ── Tabla de Proveedores (Maestro) ──────────────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS compras_proveedores (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cuit            TEXT UNIQUE,
            nombre_fantasia TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Tabla Maestra de Facturas ──────────────────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS compras_facturas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha           TEXT,
            tipo_comprobante TEXT,
            punto_venta     TEXT,
            numero_comprobante TEXT,
            cuit_proveedor  TEXT,
            proveedor       TEXT,
            neto            REAL DEFAULT 0,
            iva21           REAL DEFAULT 0,
            iva105          REAL DEFAULT 0,
            iva27           REAL DEFAULT 0,
            exento          REAL DEFAULT 0,
            percepcion_iva  REAL DEFAULT 0,
            imp_internos    REAL DEFAULT 0,
            total           REAL DEFAULT 0,
            moneda          TEXT DEFAULT 'ARS',
            tipo_operacion  TEXT DEFAULT 'COMPRA',
            status          TEXT DEFAULT 'SOLO_AFIP',
            tiene_foto      BOOLEAN DEFAULT 0,
            path_archivo    TEXT,
            hash_archivo    TEXT,
            origen          TEXT DEFAULT 'MANUAL',
            meta_json       TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(cuit_proveedor, punto_venta, numero_comprobante, tipo_comprobante)
        )
    ''')

    # ── Libro IVA Consolidado ──────────────────────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS compras_libroiva (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo         TEXT UNIQUE,
            debito_fiscal   REAL DEFAULT 0,
            credito_fiscal  REAL DEFAULT 0,
            saldo_tecnico   REAL DEFAULT 0,
            saldo_libre_disponibilidad REAL DEFAULT 0,
            path_archivo    TEXT,
            hash_archivo    TEXT UNIQUE,
            meta_json       TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── IVA Desglosado (Cross-Module Service) ──────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS compras_iva_desglosado (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo_origen   TEXT,
            fuente          TEXT,
            fecha           TEXT,
            neto            REAL DEFAULT 0,
            iva105          REAL DEFAULT 0,
            iva21           REAL DEFAULT 0,
            descripcion     TEXT,
            extern_id       INTEGER,
            hash_archivo    TEXT,
            meta_json       TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    arca_columns = {
        'tipo_comprobante_codigo': 'INTEGER', 'signo': 'INTEGER DEFAULT 1', 'cae': 'TEXT',
        'raw_ingesta_id': 'INTEGER', 'zip_raw_ingesta_id': 'INTEGER', 'numero_linea': 'INTEGER',
        'neto_gravado_centavos': 'INTEGER DEFAULT 0', 'neto_iva_0_centavos': 'INTEGER DEFAULT 0',
        'iva_25_centavos': 'INTEGER DEFAULT 0', 'neto_iva_25_centavos': 'INTEGER DEFAULT 0',
        'iva_5_centavos': 'INTEGER DEFAULT 0', 'neto_iva_5_centavos': 'INTEGER DEFAULT 0',
        'iva_105_centavos': 'INTEGER DEFAULT 0', 'neto_iva_105_centavos': 'INTEGER DEFAULT 0',
        'iva_21_centavos': 'INTEGER DEFAULT 0', 'neto_iva_21_centavos': 'INTEGER DEFAULT 0',
        'iva_27_centavos': 'INTEGER DEFAULT 0', 'neto_iva_27_centavos': 'INTEGER DEFAULT 0',
        'no_gravado_centavos': 'INTEGER DEFAULT 0', 'exento_centavos': 'INTEGER DEFAULT 0',
        'otros_tributos_centavos': 'INTEGER DEFAULT 0', 'total_iva_centavos': 'INTEGER DEFAULT 0',
        'total_centavos': 'INTEGER DEFAULT 0', 'documento_receptor': 'TEXT', 'updated_at': 'TIMESTAMP',
        'calim_raw_ingesta_id': 'INTEGER', 'calim_hash_archivo': 'TEXT',
        'calim_neto_centavos': 'INTEGER', 'calim_iva_total_centavos': 'INTEGER',
        'calim_total_centavos': 'INTEGER', 'calim_estado': 'TEXT',
    }
    for column, definition in arca_columns.items():
        _ensure_column(conn, 'compras_facturas', column, definition)

    conn.execute('''CREATE TABLE IF NOT EXISTS compras_arca_ingestas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zip_raw_ingesta_id INTEGER NOT NULL,
        csv_raw_ingesta_id INTEGER NOT NULL,
        nombre_zip TEXT NOT NULL,
        nombre_csv TEXT NOT NULL,
        hash_zip TEXT NOT NULL,
        hash_csv TEXT NOT NULL,
        path_archivo TEXT NOT NULL,
        filas INTEGER NOT NULL,
        fecha_min TEXT NOT NULL,
        fecha_max TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(zip_raw_ingesta_id, csv_raw_ingesta_id),
        FOREIGN KEY(zip_raw_ingesta_id) REFERENCES core_staging_raw(id),
        FOREIGN KEY(csv_raw_ingesta_id) REFERENCES core_staging_raw(id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS compras_calim_ingestas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_ingesta_id INTEGER NOT NULL UNIQUE,
        nombre_archivo TEXT NOT NULL,
        hash_archivo TEXT NOT NULL UNIQUE,
        path_archivo TEXT NOT NULL,
        filas INTEGER NOT NULL,
        fecha_min TEXT,
        fecha_max TEXT,
        conciliadas INTEGER NOT NULL DEFAULT 0,
        diferencias INTEGER NOT NULL DEFAULT 0,
        solo_calim INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(raw_ingesta_id) REFERENCES core_staging_raw(id)
    )''')

    conn.commit()
    conn.close()


def _stage_raw(conn, *, name, digest, source_type, raw_format, parser_version, content, rows):
    found = conn.execute('SELECT id FROM core_staging_raw WHERE hash_sha256=?', (digest,)).fetchone()
    if found:
        return found['id']
    cursor = conn.execute('''INSERT INTO core_staging_raw
        (nombre_archivo, hash_sha256, modulo, tipo_fuente, formato_raw, parser_version,
         contenido_raw, filas_leidas, estado, fecha_procesado)
        VALUES (?, ?, 'compras', ?, ?, ?, ?, ?, 'PROCESADO', datetime('now','localtime'))''',
        (name, digest, source_type, raw_format, parser_version, content, rows))
    return cursor.lastrowid


def ingest_arca_recibidos(package: dict) -> dict:
    """Ingesta atomica ZIP -> raw ZIP/CSV -> comprobantes recibidos."""
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        zip_raw_id = None
        if package.get('formato_fuente') == 'ZIP':
            zip_raw_id = _stage_raw(conn, name=package['nombre_archivo'], digest=package['hash_sha256'],
                source_type='ARCA_ZIP_RECIBIDOS', raw_format='ZIP_MANIFEST', parser_version=package['parser_version'],
                content=package['manifest_raw'], rows=sum(len(csv_file['filas']) for csv_file in package['csvs']))
        processed = 0
        csv_raw_ids = []
        for csv_file in package['csvs']:
            csv_raw_id = _stage_raw(conn, name=csv_file['nombre'], digest=csv_file['hash_sha256'],
                source_type='ARCA_COMPROBANTES_RECIBIDOS', raw_format='CSV', parser_version=package['parser_version'],
                content=csv_file['contenido_raw'], rows=len(csv_file['filas']))
            csv_raw_ids.append(csv_raw_id)
            if zip_raw_id is None:
                zip_raw_id = csv_raw_id
            conn.execute('''INSERT INTO compras_arca_ingestas
                (zip_raw_ingesta_id, csv_raw_ingesta_id, nombre_zip, nombre_csv, hash_zip, hash_csv,
                 path_archivo, filas, fecha_min, fecha_max)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(zip_raw_ingesta_id, csv_raw_ingesta_id) DO UPDATE SET
                  path_archivo=excluded.path_archivo, filas=excluded.filas,
                  fecha_min=excluded.fecha_min, fecha_max=excluded.fecha_max''',
                (zip_raw_id, csv_raw_id, package['nombre_archivo'], csv_file['nombre'], package['hash_sha256'],
                 csv_file['hash_sha256'], package['path_archivo'], len(csv_file['filas']), package['fecha_min'], package['fecha_max']))
            for row in csv_file['filas']:
                signed = row['signo']
                values = {key: row[key] * signed for key in (
                    'neto_gravado_centavos', 'neto_iva_0_centavos', 'iva_25_centavos', 'neto_iva_25_centavos',
                    'iva_5_centavos', 'neto_iva_5_centavos', 'iva_105_centavos', 'neto_iva_105_centavos',
                    'iva_21_centavos', 'neto_iva_21_centavos', 'iva_27_centavos', 'neto_iva_27_centavos',
                    'no_gravado_centavos', 'exento_centavos', 'otros_tributos_centavos',
                    'total_iva_centavos', 'total_centavos')}
                metadata = {'numero_hasta': row['numero_hasta'], 'tipo_doc_emisor': row['tipo_doc_emisor'],
                    'tipo_doc_receptor': row['tipo_doc_receptor'], 'tipo_cambio': row['tipo_cambio'],
                    'row_raw': row['row_raw']}
                # Normaliza importaciones AFIP antiguas cuyo nombre de tipo podia estar mojibakeado.
                candidates = conn.execute('''SELECT id, tipo_comprobante_codigo, meta_json
                    FROM compras_facturas WHERE cuit_proveedor=? AND punto_venta=? AND numero_comprobante=?''',
                    (row['cuit_proveedor'], row['punto_venta'], row['numero_comprobante'])).fetchall()
                for candidate in candidates:
                    legacy_code = candidate['tipo_comprobante_codigo']
                    if legacy_code is None:
                        try:
                            legacy = json.loads(candidate['meta_json'] or '{}').get('row_dump', {})
                            legacy_code = int(legacy.get('Tipo de Comprobante'))
                        except (ValueError, TypeError, AttributeError):
                            legacy_code = None
                    if legacy_code == row['tipo_comprobante_codigo']:
                        conn.execute('UPDATE compras_facturas SET tipo_comprobante=?, tipo_comprobante_codigo=? WHERE id=?',
                                     (row['tipo_comprobante'], row['tipo_comprobante_codigo'], candidate['id']))
                        break
                conn.execute('''INSERT INTO compras_facturas (
                    fecha, tipo_comprobante, tipo_comprobante_codigo, signo, punto_venta, numero_comprobante,
                    cuit_proveedor, proveedor, neto, iva21, iva105, iva27, exento, percepcion_iva, total,
                    moneda, tipo_operacion, status, tiene_foto, path_archivo, hash_archivo, origen, meta_json,
                    cae, raw_ingesta_id, zip_raw_ingesta_id, numero_linea, documento_receptor,
                    neto_gravado_centavos, neto_iva_0_centavos, iva_25_centavos, neto_iva_25_centavos,
                    iva_5_centavos, neto_iva_5_centavos, iva_105_centavos, neto_iva_105_centavos,
                    iva_21_centavos, neto_iva_21_centavos, iva_27_centavos, neto_iva_27_centavos,
                    no_gravado_centavos, exento_centavos, otros_tributos_centavos, total_iva_centavos,
                    total_centavos, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPRA', 'SOLO_ARCA', 0,
                    ?, ?, 'ARCA_CSV_RECIBIDOS', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                    ON CONFLICT(cuit_proveedor, punto_venta, numero_comprobante, tipo_comprobante) DO UPDATE SET
                      fecha=excluded.fecha, proveedor=excluded.proveedor, neto=excluded.neto,
                      iva21=excluded.iva21, iva105=excluded.iva105, iva27=excluded.iva27,
                      exento=excluded.exento, percepcion_iva=excluded.percepcion_iva, total=excluded.total,
                      moneda=excluded.moneda, hash_archivo=excluded.hash_archivo, meta_json=excluded.meta_json,
                      tipo_comprobante_codigo=excluded.tipo_comprobante_codigo, signo=excluded.signo,
                      cae=excluded.cae, raw_ingesta_id=excluded.raw_ingesta_id,
                      zip_raw_ingesta_id=excluded.zip_raw_ingesta_id, numero_linea=excluded.numero_linea,
                      documento_receptor=excluded.documento_receptor,
                      neto_gravado_centavos=excluded.neto_gravado_centavos,
                      neto_iva_0_centavos=excluded.neto_iva_0_centavos, iva_25_centavos=excluded.iva_25_centavos,
                      neto_iva_25_centavos=excluded.neto_iva_25_centavos, iva_5_centavos=excluded.iva_5_centavos,
                      neto_iva_5_centavos=excluded.neto_iva_5_centavos, iva_105_centavos=excluded.iva_105_centavos,
                      neto_iva_105_centavos=excluded.neto_iva_105_centavos, iva_21_centavos=excluded.iva_21_centavos,
                      neto_iva_21_centavos=excluded.neto_iva_21_centavos, iva_27_centavos=excluded.iva_27_centavos,
                      neto_iva_27_centavos=excluded.neto_iva_27_centavos, no_gravado_centavos=excluded.no_gravado_centavos,
                      exento_centavos=excluded.exento_centavos, otros_tributos_centavos=excluded.otros_tributos_centavos,
                      total_iva_centavos=excluded.total_iva_centavos, total_centavos=excluded.total_centavos,
                      updated_at=datetime('now','localtime')''', (
                    row['fecha'], row['tipo_comprobante'], row['tipo_comprobante_codigo'], row['signo'],
                    row['punto_venta'], row['numero_comprobante'], row['cuit_proveedor'], row['proveedor'],
                    values['neto_gravado_centavos']/100, values['iva_21_centavos']/100,
                    values['iva_105_centavos']/100, values['iva_27_centavos']/100,
                    (values['exento_centavos']+values['no_gravado_centavos'])/100,
                    values['otros_tributos_centavos']/100, values['total_centavos']/100, row['moneda'],
                    None, csv_file['hash_sha256'], json.dumps(metadata, ensure_ascii=False),
                    row['cae'], csv_raw_id, zip_raw_id, row['numero_linea'], row['documento_receptor'],
                    *(values[key] for key in (
                      'neto_gravado_centavos','neto_iva_0_centavos','iva_25_centavos','neto_iva_25_centavos',
                      'iva_5_centavos','neto_iva_5_centavos','iva_105_centavos','neto_iva_105_centavos',
                      'iva_21_centavos','neto_iva_21_centavos','iva_27_centavos','neto_iva_27_centavos',
                      'no_gravado_centavos','exento_centavos','otros_tributos_centavos','total_iva_centavos','total_centavos'))))
                processed += 1
            conn.execute("INSERT INTO core_staging_logs(staging_id, resultado, detalles) VALUES (?, 'OK', ?)",
                         (csv_raw_id, f"{len(csv_file['filas'])} comprobantes recibidos ARCA"))
        conn.commit()
        return {'zip_raw_ingesta_id': zip_raw_id, 'csv_raw_ingesta_ids': csv_raw_ids, 'filas': processed}
    except Exception:
        conn.rollback()
        logger.exception('Error en ingesta ELT de comprobantes recibidos ARCA')
        raise
    finally:
        conn.close()


def update_arca_zip_path(hash_zip, new_path):
    safe = sanitize_path_db(new_path)
    conn = get_db_connection()
    try:
        conn.execute('UPDATE compras_arca_ingestas SET path_archivo=? WHERE hash_zip=?', (safe, hash_zip))
        conn.commit()
    finally:
        conn.close()


def ingest_calim_compras(data: dict) -> dict:
    """Ingesta CALIM transaccional y conciliación contra ARCA por identidad fiscal."""
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        raw_id = _stage_raw(conn, name=data['nombre_archivo'], digest=data['hash_sha256'],
            source_type='CALIM_FACTURAS_COMPRA', raw_format='XLSX_JSON', parser_version=data['parser_version'],
            content=data['contenido_raw'], rows=len(data['filas']))
        counters = {'conciliadas': 0, 'diferencias': 0, 'solo_calim': 0}
        for row in data['filas']:
            candidates = conn.execute('''SELECT * FROM compras_facturas
                WHERE punto_venta=? AND numero_comprobante=? AND fecha=?
                  AND (tipo_comprobante_codigo=? OR tipo_comprobante_codigo IS NULL)
                  AND (cuit_proveedor=? OR (cuit_proveedor IS NULL AND proveedor LIKE ?))
                ORDER BY CASE WHEN raw_ingesta_id IS NOT NULL THEN 0 ELSE 1 END, id''',
                (row['punto_venta'], row['numero_comprobante'], row['fecha'], row['tipo_comprobante_codigo'],
                 row['cuit_proveedor'], row['cuit_proveedor'] + ' -%')).fetchall()
            canonical = next((candidate for candidate in candidates if candidate['raw_ingesta_id'] is not None), None)
            if canonical:
                arca_iva = canonical['total_iva_centavos'] or 0
                net_required = row['tipo_comprobante_codigo'] in {1, 2, 3, 51, 52, 53, 63}
                matches = (arca_iva == row['iva_total_centavos'] and
                           canonical['total_centavos'] == row['total_centavos'] and
                           (not net_required or canonical['neto_gravado_centavos'] == row['neto_centavos']))
                state = 'CONCILIADO_ARCA_CALIM' if matches else 'DIFERENCIA_ARCA_CALIM'
                counters['conciliadas' if matches else 'diferencias'] += 1
                target_id = canonical['id']
                conn.execute('''UPDATE compras_facturas SET calim_raw_ingesta_id=?, calim_hash_archivo=?,
                    calim_neto_centavos=?, calim_iva_total_centavos=?, calim_total_centavos=?, calim_estado=?,
                    status=?, updated_at=datetime('now','localtime') WHERE id=?''',
                    (raw_id, data['hash_sha256'], row['neto_centavos'], row['iva_total_centavos'],
                     row['total_centavos'], state, state, target_id))
                # Conserva filas viejas para auditoría, pero las excluye de reportes corrientes.
                for legacy in candidates:
                    if legacy['id'] != target_id and legacy['raw_ingesta_id'] is None:
                        conn.execute("UPDATE compras_facturas SET status='DUPLICADO_LEGACY_CALIM', calim_estado='DUPLICADO_LEGACY_CALIM' WHERE id=?", (legacy['id'],))
            else:
                target = candidates[0] if candidates else None
                counters['solo_calim'] += 1
                if target:
                    conn.execute('''UPDATE compras_facturas SET fecha=?, cuit_proveedor=?, proveedor=?, tipo_comprobante=?,
                        tipo_comprobante_codigo=?, neto=?, iva21=?, total=?, signo=?, calim_raw_ingesta_id=?, calim_hash_archivo=?, calim_neto_centavos=?,
                        calim_iva_total_centavos=?, calim_total_centavos=?, calim_estado='SOLO_CALIM',
                        status='SOLO_CALIM', hash_archivo=?, updated_at=datetime('now','localtime') WHERE id=?''',
                        (row['fecha'], row['cuit_proveedor'], row['proveedor'], row['tipo_comprobante'],
                         row['tipo_comprobante_codigo'], row['neto_centavos']/100,
                         row['iva_total_centavos']/100, row['total_centavos']/100, row['signo'], raw_id,
                         data['hash_sha256'], row['neto_centavos'], row['iva_total_centavos'], row['total_centavos'],
                         data['hash_sha256'], target['id']))
                else:
                    conn.execute('''INSERT INTO compras_facturas
                        (fecha,tipo_comprobante,tipo_comprobante_codigo,signo,punto_venta,numero_comprobante,
                         cuit_proveedor,proveedor,neto,iva21,total,tipo_operacion,status,origen,hash_archivo,
                         calim_raw_ingesta_id,calim_hash_archivo,calim_neto_centavos,calim_iva_total_centavos,
                         calim_total_centavos,calim_estado,numero_linea,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,'COMPRA','SOLO_CALIM','CALIM_XLSX',?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)''',
                        (row['fecha'], row['tipo_comprobante'], row['tipo_comprobante_codigo'], row['signo'],
                         row['punto_venta'], row['numero_comprobante'], row['cuit_proveedor'], row['proveedor'],
                         row['neto_centavos']/100, row['iva_total_centavos']/100, row['total_centavos']/100,
                         data['hash_sha256'], raw_id, data['hash_sha256'], row['neto_centavos'],
                         row['iva_total_centavos'], row['total_centavos'], 'SOLO_CALIM', row['numero_linea']))
        conn.execute('''INSERT INTO compras_calim_ingestas
            (raw_ingesta_id,nombre_archivo,hash_archivo,path_archivo,filas,fecha_min,fecha_max,conciliadas,diferencias,solo_calim)
            VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(raw_ingesta_id) DO UPDATE SET
              path_archivo=excluded.path_archivo, filas=excluded.filas, fecha_min=excluded.fecha_min,
              fecha_max=excluded.fecha_max, conciliadas=excluded.conciliadas,
              diferencias=excluded.diferencias, solo_calim=excluded.solo_calim, updated_at=CURRENT_TIMESTAMP''',
            (raw_id,data['nombre_archivo'],data['hash_sha256'],data['path_archivo'],len(data['filas']),
             data['fecha_min'],data['fecha_max'],counters['conciliadas'],counters['diferencias'],counters['solo_calim']))
        conn.execute("INSERT INTO core_staging_logs(staging_id,resultado,detalles) VALUES (?,'OK',?)",
                     (raw_id, json.dumps(counters, ensure_ascii=False)))
        conn.commit()
        return {'raw_ingesta_id': raw_id, 'filas': len(data['filas']), **counters}
    except Exception:
        conn.rollback()
        logger.exception('Error en ingesta ELT de CALIM')
        raise
    finally:
        conn.close()


def update_calim_path(hash_archivo, new_path):
    safe = sanitize_path_db(new_path)
    conn = get_db_connection()
    try:
        conn.execute('UPDATE compras_calim_ingestas SET path_archivo=? WHERE hash_archivo=?', (safe, hash_archivo))
        conn.commit()
    finally:
        conn.close()


def save_factura(f: dict):
    """Guarda una factura con volcado híbrido v4.5. Retorna el ID del registro."""
    conn = get_db_connection()
    try:
        columnas_duras = {
            'fecha', 'tipo_comprobante', 'punto_venta', 'numero_comprobante',
            'cuit_proveedor', 'proveedor', 'neto', 'iva21', 'iva105',
            'iva27', 'exento', 'percepcion_iva', 'imp_internos', 'total', 
            'moneda', 'tipo_operacion', 'status', 'tiene_foto', 
            'path_archivo', 'hash_archivo', 'origen'
        }
        metadata = {k: v for k, v in f.items() if k not in columnas_duras}
        
        # Sanitizar ruta
        path_limpio = sanitize_path_db(f.get('path_archivo'))

        cursor = conn.execute('''
            INSERT OR IGNORE INTO compras_facturas (
                fecha, tipo_comprobante, punto_venta, numero_comprobante,
                cuit_proveedor, proveedor, neto, iva21, iva105,
                iva27, exento, percepcion_iva, imp_internos, total, moneda,
                tipo_operacion, status, tiene_foto, path_archivo, hash_archivo, origen, 
                meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f.get('fecha'), f.get('tipo_comprobante'), f.get('punto_venta'),
            f.get('numero_comprobante'), f.get('cuit_proveedor'), f.get('proveedor'),
            f.get('neto', 0), f.get('iva21', 0), f.get('iva105', 0),
            f.get('iva27', 0), f.get('exento', 0), f.get('percepcion_iva', 0), 
            f.get('imp_internos', 0), f.get('total', 0), f.get('moneda', 'ARS'),
            f.get('tipo_operacion', 'COMPRA'), f.get('status', 'SOLO_AFIP'),
            f.get('tiene_foto', 0), path_limpio, f.get('hash_archivo'), f.get('origen', 'MANUAL'),
            json.dumps(metadata, ensure_ascii=False, default=str)
        ))
        
        last_id = cursor.lastrowid
        
        if last_id == 0 or last_id is None:
            res = conn.execute('''
                SELECT id FROM compras_facturas 
                WHERE cuit_proveedor = ? AND punto_venta = ? AND numero_comprobante = ? AND tipo_comprobante = ?
            ''', (f.get('cuit_proveedor'), f.get('punto_venta'), f.get('numero_comprobante'), f.get('tipo_comprobante'))).fetchone()
            if res: last_id = res['id']

        conn.commit()
        return last_id
    except Exception as e:
        logger.warning(f"Error guardando factura: {e}")
        return None
    finally:
        conn.close()


def upsert_proveedor(cuit, nombre):
    """Registra o actualiza un proveedor en el maestro."""
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO compras_proveedores (cuit, nombre_fantasia) VALUES (?, ?)
            ON CONFLICT(cuit) DO UPDATE SET nombre_fantasia = excluded.nombre_fantasia
        ''', (cuit, nombre))
        conn.commit()
    finally:
        conn.close()


def buscar_compras_proveedores_fuzzy(termino):
    """Búsqueda difusa de compras_proveedores por nombre o CUIT."""
    import difflib
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT cuit, nombre_fantasia FROM compras_proveedores").fetchall()
        compras_proveedores = [dict(r) for r in rows]
        
        # Primero Intentamos Match Exacto por CUIT
        exacto = [p for p in compras_proveedores if p['cuit'] == termino or termino in p['cuit']]
        if exacto: return exacto
        
        # Búsqueda Difusa por Nombre
        nombres = [p['nombre_fantasia'] for p in compras_proveedores]
        matches = difflib.get_close_matches(termino.upper(), [n.upper() for n in nombres], n=5, cutoff=0.4)
        
        resultado = []
        for m in matches:
            for p in compras_proveedores:
                if p['nombre_fantasia'].upper() == m:
                    resultado.append(p)
        return resultado
    finally:
        conn.close()


def archivar_evidencia_visual(factura_id, source_path, cuit, nombre_proveedor, fecha, punto_venta, numero):
    """
    Renombra y mueve archivo a: archivos_compras/NombreProveedor/YYYY/MM/
    Nombre: YYYYMMDD_NombreProveedor_PV-NUM.ext
    """
    import shutil
    from datetime import datetime
    
    try:
        ext = os.path.splitext(source_path)[1].lower()
        # Reparar fecha si viene con guiones o barras
        try:
            fecha_dt = datetime.strptime(fecha, '%Y-%m-%d')
        except:
            fecha_dt = datetime.strptime(fecha, '%d/%m/%Y')

        # Estructura v4.6: modulo_compras/archivos_compras/PROVEEDOR/YYYY/MM/
        nuevo_nombre = f"{fecha_dt.strftime('%Y%m%d')}_{nombre_proveedor.replace(' ', '_')}_{punto_venta}-{numero}{ext}"
        
        rel_path_from_archive = os.path.join(nombre_proveedor.upper().replace(' ', '_'), 
                                           fecha_dt.strftime('%Y'), 
                                           fecha_dt.strftime('%m'))
        
        target_dir = os.path.join(BASE_DIR, "modulo_compras", "archivos_compras", rel_path_from_archive)
        os.makedirs(target_dir, exist_ok=True)
        
        target_path = os.path.join(target_dir, nuevo_nombre)
        shutil.copy2(source_path, target_path)
        
        # Guardar solo la ruta relativa DESDE archivos_compras para el servidor estático
        final_rel_path = os.path.join(rel_path_from_archive, nuevo_nombre)
        
        # Actualizar DB
        conn = get_db_connection()
        conn.execute("UPDATE compras_facturas SET tiene_foto = 1, path_archivo = ?, status = 'ARCHIVADO' WHERE id = ?", (final_rel_path, factura_id))
        conn.commit()
        conn.close()
        
        return True, final_rel_path
    except Exception as e:
        logger.error(f"Error archivando evidencia: {e}")
        return False, str(e)


def save_libro_iva(data: dict):
    """Persistencia del Libro IVA v4.5."""
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO compras_libroiva (
                periodo, debito_fiscal, credito_fiscal, saldo_tecnico, 
                saldo_libre_disponibilidad, path_archivo, hash_archivo, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(periodo) DO UPDATE SET
                debito_fiscal = excluded.debito_fiscal,
                credito_fiscal = excluded.credito_fiscal,
                saldo_tecnico = excluded.saldo_tecnico,
                saldo_libre_disponibilidad = excluded.saldo_libre_disponibilidad,
                path_archivo = excluded.path_archivo,
                hash_archivo = excluded.hash_archivo,
                meta_json = excluded.meta_json
        ''', (
            data.get('periodo'), data.get('debito_fiscal', 0),
            data.get('credito_fiscal', 0), data.get('saldo_tecnico', 0),
            data.get('saldo_libre_disponibilidad', 0), 
            data.get('path_archivo'), data.get('hash_archivo'),
            json.dumps(data.get('metadata', {}), ensure_ascii=False, default=str)
        ))
        conn.commit()
        return True
    except Exception as e:
        logger.warning(f"Error guardando Libro IVA: {e}")
        return False
    finally:
        conn.close()


def get_all_compras_facturas(anio=None, mes=None):
    """Retorna compras_facturas de compras con soporte de filtrado cronológico v4.7."""
    conn = get_db_connection()
    try:
        query = '''
            SELECT id, fecha, tipo_comprobante, punto_venta, numero_comprobante, 
                   proveedor, cuit_proveedor, neto, iva21, total, status, 
                   tiene_foto, path_archivo, origen, meta_json
            FROM compras_facturas 
            WHERE tipo_operacion = 'COMPRA'
              AND COALESCE(status, '') <> 'DUPLICADO_LEGACY_CALIM'
        '''
        params = []
        
        if anio and mes:
            # Formato YYYY-MM
            query += " AND (fecha LIKE ?)"
            params.append(f"{anio}-{mes}%")
        elif anio:
            query += " AND (fecha LIKE ?)"
            params.append(f"{anio}%")

        query += " ORDER BY fecha DESC"
        
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_record_path(record_id, new_path, table="compras_facturas"):
    """Actualiza la ruta física del archivo tras el archivado legal v4.5."""
    conn = get_db_connection()
    try:
        if table not in ["compras_facturas", "compras_libroiva"]:
            raise ValueError(f"Tabla no permitida: {table}")
        if table == "compras_facturas":
            conn.execute(f"UPDATE {table} SET path_archivo = ?, tiene_foto = 1, status = 'ARCHIVADO' WHERE id = ?", (new_path, record_id))
        else:
            conn.execute(f"UPDATE {table} SET path_archivo = ? WHERE id = ?", (new_path, record_id))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error actualizando path en {table}: {e}")
    finally:
        conn.close()


def get_reporte_discrepancias():
    """Retorna compras_facturas cruzadas que están en AFIP/Manual pero no en CALIM."""
    conn = get_db_connection()
    try:
        rows = conn.execute('''
            SELECT id, numero_comprobante, proveedor, fecha, total, origen, status 
            FROM compras_facturas 
            WHERE tipo_operacion = 'COMPRA' AND status = 'SOLO_AFIP'
            ORDER BY fecha DESC
        ''').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_compras_facturas_sin_archivo():
    """Retorna compras_facturas importadas que aún no tienen evidencia visual vinculada."""
    conn = get_db_connection()
    try:
        rows = conn.execute('''
            SELECT id, numero_comprobante, proveedor, fecha, total, origen 
            FROM compras_facturas 
            WHERE (tiene_foto = 0 OR path_archivo IS NULL)
              AND COALESCE(status, '') <> 'DUPLICADO_LEGACY_CALIM'
            ORDER BY fecha DESC
        ''').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_factura_status(factura_id, status_nuevo):
    """Actualiza solo el status de una factura."""
    conn = get_db_connection()
    try:
        conn.execute("UPDATE compras_facturas SET status = ? WHERE id = ?", (status_nuevo, factura_id))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error actualizando status en factura {factura_id}: {e}")
    finally:
        conn.close()


def get_factura_by_id(factura_id):
    """Retorna una factura completa por su ID."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM compras_facturas WHERE id = ?", (factura_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def smart_search_invoice(query):
    """Busca compras_facturas por coincidencia en número o en metadatos (CAE) v4.9."""
    conn = get_db_connection()
    try:
        clean_q = query.strip().replace('-', '').lstrip('0')
        raw_q = query.strip()
        if not raw_q: return []
        
        search_pattern = f"%{clean_q}%" if clean_q else f"%{raw_q}%"
        text_pattern = f"%{raw_q}%"
        
        rows = conn.execute("""
            SELECT id, proveedor, cuit_proveedor, fecha, punto_venta, numero_comprobante, total, origen 
            FROM compras_facturas 
            WHERE tipo_operacion = 'COMPRA' 
              AND COALESCE(status, '') <> 'DUPLICADO_LEGACY_CALIM'
              AND (
                  numero_comprobante LIKE ? OR 
                  (punto_venta || numero_comprobante) LIKE ? OR
                  (CAST(CAST(numero_comprobante AS INTEGER) AS TEXT)) LIKE ? OR
                  proveedor LIKE ? OR
                  cuit_proveedor LIKE ? OR
                  meta_json LIKE ?
              )
            ORDER BY fecha DESC LIMIT 5
        """, (search_pattern, search_pattern, search_pattern, text_pattern, text_pattern, text_pattern)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_factura_fields(factura_id, fields: dict):
    """Actualiza campos arbitrarios de una factura (punto_venta, numero_comprobante, etc)."""
    conn = get_db_connection()
    try:
        query = "UPDATE compras_facturas SET "
        sets = [f"{k} = ?" for k in fields.keys()]
        query += ", ".join(sets)
        query += " WHERE id = ?"
        
        params = list(fields.values()) + [factura_id]
        conn.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error actualizando campos en factura {factura_id}: {e}")
        return False
    finally:
        conn.close()


def get_resumen_facturacion(anio=None):
    """Estadísticas de compras_facturas v4.5."""
    conn = get_db_connection()
    params = [f"{anio}%"] if anio else []
    where = " WHERE fecha LIKE ?" if anio else ""
    cur = conn.cursor()
    active = "COALESCE(status, '') <> 'DUPLICADO_LEGACY_CALIM'"
    count = cur.execute(f"SELECT COUNT(*) FROM compras_facturas {where} {'AND' if anio else 'WHERE'} {active}", params).fetchone()[0] or 0
    ventas = cur.execute(f"SELECT SUM(total) FROM compras_facturas {where} {'AND' if anio else 'WHERE'} tipo_operacion = 'VENTA' AND {active}", params).fetchone()[0] or 0.0
    compras = cur.execute(f"SELECT SUM(total) FROM compras_facturas {where} {'AND' if anio else 'WHERE'} tipo_operacion = 'COMPRA' AND {active}", params).fetchone()[0] or 0.0
    conn.close()
    return {"total_count": count, "monto_ventas": ventas, "monto_compras": compras}


def buscar_compras_facturas(termino):
    """Busca en compras_facturas v4.5."""
    conn = get_db_connection()
    cur = conn.cursor()
    q = f"%{termino}%"
    rows = cur.execute("""
        SELECT * FROM compras_facturas 
        WHERE COALESCE(status, '') <> 'DUPLICADO_LEGACY_CALIM'
          AND (numero_comprobante LIKE ? OR proveedor LIKE ? OR cuit_proveedor LIKE ?)
        ORDER BY fecha DESC LIMIT 20
    """, (q, q, q)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def registrar_impuesto(data: dict):
    """API Interna para registrar IVA v4.5."""
    conn = get_db_connection()
    try:
        metadata = {k: v for k, v in data.items()
                    if k not in {'modulo', 'fuente', 'fecha', 'neto',
                                 'iva105', 'iva21', 'descripcion', 'extern_id',
                                 'hash_archivo'}}
        conn.execute('''
            INSERT INTO compras_iva_desglosado (
                modulo_origen, fuente, fecha, neto, iva105, iva21,
                descripcion, extern_id, hash_archivo, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('modulo'), data.get('fuente'), data.get('fecha'),
            data.get('neto', 0), data.get('iva105', 0), data.get('iva21', 0),
            data.get('descripcion'), data.get('extern_id'), data.get('hash_archivo'),
            json.dumps(metadata, ensure_ascii=False, default=str)
        ))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error registrando IVA: {e}")
    finally:
        conn.close()
