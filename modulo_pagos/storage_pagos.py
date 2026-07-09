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

def init_db_pagos_vencimientos():
    """Crea la tabla de Pagos con soporte para Legajo Único (Boleta + Comprobante)."""
    conn = get_db_connection()
    print("🧱 [PAGOS] Evolucionando tabla de Pagos v5.2 (Schema Trazabilidad Dual)...")

    # Migración/Creación: Usamos un diseño que soporta el ciclo de vida del pago
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pagos_vencimientos (
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
            codigo_barras       TEXT,
            meta_json           TEXT DEFAULT '{}',
            raw_ingesta_id      INTEGER DEFAULT NULL,
            numero_linea        INTEGER DEFAULT NULL,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migración dinámica para bases de datos existentes
    try:
        conn.execute("ALTER TABLE pagos_vencimientos ADD COLUMN raw_ingesta_id INTEGER DEFAULT NULL;")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE pagos_vencimientos ADD COLUMN numero_linea INTEGER DEFAULT NULL;")
    except sqlite3.OperationalError:
        pass
        
    # Crear índice para optimizar reprocesamiento
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pagos_raw_id ON pagos_vencimientos(raw_ingesta_id);")
    
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
        
        codigo_barras = data.get('codigo_barras')
        
        # Escalar montos a centavos enteros
        monto_cents = int(round(float(data.get('monto') or 0) * 100))
        monto_2_cents = int(round(float(data.get('monto_2') or 0) * 100))
        
        # 1. PRIORIDAD: Buscar por Código de Barras Único (Cruce Atómico v5.7)
        res = None
        if codigo_barras:
            cursor = conn.execute('''
                SELECT id, estado, path_boleta, path_comprobante, monto, monto_2, fecha_vencimiento, fecha_vencimiento_2 FROM pagos_vencimientos 
                WHERE codigo_barras = ?
            ''', (codigo_barras,))
            res = cursor.fetchone()

        # 2. SEGUNDA OPCIÓN: Buscar por Periodo (Fallback)
        if not res:
            cursor = conn.execute('''
                SELECT id, estado, path_boleta, path_comprobante, monto, monto_2, fecha_vencimiento, fecha_vencimiento_2 FROM pagos_vencimientos 
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
            final_boleta = p_boleta if p_boleta else res['path_boleta']
            final_compro = p_comprobante if p_comprobante else res['path_comprobante']
            final_estado = 'PAGADO' if final_compro else 'PENDIENTE'
            
            # Si es un comprobante, no sobreescribir montos ni vencimientos
            if p_comprobante:
                final_monto = res['monto'] if res['monto'] else monto_cents
                final_monto_2 = res['monto_2'] if res['monto_2'] else monto_2_cents
                final_vto = res['fecha_vencimiento'] if res['fecha_vencimiento'] else data.get('fecha_vencimiento')
                final_vto_2 = res['fecha_vencimiento_2'] if res['fecha_vencimiento_2'] else data.get('fecha_vencimiento_2')
            else:
                final_monto = monto_cents
                final_monto_2 = monto_2_cents
                final_vto = data.get('fecha_vencimiento')
                final_vto_2 = data.get('fecha_vencimiento_2')
            
            conn.execute('''
                UPDATE pagos_vencimientos SET 
                    categoria = COALESCE(?, categoria),
                    monto = COALESCE(?, monto),
                    fecha_vencimiento = COALESCE(?, fecha_vencimiento),
                    monto_2 = COALESCE(?, monto_2),
                    fecha_vencimiento_2 = COALESCE(?, fecha_vencimiento_2),
                    path_boleta = ?,
                    path_comprobante = ?,
                    hash_boleta = COALESCE(?, hash_boleta),
                    estado = ?,
                    codigo_barras = COALESCE(?, codigo_barras),
                    meta_json = ?,
                    raw_ingesta_id = COALESCE(?, raw_ingesta_id),
                    numero_linea = COALESCE(?, numero_linea)
                WHERE id = ?
            ''', (
                data.get('categoria'), final_monto, final_vto,
                final_monto_2, final_vto_2,
                final_boleta, final_compro, data.get('hash_boleta'), final_estado,
                codigo_barras, json.dumps(data.get('meta_json', {})),
                data.get('raw_ingesta_id'), data.get('numero_linea'), pago_id
            ))
            conn.commit()
            logger.info(f"🔄 [PAGOS] Registro actualizado: {concepto} {periodo_mes}/{periodo_anio} -> {final_estado}")
            return pago_id
        else:
            # SI EL REGISTRO NO EXISTE: Crear uno nuevo desde cero
            estado_inicial = 'PAGADO' if p_comprobante else 'PENDIENTE'
            cursor = conn.execute('''
                INSERT INTO pagos_vencimientos (
                    categoria, concepto, periodo_mes, periodo_anio, monto, fecha_vencimiento,
                    monto_2, fecha_vencimiento_2,
                    estado, path_boleta, path_comprobante, hash_boleta, codigo_barras, meta_json,
                    raw_ingesta_id, numero_linea
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('categoria', 'OTROS'), concepto, periodo_mes, periodo_anio,
                monto_cents, data.get('fecha_vencimiento'),
                monto_2_cents, data.get('fecha_vencimiento_2'),
                estado_inicial, p_boleta, p_comprobante, data.get('hash_boleta'),
                codigo_barras, json.dumps(data.get('meta_json', {})),
                data.get('raw_ingesta_id'), data.get('numero_linea')
            ))
            conn.commit()
            logger.info(f"✅ [PAGOS] Nuevo registro creado: {concepto} {periodo_mes}/{periodo_anio} -> {estado_inicial}")
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error en save_pago: {e}")
        return None
    finally:
        conn.close()

def _convert_row_to_floats(row_dict):
    """Convierte importes en centavos a flotantes decimales."""
    if not row_dict: return None
    res = dict(row_dict)
    res['monto'] = float(res.get('monto') or 0) / 100.0
    res['monto_2'] = float(res.get('monto_2') or 0) / 100.0
    return res

def find_pago_record(codigo_barras=None, concepto=None, mes=None, anio=None):
    """Busca un registro existente por barras o periodo."""
    conn = get_db_connection()
    res = None
    if codigo_barras:
        res = conn.execute("SELECT * FROM pagos_vencimientos WHERE codigo_barras = ?", (codigo_barras,)).fetchone()
    if not res and concepto and mes and anio:
        res = conn.execute("SELECT * FROM pagos_vencimientos WHERE concepto = ? AND periodo_mes = ? AND periodo_anio = ?", (concepto, mes, anio)).fetchone()
    conn.close()
    return _convert_row_to_floats(res)

def get_pagos_vencimientos(estado=None, categoria=None, periodo_anio=None, periodo_mes=None, entidad=None):
    conn = get_db_connection()
    query = "SELECT * FROM pagos_vencimientos WHERE 1=1"
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
    if entidad:
        query += " AND entidad = ?"
        params.append(entidad)
        
    query += " ORDER BY fecha_vencimiento ASC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_convert_row_to_floats(r) for r in rows]

if __name__ == "__main__":
    init_db_pagos_vencimientos()
