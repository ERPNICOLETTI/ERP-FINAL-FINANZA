import sqlite3
import json
import os
import logging
import re
from datetime import datetime

# STORAGE PAGOS - v5.0.0 💳🧱🧠⚖️
# Coherencia Arquitectónica con Compras y Bancos

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')

def sanitize_path_db(path):
    """Leyes de la Bóveda v5.2: Normalización universal y limpieza de ruido binario."""
    if not path: return None
    p = str(path).replace('\\', '/')
    p = "".join([c for c in p if 31 < ord(c) < 127 or ord(c) > 160])
    p = re.sub(r'/+', '/', p)
    p = p.replace(':/', '://').replace('://', ':/')
    return p.strip()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db_pagos():
    """Crea la tabla de Pagos y Vencimientos."""
    conn = get_db_connection()
    print("🧱 [PAGOS] Construyendo tabla de Vencimientos y Pagos v5.0...")

    conn.execute('''
        CREATE TABLE IF NOT EXISTS pagos (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto            TEXT NOT NULL,
            categoria           TEXT, -- Luz, Alquiler, 931, etc.
            fecha_vencimiento   TEXT,
            fecha_pago          TEXT,
            monto               REAL DEFAULT 0,
            estado              TEXT DEFAULT 'PENDIENTE', -- PENDING / PAID
            path_archivo        TEXT,
            hash_archivo        TEXT,
            meta_json           TEXT DEFAULT '{}',
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_pago(data: dict):
    """Guarda o actualiza un vencimiento/pago."""
    conn = get_db_connection()
    try:
        path_limpio = sanitize_path_db(data.get('path_archivo'))
        
        # Si tiene ID, es un UPDATE
        if data.get('id'):
            cursor = conn.execute('''
                UPDATE pagos SET 
                    concepto = COALESCE(?, concepto),
                    categoria = COALESCE(?, categoria),
                    fecha_vencimiento = COALESCE(?, fecha_vencimiento),
                    fecha_pago = COALESCE(?, fecha_pago),
                    monto = COALESCE(?, monto),
                    estado = COALESCE(?, estado),
                    path_archivo = ?,
                    meta_json = ?
                WHERE id = ?
            ''', (
                data.get('concepto'), data.get('categoria'), 
                data.get('fecha_vencimiento'), data.get('fecha_pago'),
                data.get('monto'), data.get('estado'),
                path_limpio, json.dumps(data.get('meta_json', {})),
                data.get('id')
            ))
            return data.get('id')
        else:
            # INSERT
            cursor = conn.execute('''
                INSERT INTO pagos (
                    concepto, categoria, fecha_vencimiento, monto, estado, path_archivo, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('concepto'), data.get('categoria', 'OTROS'),
                data.get('fecha_vencimiento'), data.get('monto', 0),
                data.get('estado', 'PENDIENTE'), path_limpio, 
                json.dumps(data.get('meta_json', {}))
            ))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error en save_pago: {e}")
        return None
    finally:
        conn.close()

def get_pagos(estado=None, categoria=None):
    """Lista los pagos con filtros opcionales."""
    conn = get_db_connection()
    query = "SELECT * FROM pagos WHERE 1=1"
    params = []
    
    if estado:
        query += " AND estado = ?"
        params.append(estado)
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
        
    query += " ORDER BY fecha_vencimiento ASC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

if __name__ == "__main__":
    init_db_pagos()
