import sqlite3
import json
import os
import logging
import re
from datetime import datetime

# STORAGE PAGOS - v5.2.0 (Inteligencia Centralizada) 💳🧱🧠⚖️

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
    """Crea la tabla de Pagos con soporte para Legajo Único (Boleta + Comprobante)."""
    conn = get_db_connection()
    print("🧱 [PAGOS] Evolucionando tabla de Pagos v5.2 (Schema Trazabilidad Dual)...")

    # Migración/Creación: Usamos un diseño que soporta el ciclo de vida del pago
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pagos (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto            TEXT NOT NULL,
            categoria           TEXT,
            fecha_vencimiento   TEXT,
            monto               REAL DEFAULT 0,
            path_boleta         TEXT,
            path_comprobante    TEXT,
            estado              TEXT DEFAULT 'PENDIENTE',
            hash_boleta         TEXT,
            hash_comprobante    TEXT,
            meta_json           TEXT DEFAULT '{}',
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_pago(data: dict):
    """
    Guarda o actualiza un pago. 
    Lógica de Estado: PENDIENTE si solo hay boleta, PAGADO si hay comprobante.
    """
    conn = get_db_connection()
    try:
        p_boleta = sanitize_path_db(data.get('path_boleta'))
        p_comprobante = sanitize_path_db(data.get('path_comprobante'))
        
        # Determinar estado
        estado = 'PAGADO' if p_comprobante else 'PENDIENTE'
        
        # Si ya existe por concepto y fecha_vencimiento, hacemos UPDATE
        cursor = conn.execute('''
            SELECT id, path_boleta, path_comprobante FROM pagos 
            WHERE concepto = ? AND (fecha_vencimiento = ? OR fecha_vencimiento IS NULL)
        ''', (data.get('concepto'), data.get('fecha_vencimiento')))
        
        res = cursor.fetchone()
        
        if res:
            pago_id = res['id']
            # Mantener lo que ya estaba si el nuevo dato es nulo
            final_boleta = p_boleta if p_boleta else res['path_boleta']
            final_compro = p_comprobante if p_comprobante else res['path_comprobante']
            final_estado = 'PAGADO' if final_compro else 'PENDIENTE'
            
            conn.execute('''
                UPDATE pagos SET 
                    categoria = COALESCE(?, categoria),
                    monto = COALESCE(?, monto),
                    fecha_vencimiento = COALESCE(?, fecha_vencimiento),
                    path_boleta = ?,
                    path_comprobante = ?,
                    estado = ?,
                    meta_json = ?
                WHERE id = ?
            ''', (
                data.get('categoria'), data.get('monto'), data.get('fecha_vencimiento'),
                final_boleta, final_compro, final_estado,
                json.dumps(data.get('meta_json', {})), pago_id
            ))
            conn.commit()
            return pago_id
        else:
            # INSERT
            cursor = conn.execute('''
                INSERT INTO pagos (
                    concepto, categoria, fecha_vencimiento, monto, 
                    path_boleta, path_comprobante, estado, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('concepto'), data.get('categoria', 'OTROS'),
                data.get('fecha_vencimiento'), data.get('monto', 0),
                p_boleta, p_comprobante, estado, json.dumps(data.get('meta_json', {}))
            ))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error en save_pago: {e}")
        return None
    finally:
        conn.close()

def get_pagos():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM pagos ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

if __name__ == "__main__":
    init_db_pagos()
