import sqlite3
import os

# CORE SISTEMA - ORQUESTADOR DE BASE DE DATOS Y BÚSQUEDA GLOBAL 🧠🏗️⚖️
# Este archivo coordina el esquema modular y mantiene el índice FTS5.

# Determinamos la raíz del proyecto para una DB única
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')

def get_db_connection():
    return sqlite3.connect(DB_PATH, timeout=30.0)

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
    
    # 3. El Core construye el registro de auditoría de ingestas (Anti-duplicados)
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS core_registro_ingestas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo TEXT,
            tipo TEXT,              -- FILE, TEXT
            nombre_fuente TEXT,     -- filename or description
            hash_sha256 TEXT UNIQUE,
            fecha_proceso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

    print("✨ [CORE] Base de datos lista y orquestada.")

def setup_search_index():
    """Prepara la tabla virtual FTS5 para búsquedas inteligentes."""
    conn = get_db_connection()
    try:
        conn.execute("DROP TABLE IF EXISTS search_index")
        conn.execute("CREATE VIRTUAL TABLE search_index USING fts5(source, id, name, amount, date, extra)")
        conn.commit()
    finally:
        conn.close()

def update_search_index():
    """Regenera el índice de búsqueda cruzando todos los módulos."""
    conn = get_db_connection()
    try:
        print("🔍 [CORE] Actualizando índice de búsqueda global...")
        conn.execute("DELETE FROM search_index")
        conn.execute("""
            INSERT INTO search_index(source, id, name, amount, date, extra)
            SELECT 'Tarjeta_Payway', id, cupon || ' Lote ' || lote, monto_bruto, fecha_compra, marca FROM payway_records
            UNION ALL
            SELECT 'Factura', id, numero_completo || ' ' || proveedor, monto_total, fecha_emision, status FROM facturas
            UNION ALL
            SELECT 'Liquidacion', id, fuente || ' ' || marca, total_bruto, fecha_liquidacion, 'Periodo: ' || periodo FROM liquidaciones_tarjetas
            UNION ALL
            SELECT 'Banco', id, banco || ' ' || descripcion, importe, fecha, cuenta FROM bancos_movimientos
        """)
        conn.commit()
    finally:
        conn.close()

# Las funciones persistir_* han sido delegadas a sus respectivos módulos
# modulo_tarjetas.storage_tarjetas
# modulo_compras.storage_compras
# modulo_bancos.storage_bancos
