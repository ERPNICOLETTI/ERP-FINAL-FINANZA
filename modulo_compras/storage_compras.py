import sqlite3
import json
import os
import logging

# STORAGE COMPRAS - v4.5 GOLDEN MASTER 🧾🧱🧠⚖️
# Diseño Híbrido: Columnas Duras + meta_json (JSON) + path_archivo

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db_compras():
    """Crea las tablas del dominio Compras con diseño híbrido v4.5."""
    conn = get_db_connection()
    print("🧱 [COMPRAS] Construyendo tablas Golden Master v4.5 (Híbrido)...")

    # ── Tabla de Proveedores (Maestro) ──────────────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS proveedores (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cuit            TEXT UNIQUE,
            nombre_fantasia TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Tabla Maestra de Facturas ──────────────────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
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
        CREATE TABLE IF NOT EXISTS libroiva (
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
        CREATE TABLE IF NOT EXISTS iva_desglosado (
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

    conn.commit()
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

        cursor = conn.execute('''
            INSERT OR IGNORE INTO facturas (
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
            f.get('tiene_foto', 0), f.get('path_archivo'), f.get('hash_archivo'), f.get('origen', 'MANUAL'),
            json.dumps(metadata, ensure_ascii=False, default=str)
        ))
        
        last_id = cursor.lastrowid
        
        if last_id == 0 or last_id is None:
            res = conn.execute('''
                SELECT id FROM facturas 
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
            INSERT INTO proveedores (cuit, nombre_fantasia) VALUES (?, ?)
            ON CONFLICT(cuit) DO UPDATE SET nombre_fantasia = excluded.nombre_fantasia
        ''', (cuit, nombre))
        conn.commit()
    finally:
        conn.close()


def buscar_proveedores_fuzzy(termino):
    """Búsqueda difusa de proveedores por nombre o CUIT."""
    import difflib
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT cuit, nombre_fantasia FROM proveedores").fetchall()
        proveedores = [dict(r) for r in rows]
        
        # Primero Intentamos Match Exacto por CUIT
        exacto = [p for p in proveedores if p['cuit'] == termino or termino in p['cuit']]
        if exacto: return exacto
        
        # Búsqueda Difusa por Nombre
        nombres = [p['nombre_fantasia'] for p in proveedores]
        matches = difflib.get_close_matches(termino.upper(), [n.upper() for n in nombres], n=5, cutoff=0.4)
        
        resultado = []
        for m in matches:
            for p in proveedores:
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
        conn.execute("UPDATE facturas SET tiene_foto = 1, path_archivo = ?, status = 'ARCHIVADO' WHERE id = ?", (final_rel_path, factura_id))
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
            INSERT INTO libroiva (
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


def get_all_facturas():
    """Retorna todas las facturas de compras registradas."""
    conn = get_db_connection()
    try:
        rows = conn.execute('''
            SELECT id, fecha, tipo_comprobante, punto_venta, numero_comprobante, 
                   proveedor, cuit_proveedor, neto, iva21, total, status, 
                   tiene_foto, path_archivo, origen, meta_json
            FROM facturas 
            WHERE tipo_operacion = 'COMPRA'
            ORDER BY fecha DESC
        ''').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_record_path(record_id, new_path, table="facturas"):
    """Actualiza la ruta física del archivo tras el archivado legal v4.5."""
    conn = get_db_connection()
    try:
        if table not in ["facturas", "libroiva"]:
            raise ValueError(f"Tabla no permitida: {table}")
        if table == "facturas":
            conn.execute(f"UPDATE {table} SET path_archivo = ?, tiene_foto = 1, status = 'ARCHIVADO' WHERE id = ?", (new_path, record_id))
        else:
            conn.execute(f"UPDATE {table} SET path_archivo = ? WHERE id = ?", (new_path, record_id))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error actualizando path en {table}: {e}")
    finally:
        conn.close()


def get_reporte_discrepancias():
    """Retorna facturas cruzadas que están en AFIP/Manual pero no en CALIM."""
    conn = get_db_connection()
    try:
        rows = conn.execute('''
            SELECT id, numero_comprobante, proveedor, fecha, total, origen, status 
            FROM facturas 
            WHERE tipo_operacion = 'COMPRA' AND status = 'SOLO_AFIP'
            ORDER BY fecha DESC
        ''').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_facturas_sin_archivo():
    """Retorna facturas importadas que aún no tienen evidencia visual vinculada."""
    conn = get_db_connection()
    try:
        rows = conn.execute('''
            SELECT id, numero_comprobante, proveedor, fecha, total, origen 
            FROM facturas 
            WHERE tiene_foto = 0 OR path_archivo IS NULL
            ORDER BY fecha DESC
        ''').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_factura_status(factura_id, status_nuevo):
    """Actualiza solo el status de una factura."""
    conn = get_db_connection()
    try:
        conn.execute("UPDATE facturas SET status = ? WHERE id = ?", (status_nuevo, factura_id))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error actualizando status en factura {factura_id}: {e}")
    finally:
        conn.close()


def update_factura_fields(factura_id, fields: dict):
    """Actualiza campos arbitrarios de una factura (punto_venta, numero_comprobante, etc)."""
    conn = get_db_connection()
    try:
        query = "UPDATE facturas SET "
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
    """Estadísticas de facturas v4.5."""
    conn = get_db_connection()
    params = [f"{anio}%"] if anio else []
    where = " WHERE fecha LIKE ?" if anio else ""
    cur = conn.cursor()
    count = cur.execute(f"SELECT COUNT(*) FROM facturas {where}", params).fetchone()[0] or 0
    ventas = cur.execute(f"SELECT SUM(total) FROM facturas {where} {'AND' if anio else 'WHERE'} tipo_operacion = 'VENTA'", params).fetchone()[0] or 0.0
    compras = cur.execute(f"SELECT SUM(total) FROM facturas {where} {'AND' if anio else 'WHERE'} tipo_operacion = 'COMPRA'", params).fetchone()[0] or 0.0
    conn.close()
    return {"total_count": count, "monto_ventas": ventas, "monto_compras": compras}


def buscar_facturas(termino):
    """Busca en facturas v4.5."""
    conn = get_db_connection()
    cur = conn.cursor()
    q = f"%{termino}%"
    rows = cur.execute("""
        SELECT * FROM facturas 
        WHERE numero_comprobante LIKE ? OR proveedor LIKE ? OR cuit_proveedor LIKE ?
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
            INSERT INTO iva_desglosado (
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
