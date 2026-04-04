import pandas as pd
import json
from . import storage_tarjetas as storage

# Motor Unificado de Tarjetas (Payway, Patagonia 365, Naranja) 💳🏗️🧠

def get_base_marca(m):
    m = m.upper()
    if 'VISA' in m: return 'VISA'
    if 'MASTERCARD' in m: return 'MASTERCARD'
    if 'CABAL' in m: return 'CABAL'
    if 'AMEX' in m: return 'AMEX'
    if '365' in m or 'PATAGONIA' in m: return 'PATAGONIA 365'
    return m

def resumen_ejecutivo(anio):
    """Estadísticas consolidadas de todas las tarjetas por año/periodo. (Usa storage)"""
    return storage.get_resumen_tarjetas(anio)

def buscar_cupon(cupon_id):
    """Busca detalle de un cupón. (Usa storage)"""
    return storage.get_cupon_detalle(cupon_id)

def auditoria_360():
    """Cruce de Ventas vs Liquidaciones (Lógica de negocio sobre datos de Storage)."""
    data = storage.get_data_auditoria()
    
    # Ventas (Convertimos lista de dicts a DataFrame para lógica analítica)
    df_records = pd.DataFrame(data['records'])
    if df_records.empty:
        return {"missing_liquidations": [], "missing_coupons": []}
        
    df_records['marca_base'] = df_records['marca'].apply(get_base_marca)
    # Nota: Usamos 'fecha' que viene del alias en get_data_auditoria
    sum_p = df_records.groupby(['fecha', 'marca_base'])['monto_bruto'].sum().reset_index()

    # Liquidaciones Diarias
    df_liq = pd.DataFrame(data['liquidaciones'])
    if df_liq.empty:
        return {"missing_liquidations": sum_p.to_dict('records'), "missing_coupons": []}
        
    df_liq['marca_base'] = df_liq['marca'].apply(get_base_marca)

    missing_liq = []
    for _, row in sum_p.iterrows():
        match = df_liq[ (abs(df_liq['total_bruto'] - row['monto_bruto']) < 1.0) & (df_liq['marca_base'] == row['marca_base']) ]
        if match.empty: missing_liq.append(row)

    missing_coupons = []
    for _, row in df_liq.iterrows():
        match = sum_p[ (abs(sum_p['monto_bruto'] - row['total_bruto']) < 1.0) & (sum_p['marca_base'] == row['marca_base']) ]
        if match.empty: missing_coupons.append(row)

    return {
        "missing_liquidations": [m.to_dict() for m in missing_liq[:10]],
        "missing_coupons": [m.to_dict() for m in missing_coupons[:10]],
    }
