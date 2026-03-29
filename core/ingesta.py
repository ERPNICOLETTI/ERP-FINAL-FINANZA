import sqlite3
import json

# MOTOR DE INGESTA Y NORMALIZACIÓN 🏗️🧱🧠
# Es el "ladrillero" que recibe los datos de los parsers y los coloca en su lugar.

DB_PATH = 'erp_nicoletti.db'

def get_db_connection():
    return sqlite3.connect(DB_PATH)

# --- ÁREA: TARJETAS ---
def persistir_liquidacion(data: dict):
    """Guarda una liquidación (diaria o mensual) de cualquier fuente."""
    conn = get_db_connection()
    try:
        # Normalizamos campos obligatorios antes de insertar
        fuente = data.get('fuente', 'DESCONOCIDA').upper()
        tipo = data.get('tipo', 'DIARIA').upper()
        fecha = data.get('fecha_liquidacion')
        periodo = data.get('periodo')
        
        conn.execute('''
            INSERT OR IGNORE INTO liquidaciones_tarjetas (
                fuente, tipo, fecha_liquidacion, periodo, marca, establecimiento,
                total_bruto, costo_arancel, costo_financiero, iva_21, iva_105,
                retenciones, total_neto, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fuente, tipo, fecha, periodo, data.get('marca'), data.get('establecimiento'),
            data.get('total_bruto', 0.0), data.get('costo_arancel', 0.0), 
            data.get('costo_financiero', 0.0), data.get('iva_21', 0.0), 
            data.get('iva_105', 0.0), data.get('retenciones', 0.0),
            data.get('total_neto', 0.0), json.dumps(data.get('metadata', {}))
        ))
        conn.commit()
    finally:
        conn.close()

def persistir_cupones(lista_cupones: list):
    """Guarda masivamente cupones individuales (movimientos presentados)."""
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

# --- ÁREA: FACTURACIÓN ---
def persistir_factura(f: dict):
    """Guarda una factura normalizada."""
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT OR IGNORE INTO facturas (
                numero_completo, tipo_operacion, tipo_comprobante, proveedor, 
                fecha_emision, neto_gravado, monto_iva, monto_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f.get('numero_completo'), f.get('tipo_operacion'), f.get('tipo_comprobante'),
            f.get('proveedor'), f.get('fecha_emision'), f.get('neto_gravado'),
            f.get('monto_iva'), f.get('monto_total')
        ))
        conn.commit()
    finally:
        conn.close()

# --- ÁREA: BANCO ---
def persistir_transaccion(t: dict):
    """Guarda movimientos bancarios."""
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT OR IGNORE INTO transactions (
                entity, account, category, type, amount, desc, date, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            t.get('entity'), t.get('account'), t.get('category'), 
            t.get('type'), t.get('amount'), t.get('desc'), 
            t.get('date'), t.get('currency', 'ARS')
        ))
        conn.commit()
    finally:
        conn.close()
