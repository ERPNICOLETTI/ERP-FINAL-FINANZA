import sqlite3
import json
import os

# STORAGE TARJETAS - Dueño de tablas Payway, Naranja y Patagonia 💳🧱🧠

DB_PATH = 'erp_nicoletti.db'

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def init_db_tarjetas():
    """Crea las tablas pertenecientes al dominio de Tarjetas."""
    conn = get_db_connection()
    print("🧱 [TARJETAS] Inicializando tablas...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS payway_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            fecha_compra TEXT, 
            fecha_presentacion TEXT, 
            fecha_pago TEXT,
            lote TEXT, 
            cupon TEXT, 
            marca TEXT, 
            monto_bruto REAL, 
            estado TEXT DEFAULT 'PENDIENTE', 
            metadata TEXT,
            matching_tx_id INTEGER,
            UNIQUE(lote, cupon, fecha_compra, monto_bruto)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS liquidaciones_tarjetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fuente TEXT, -- Payway, Patagonia365, Naranja
            tipo TEXT,   -- DIARIA, MENSUAL
            fecha_liquidacion TEXT,
            periodo TEXT, -- YYYY-MM
            marca TEXT,
            establecimiento TEXT,
            total_bruto REAL,
            costo_arancel REAL,
            costo_financiero REAL,
            iva_21 REAL,
            iva_105 REAL,
            retenciones REAL,
            total_neto REAL,
            metadata TEXT,
            UNIQUE(fuente, fecha_liquidacion, periodo, marca, establecimiento, total_neto)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS liquidaciones_detalles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            liquidacion_id INTEGER,
            fecha TEXT,
            descripcion TEXT,
            monto_bruto REAL,
            arancel REAL,
            financiero REAL,
            iva REAL,
            retenciones REAL,
            monto_neto REAL,
            metadata_raw TEXT,
            FOREIGN KEY(liquidacion_id) REFERENCES liquidaciones_tarjetas(id)
        )
    ''')
    conn.commit()
    conn.close()

def save_liquidacion(data: dict):
    """Persistencia de cabecera de liquidación."""
    conn = get_db_connection()
    try:
        fuente = data.get('fuente', 'DESCONOCIDA').upper()
        tipo = data.get('tipo', 'DIARIA').upper()
        
        cursor = conn.execute('''
            INSERT OR IGNORE INTO liquidaciones_tarjetas (
                fuente, tipo, fecha_liquidacion, periodo, marca, establecimiento,
                total_bruto, costo_arancel, costo_financiero, iva_21, iva_105,
                retenciones, total_neto, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fuente, tipo, data.get('fecha_liquidacion'), data.get('periodo'), 
            data.get('marca'), data.get('establecimiento'),
            data.get('total_bruto', 0.0), data.get('costo_arancel', 0.0), 
            data.get('costo_financiero', 0.0), data.get('iva_21', 0.0), 
            data.get('iva_105', 0.0), data.get('retenciones', 0.0),
            data.get('total_neto', 0.0), json.dumps(data.get('metadata', {}))
        ))
        
        last_id = cursor.lastrowid
        if last_id == 0:
            res = conn.execute("""
                SELECT id FROM liquidaciones_tarjetas 
                WHERE fuente=? AND fecha_liquidacion=? AND periodo=? AND marca=? AND total_neto=?
            """, (fuente, data.get('fecha_liquidacion'), data.get('periodo'), data.get('marca'), data.get('total_neto'))).fetchone()
            if res: last_id = res[0]
            
        conn.commit()
        return last_id
    finally:
        conn.close()

def save_liquidacion_detalle(liq_id, detalle_lista: list):
    """Persistencia de líneas de detalle."""
    conn = get_db_connection()
    try:
        for d in detalle_lista:
            conn.execute('''
                INSERT INTO liquidaciones_detalles (
                    liquidacion_id, fecha, descripcion, monto_bruto, arancel, financiero, iva, retenciones, monto_neto, metadata_raw
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                liq_id, d.get('fecha'), d.get('descripcion'), d.get('monto_bruto', 0.0),
                d.get('arancel', 0.0), d.get('financiero', 0.0), d.get('iva', 0.0),
                d.get('retenciones', 0.0), d.get('monto_neto', 0.0), json.dumps(d.get('metadata_raw', {}))
            ))
        conn.commit()
    finally:
        conn.close()

def save_payway_records(lista_cupones: list):
    """Persistencia de registros de Payway."""
    conn = get_db_connection()
    try:
        for c in lista_cupones:
            conn.execute('''
                INSERT OR IGNORE INTO payway_records (
                    fecha_compra, fecha_presentacion, fecha_pago, lote, cupon, marca, monto_bruto, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                c.get('fecha_compra'), c.get('fecha_presentacion'), c.get('fecha_pago'),
                c.get('lote'), c.get('cupon'), c.get('marca'), c.get('monto_bruto'),
                json.dumps(c.get('metadata', {}))
            ))
        conn.commit()
    finally:
        conn.close()
