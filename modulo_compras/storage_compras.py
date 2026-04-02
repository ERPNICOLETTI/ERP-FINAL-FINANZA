import sqlite3
import os

# STORAGE COMPRAS - Dueño de tablas de Facturación (ARCA, CALIM) 🧾🧱🧠

DB_PATH = 'erp_nicoletti.db'

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def init_db_compras():
    """Crea las tablas pertenecientes al dominio de Compras."""
    conn = get_db_connection()
    print("🧱 [COMPRAS] Inicializando tablas...")
    # Tabla Maestra de Facturas
    conn.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            numero_completo TEXT UNIQUE, 
            tipo_operacion TEXT, 
            tipo_comprobante TEXT, 
            proveedor TEXT, 
            fecha_emision TEXT, 
            neto_gravado REAL, 
            monto_iva REAL, 
            monto_total REAL, 
            esta_en_afip INTEGER DEFAULT 0, 
            esta_en_calim INTEGER DEFAULT 0, 
            status TEXT DEFAULT 'SOLO_AFIP', 
            path_archivo TEXT
        )
    ''')
    
    # Tabla Espejo CALIM
    conn.execute('''
        CREATE TABLE IF NOT EXISTS facturas_calim (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            numero_completo TEXT UNIQUE, 
            tipo_operacion TEXT, 
            tipo_comprobante TEXT, 
            proveedor TEXT, 
            fecha_emision TEXT, 
            neto_gravado REAL, 
            monto_iva REAL, 
            monto_total REAL, 
            estado_proceso TEXT DEFAULT 'PENDIENTE'
        )
    ''')

    # Libro IVA Consolidado
    conn.execute('''
        CREATE TABLE IF NOT EXISTS libroiva (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo TEXT UNIQUE,
            debito_fiscal REAL,
            credito_fiscal REAL,
            saldo_tecnico REAL,
            saldo_libre_disponibilidad REAL
        )
    ''')

    # DETALLE DE IVA (Especial para Comisiones e Intereses)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS iva_desglosado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo_origen TEXT,     -- TARJETAS, BANCOS
            fuente TEXT,            -- PAYWAY, CHUBUT, etc.
            fecha TEXT,
            neto_gravado REAL,
            iva_105 REAL,
            iva_21 REAL,
            descripcion TEXT,
            extern_id INTEGER       -- Referencia al ID original en el módulo
        )
    ''')
    conn.commit()
    conn.close()

def save_factura(f: dict):
    """Guarda una factura normalizada."""
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT OR IGNORE INTO facturas (
                numero_completo, tipo_operacion, tipo_comprobante, proveedor, 
                fecha_emision, neto_gravado, monto_iva, monto_total, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f.get('numero_completo'), f.get('tipo_operacion'), f.get('tipo_comprobante'),
            f.get('proveedor'), f.get('fecha_emision'), f.get('neto_gravado'),
            f.get('monto_iva'), f.get('monto_total'), f.get('status', 'SOLO_AFIP')
        ))
        conn.commit()
    finally:
        conn.close()

def registrar_impuesto(data: dict):
    """API Interna para registrar IVA desde cualquier módulo."""
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO iva_desglosado (
                modulo_origen, fuente, fecha, neto_gravado, iva_105, iva_21, descripcion, extern_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('modulo'), data.get('fuente'), data.get('fecha'),
            data.get('neto_gravado', 0), data.get('iva_105', 0), data.get('iva_21', 0),
            data.get('descripcion'), data.get('extern_id')
        ))
        conn.commit()
    finally:
        conn.close()
