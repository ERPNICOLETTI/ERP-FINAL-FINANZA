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
            categoria           TEXT,
            concepto            TEXT NOT NULL,
            periodo_mes         TEXT,
            periodo_anio        TEXT,
            monto               REAL DEFAULT 0,
            fecha_vencimiento   TEXT,
            monto_2             REAL DEFAULT 0,
            fecha_vencimiento_2   TEXT,
            estado              TEXT DEFAULT 'PENDIENTE',
            path_boleta         TEXT,
            path_comprobante    TEXT,
            hash_boleta         TEXT,
            meta_json           TEXT DEFAULT '{}',
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_pago(data: dict):
    """
    Guarda o actualiza un pago con lógica estricta de periodo.
    """
    conn = get_db_connection()
    try:
        p_boleta = sanitize_path_db(data.get('path_boleta'))
        p_comprobante = sanitize_path_db(data.get('path_comprobante'))
        
        concepto = data.get('concepto')
        periodo_mes = data.get('periodo_mes')
        periodo_anio = data.get('periodo_anio')
        
        # Buscar Duplicados de Periodo
        cursor = conn.execute('''
            SELECT id, estado, path_boleta, path_comprobante FROM pagos 
            WHERE concepto = ? AND periodo_mes = ? AND periodo_anio = ?
        ''', (concepto, periodo_mes, periodo_anio))
        
        res = cursor.fetchone()
        
        if res:
            pago_id = res['id']
            estado_actual = res['estado']
            
            # SI EL REGISTRO YA ESTÁ 'PAGADO' 🟢
            if estado_actual == 'PAGADO':
                logger.warning(f"⚠️ [PAGOS] Intento de modificar {concepto} {periodo_mes}/{periodo_anio} que ya está PAGADO. Operación ignorada para evitar errores.")
                return pago_id
            
            # SI EL REGISTRO EXISTE Y ESTÁ 'IMPAGO/VENCIDO' o 'PENDIENTE'
            # 1. Reemplazar el archivo físico (esto se maneja pre-guardado borrando el viejo si es necesario, 
            #    pero aquí actualizamos la ruta)
            final_boleta = p_boleta if p_boleta else res['path_boleta']
            final_compro = p_comprobante if p_comprobante else res['path_comprobante']
            
            # 3. Resetear el estado a 'PENDIENTE' 🔴 (Si se está subiendo una boleta nueva)
            # Acotación: si final_compro existe, pasa a PAGADO.
            final_estado = 'PAGADO' if final_compro else 'PENDIENTE'
            
            conn.execute('''
                UPDATE pagos SET 
                    categoria = COALESCE(?, categoria),
                    monto = COALESCE(?, monto),
                    fecha_vencimiento = COALESCE(?, fecha_vencimiento),
                    monto_2 = COALESCE(?, monto_2),
                    fecha_vencimiento_2 = COALESCE(?, fecha_vencimiento_2),
                    path_boleta = ?,
                    path_comprobante = ?,
                    hash_boleta = COALESCE(?, hash_boleta),
                    estado = ?,
                    meta_json = ?
                WHERE id = ?
            ''', (
                data.get('categoria'), data.get('monto'), data.get('fecha_vencimiento'),
                data.get('monto_2'), data.get('fecha_vencimiento_2'),
                final_boleta, final_compro, data.get('hash_boleta'), final_estado,
                json.dumps(data.get('meta_json', {})), pago_id
            ))
            conn.commit()
            logger.info(f"🔄 [PAGOS] Registro actualizado: {concepto} {periodo_mes}/{periodo_anio} -> {final_estado}")
            return pago_id
        else:
            # SI EL REGISTRO NO EXISTE: Crear uno nuevo desde cero
            estado_inicial = 'PAGADO' if p_comprobante else 'PENDIENTE'
            cursor = conn.execute('''
                INSERT INTO pagos (
                    categoria, concepto, periodo_mes, periodo_anio, monto, fecha_vencimiento,
                    monto_2, fecha_vencimiento_2,
                    estado, path_boleta, path_comprobante, hash_boleta, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('categoria', 'OTROS'), concepto, periodo_mes, periodo_anio,
                data.get('monto', 0), data.get('fecha_vencimiento'),
                data.get('monto_2', 0), data.get('fecha_vencimiento_2'),
                estado_inicial, p_boleta, p_comprobante, data.get('hash_boleta'),
                json.dumps(data.get('meta_json', {}))
            ))
            conn.commit()
            logger.info(f"✅ [PAGOS] Nuevo registro creado: {concepto} {periodo_mes}/{periodo_anio} -> {estado_inicial}")
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error en save_pago: {e}")
        return None
    finally:
        conn.close()

def get_pagos(estado=None, categoria=None, periodo_anio=None, periodo_mes=None):
    conn = get_db_connection()
    query = "SELECT * FROM pagos WHERE 1=1"
    params = []
    
    if estado:
        query += " AND estado = ?"
        params.append(estado)
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    if periodo_anio:
        query += " AND periodo_anio = ?"
        params.append(periodo_anio)
    if periodo_mes:
        query += " AND periodo_mes = ?"
        params.append(periodo_mes)
        
    query += " ORDER BY fecha_vencimiento ASC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

if __name__ == "__main__":
    init_db_pagos()
