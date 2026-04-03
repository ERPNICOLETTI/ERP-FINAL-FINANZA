import sqlite3
import pandas as pd
import json

# Motor Unificado de Tarjetas (Payway, Patagonia 365, Naranja) 💳🏗️🧠

def get_base_marca(m):
    m = m.upper()
    if 'VISA' in m: return 'VISA'
    if 'MASTERCARD' in m: return 'MASTERCARD'
    if 'CABAL' in m: return 'CABAL'
    if 'AMEX' in m: return 'AMEX'
    if '365' in m or 'PATAGONIA' in m: return 'PATAGONIA 365'
    return m

def get_db_connection():
    return sqlite3.connect(DB_PATH, timeout=30.0)

def resumen_ejecutivo(anio):
    """Estadísticas consolidadas de todas las tarjetas por año/periodo."""
    conn = get_db_connection()
    params = [f"{anio}%"] if anio else []
    
    # 1. Ventas por Posnet (Payway Records)
    # Nota: Patagonia 365 y Naranja a veces no vienen en el CSV de Payway.
    # Por ahora sumamos lo que hay en payway_records.
    q_ventas = "SELECT COUNT(*), SUM(monto_bruto) FROM payway_records"
    if anio: q_ventas += " WHERE fecha_compra LIKE ?"
    res_v = conn.execute(q_ventas, params).fetchone()

    # 2. Liquidaciones Consolidadas (La nueva tabla unificada)
    q_liq = "SELECT fuente, tipo, COUNT(*), SUM(total_bruto), SUM(total_neto), SUM(costo_arancel + costo_financiero + retenciones + iva_21 + iva_105) FROM liquidaciones_tarjetas"
    if anio: q_liq += " WHERE (fecha_liquidacion LIKE ? OR periodo LIKE ?)"
    
    # Adaptar params para fecha y periodo
    p_liq = [f"{anio}%", f"{anio}%"] if anio else []
    res_l = conn.execute(q_liq + " GROUP BY fuente, tipo", p_liq).fetchall()
    
    conn.close()
    
    liqs_data = []
    for r in res_l:
        liqs_data.append({
            "fuente": r[0],
            "tipo": r[1],
            "cantidad": r[2],
            "bruto": r[3] or 0.0,
            "neto": r[4] or 0.0,
            "gastos": r[5] or 0.0
        })

    return {
        "ventas_posnet": {"total_count": res_v[0] or 0, "monto_bruto": res_v[1] or 0.0},
        "liquidaciones": liqs_data
    }

def buscar_cupon(cupon_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    q = cupon_id.zfill(8)
    row = conn.execute("SELECT * FROM payway_records WHERE cupon = ? OR cupon LIKE ?", (q, f"%{cupon_id}")).fetchone()
    conn.close()
    if row:
        res = dict(row)
        res['metadata'] = json.loads(res['metadata'])
        return res
    return None

def auditoria_360():
    """Cruce de Ventas vs Liquidaciones (Solo para las que son DIARIAS, como Payway)."""
    conn = get_db_connection()
    
    # Ventas
    df_records = pd.read_sql_query("SELECT fecha_presentacion, marca, monto_bruto FROM payway_records", conn)
    df_records['marca_base'] = df_records['marca'].apply(get_base_marca)
    sum_p = df_records.groupby(['fecha_presentacion', 'marca_base'])['monto_bruto'].sum().reset_index()

    # Liquidaciones Diarias
    df_liq = pd.read_sql_query("SELECT fecha_liquidacion, marca, total_bruto, fuente FROM liquidaciones_tarjetas WHERE tipo = 'DIARIA'", conn)
    df_liq['marca_base'] = df_liq['marca'].apply(get_base_marca)

    missing_liq = []
    for _, row in sum_p.iterrows():
        match = df_liq[ (abs(df_liq['total_bruto'] - row['monto_bruto']) < 1.0) & (df_liq['marca_base'] == row['marca_base']) ]
        if match.empty: missing_liq.append(row)

    missing_coupons = []
    for _, row in df_liq.iterrows():
        match = sum_p[ (abs(sum_p['monto_bruto'] - row['total_bruto']) < 1.0) & (sum_p['marca_base'] == row['marca_base']) ]
        if match.empty: missing_coupons.append(row)

    conn.close()
    return {
        "missing_liquidations": [m.to_dict() for m in missing_liq[:10]],
        "missing_coupons": [m.to_dict() for m in missing_coupons[:10]],
    }
