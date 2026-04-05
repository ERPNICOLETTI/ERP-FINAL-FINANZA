import sqlite3
import os
import logging

# CORE SISTEMA - ORQUESTADOR DE BASE DE DATOS Y BÚSQUEDA GLOBAL 🧠🏗️⚖️
# Coordina el esquema modular y mantiene el índice FTS5 + metadata_cruda.

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def initialize_all():
    """Llamada central para inicializar toda la estructura del ERP."""
    from modulo_tarjetas.storage_tarjetas import init_db_tarjetas
    from modulo_compras.storage_compras import init_db_compras
    from modulo_bancos.storage_bancos import init_db_bancos

    print("🧠 [CORE] Iniciando construcción modular de la base de datos...")

    # 1. Cada módulo construye sus propias tablas
    init_db_tarjetas()
    init_db_compras()
    init_db_bancos()

    # 2. El Core construye la infraestructura de búsqueda
    setup_search_index()

    # 3. Registro de auditoría de ingestas (Anti-duplicados)
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS core_registro_ingestas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo          TEXT,
            tipo            TEXT,
            nombre_fuente   TEXT,
            hash_sha256     TEXT UNIQUE,
            fecha_proceso   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

    print("✨ [CORE] Base de datos lista y orquestada (Diseño Híbrido).")


def setup_search_index():
    """Prepara la tabla virtual FTS5 para búsquedas inteligentes.
    Indexa columnas duras + contenido de metadata_cruda."""
    conn = get_db_connection()
    try:
        conn.execute("DROP TABLE IF EXISTS search_index")
        conn.execute("""
            CREATE VIRTUAL TABLE search_index USING fts5(
                source,
                record_id,
                nombre,
                monto,
                fecha,
                extra,
                metadata_texto
            )
        """)
        conn.commit()
    finally:
        conn.close()


def update_search_index():
    """Regenera el índice de búsqueda cruzando todos los módulos.
    Incluye metadata_cruda en la columna metadata_texto para búsqueda full-text."""
    conn = get_db_connection()
    try:
        print("🔍 [CORE] Actualizando índice de búsqueda global (con metadata)...")
        conn.execute("DELETE FROM search_index")
        conn.execute("""
            INSERT INTO search_index(source, record_id, nombre, monto, fecha, extra, metadata_texto)

            SELECT 'Factura', id,
                   COALESCE(punto_venta, '') || '-' || COALESCE(numero_comprobante, '') || ' ' || COALESCE(proveedor, ''),
                   monto_total, fecha,
                   COALESCE(tipo_comprobante, '') || ' CUIT:' || COALESCE(cuit_proveedor, ''),
                   COALESCE(metadata_cruda, '')
            FROM facturas

            UNION ALL

            SELECT 'Liquidacion', id,
                   COALESCE(fuente, '') || ' ' || COALESCE(marca, ''),
                   total_bruto, fecha_liquidacion,
                   'Periodo: ' || COALESCE(periodo, '') || ' Neto: ' || COALESCE(CAST(total_neto AS TEXT), ''),
                   COALESCE(metadata_cruda, '')
            FROM liquidaciones_tarjetas

            UNION ALL

            SELECT 'Cupon', id,
                   COALESCE(fuente, '') || ' Lote:' || COALESCE(lote, '') || ' Cupon:' || COALESCE(cupon, ''),
                   monto_bruto, fecha_compra,
                   COALESCE(marca, ''),
                   COALESCE(metadata_cruda, '')
            FROM payway_records

            UNION ALL

            SELECT 'Banco', id,
                   COALESCE(banco, '') || ' ' || COALESCE(descripcion, ''),
                   importe, fecha,
                   COALESCE(cuenta, '') || ' ' || COALESCE(tipo_movimiento, ''),
                   COALESCE(metadata_cruda, '')
            FROM bancos_movimientos
        """)
        conn.commit()
        print("✅ [CORE] Índice FTS5 actualizado con metadata cruda.")
    except Exception as e:
        logger.warning(f"Error actualizando search_index: {e}")
    finally:
        conn.close()
def search_360(term):
    """Buscador global usando FTS5 (Movido de erp_master.py)."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        rows = cur.execute("SELECT * FROM search_index WHERE search_index MATCH ? ORDER BY rank LIMIT 15", (term,)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Error en búsqueda FTS5: {e}")
        return []
    finally:
        conn.close()
