import sqlite3
import json
import os
import logging

# STORAGE COMPRAS - v4.0 GOLDEN MASTER 🧾🧱🧠⚖️
# Diseño Híbrido: Columnas Duras + metadata_cruda (JSON) + path_archivo

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db_compras():
    """Crea las tablas del dominio Compras con diseño híbrido v4.0."""
    conn = get_db_connection()
    print("🧱 [COMPRAS] Construyendo tablas Golden Master (Híbrido)...")

    # ── Tabla Maestra de Facturas ──────────────────────────────────
    # Unificada para ARCA (AFIP) y CALIM
    conn.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha           TEXT,
            tipo_comprobante TEXT,
            punto_venta     TEXT,
            numero_completo TEXT,
            cuit_proveedor  TEXT,
            proveedor       TEXT,
            neto_gravado    REAL DEFAULT 0,
            iva_21          REAL DEFAULT 0,
            iva_105         REAL DEFAULT 0,
            iva_27          REAL DEFAULT 0,
            percepciones    REAL DEFAULT 0,
            imp_internos    REAL DEFAULT 0,
            monto_total     REAL DEFAULT 0,
            moneda          TEXT DEFAULT 'ARS',
            tipo_operacion  TEXT DEFAULT 'COMPRA', -- COMPRA o VENTA
            status          TEXT DEFAULT 'SOLO_AFIP', -- SOLO_AFIP, CONCILIADO_CALIM, ARCHIVADO
            path_archivo    TEXT, -- [v4.0]
            hash_archivo    TEXT, -- [v4.0] NO UNIQUE: La idempotencia es por Fila
            origen          TEXT DEFAULT 'MANUAL',
            metadata_cruda  TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(cuit_proveedor, punto_venta, numero_completo, tipo_comprobante)
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
            path_archivo    TEXT, -- [NUEVO v4.0]
            hash_archivo    TEXT UNIQUE,
            metadata_cruda  TEXT DEFAULT '{}',
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
            neto_gravado    REAL DEFAULT 0,
            iva_105         REAL DEFAULT 0,
            iva_21          REAL DEFAULT 0,
            descripcion     TEXT,
            extern_id       INTEGER,
            hash_archivo    TEXT,
            metadata_cruda  TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


def save_factura(f: dict):
    """Guarda una factura con volcado híbrido v4.0."""
    conn = get_db_connection()
    try:
        columnas_duras = {
            'fecha', 'tipo_comprobante', 'punto_venta', 'numero_completo',
            'cuit_proveedor', 'proveedor', 'neto_gravado', 'iva_21', 'iva_105',
            'iva_27', 'percepciones', 'imp_internos', 'monto_total', 'moneda',
            'tipo_operacion', 'status', 'path_archivo', 'hash_archivo', 'origen'
        }
        metadata = {k: v for k, v in f.items() if k not in columnas_duras}

        conn.execute('''
            INSERT OR IGNORE INTO facturas (
                fecha, tipo_comprobante, punto_venta, numero_completo,
                cuit_proveedor, proveedor, neto_gravado, iva_21, iva_105,
                iva_27, percepciones, imp_internos, monto_total, moneda,
                tipo_operacion, status, path_archivo, hash_archivo, origen, 
                metadata_cruda
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f.get('fecha'), f.get('tipo_comprobante'), f.get('punto_venta'),
            f.get('numero_completo'), f.get('cuit_proveedor'), f.get('proveedor'),
            f.get('neto_gravado', 0), f.get('iva_21', 0), f.get('iva_105', 0),
            f.get('iva_27', 0), f.get('percepciones', 0), f.get('imp_internos', 0),
            f.get('monto_total', 0), f.get('moneda', 'ARS'),
            f.get('tipo_operacion', 'COMPRA'), f.get('status', 'SOLO_AFIP'),
            f.get('path_archivo'), f.get('hash_archivo'), f.get('origen', 'MANUAL'),
            json.dumps(metadata, ensure_ascii=False, default=str)
        ))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error guardando factura: {e}")
    finally:
        conn.close()


def save_libro_iva(data: dict):
    """Persistencia del Libro IVA v4.0 (Patrón Repositorio)."""
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO libroiva (
                periodo, debito_fiscal, credito_fiscal, saldo_tecnico, 
                saldo_libre_disponibilidad, path_archivo, hash_archivo, metadata_cruda
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(periodo) DO UPDATE SET
                debito_fiscal = excluded.debito_fiscal,
                credito_fiscal = excluded.credito_fiscal,
                saldo_tecnico = excluded.saldo_tecnico,
                saldo_libre_disponibilidad = excluded.saldo_libre_disponibilidad,
                path_archivo = excluded.path_archivo,
                hash_archivo = excluded.hash_archivo,
                metadata_cruda = excluded.metadata_cruda
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


def update_record_path(record_id, new_path, table="facturas"):
    """Actualiza la ruta física del archivo tras el archivado legal v4.0."""
    conn = get_db_connection()
    try:
        if table not in ["facturas", "libroiva"]:
            raise ValueError(f"Tabla no permitida: {table}")
        conn.execute(f"UPDATE {table} SET path_archivo = ? WHERE id = ?", (new_path, record_id))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error actualizando path en {table}: {e}")
    finally:
        conn.close()


def get_resumen_facturacion(anio=None):
    """Estadísticas de facturas v4.0."""
    conn = get_db_connection()
    params = [f"{anio}%"] if anio else []
    where = " WHERE fecha LIKE ?" if anio else ""
    cur = conn.cursor()
    count = cur.execute(f"SELECT COUNT(*) FROM facturas {where}", params).fetchone()[0] or 0
    ventas = cur.execute(f"SELECT SUM(monto_total) FROM facturas {where} {'AND' if anio else 'WHERE'} tipo_operacion = 'VENTA'", params).fetchone()[0] or 0.0
    compras = cur.execute(f"SELECT SUM(monto_total) FROM facturas {where} {'AND' if anio else 'WHERE'} tipo_operacion = 'COMPRA'", params).fetchone()[0] or 0.0
    conn.close()
    return {"total_count": count, "monto_ventas": ventas, "monto_compras": compras}


def buscar_facturas(termino):
    """Busca en facturas v4.0."""
    conn = get_db_connection()
    cur = conn.cursor()
    q = f"%{termino}%"
    rows = cur.execute("""
        SELECT * FROM facturas 
        WHERE numero_completo LIKE ? OR proveedor LIKE ? OR cuit_proveedor LIKE ?
        ORDER BY fecha DESC LIMIT 20
    """, (q, q, q)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def registrar_impuesto(data: dict):
    """API Interna para registrar IVA v4.0."""
    conn = get_db_connection()
    try:
        metadata = {k: v for k, v in data.items()
                    if k not in {'modulo', 'fuente', 'fecha', 'neto_gravado',
                                 'iva_105', 'iva_21', 'descripcion', 'extern_id',
                                 'hash_archivo'}}
        conn.execute('''
            INSERT INTO iva_desglosado (
                modulo_origen, fuente, fecha, neto_gravado, iva_105, iva_21,
                descripcion, extern_id, hash_archivo, metadata_cruda
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('modulo'), data.get('fuente'), data.get('fecha'),
            data.get('neto_gravado', 0), data.get('iva_105', 0), data.get('iva_21', 0),
            data.get('descripcion'), data.get('extern_id'), data.get('hash_archivo'),
            json.dumps(metadata, ensure_ascii=False, default=str)
        ))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error registrando IVA: {e}")
    finally:
        conn.close()
