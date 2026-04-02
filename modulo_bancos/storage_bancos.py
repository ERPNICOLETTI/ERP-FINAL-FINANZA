import sqlite3
import json
import os

# STORAGE BANCOS - Dueño de tablas de Tesorería (Extractos Bancarios) 🏦🧱🧠

DB_PATH = 'erp_nicoletti.db'

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def init_db_bancos():
    """Crea las tablas pertenecientes al dominio de Bancos."""
    conn = get_db_connection()
    print("🧱 [BANCOS] Inicializando tablas...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bancos_movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            banco TEXT, -- CHUBUT, HIPOTECARIO, CREDICOOP
            cuenta TEXT, 
            fecha TEXT,
            descripcion TEXT,
            codigo_movimiento TEXT,
            importe REAL,
            metadata TEXT,
            UNIQUE(banco, cuenta, fecha, descripcion, codigo_movimiento, importe)
        )
    ''')
    conn.commit()
    conn.close()

def save_movimiento_banco(lista_movimientos: list):
    """Guarda masivamente movimientos bancarios."""
    conn = get_db_connection()
    try:
        agregados = 0
        for b in lista_movimientos:
            cursor = conn.execute('''
                INSERT OR IGNORE INTO bancos_movimientos (
                    banco, cuenta, fecha, descripcion, codigo_movimiento, importe, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                b.get('banco'), b.get('cuenta', 'SIN_ASIGNAR'), b.get('fecha'), b.get('descripcion'),
                b.get('codigo_movimiento'), b.get('importe'),
                json.dumps(b.get('metadata', {}))
            ))
            if cursor.rowcount > 0:
                agregados += 1
        conn.commit()
        return agregados
    finally:
        conn.close()
