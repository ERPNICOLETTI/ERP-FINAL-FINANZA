import re

# LECTOR PUNTUAL: SEC v6.0.0 🧾🧠

def _iso(fecha_str):
    try:
        partes = fecha_str.strip().split('/')
        return f"{partes[2]}-{partes[1]}-{partes[0]}"
    except:
        return None

def _parse_monto(monto_str):
    try:
        return float(monto_str.replace('.', '').replace(',', '.'))
    except:
        return None

def procesar(TU, info):
    """Extrae periodo, montos y vencimientos para SEC."""
    # 1. Extraer periodo (Formato YYYY-MM)
    m = re.search(r'\b(\d{4})-(\d{2})\s+SEC', TU)
    if m:
        info['periodo_anio'] = m.group(1)
        info['periodo_mes']  = m.group(2)

    # 2. Extraer vencimiento 1 y 2
    pat_a1 = re.search(r'FECHA\s+1ER\s+VTO\.?\s*:?\s*(\d{2}/\d{2}/\d{4})', TU)
    pat_a2 = re.search(r'FECHA\s+2DO\s+VTO\.?\s*:?\s*(\d{2}/\d{2}/\d{4})', TU)
    if pat_a1:
        info['fecha_vencimiento'] = _iso(pat_a1.group(1))
    if pat_a2:
        info['fecha_vencimiento_2'] = _iso(pat_a2.group(1))

    # 3. Buscar pares de fecha $ importe en tabla
    pares_sec = re.findall(r'(\d{2}/\d{2}/\d{4})\s*\$?\s*([\d\.]+,\d{2})', TU)
    montos_sec = []
    for fecha_str, monto_str in pares_sec:
        val = _parse_monto(monto_str)
        if val and val > 1000:
            iso_val = _iso(fecha_str)
            if iso_val not in [x[0] for x in montos_sec]:
                montos_sec.append((iso_val, val))
    montos_sec.sort(key=lambda x: x[0])
    
    if montos_sec:
        info['fecha_vencimiento'] = montos_sec[0][0]
        info['monto'] = montos_sec[0][1]
        if len(montos_sec) > 1:
            info['fecha_vencimiento_2'] = montos_sec[1][0]
            info['monto_2'] = montos_sec[1][1]

    # 4. Formato Comprobante
    if not info['monto']:
        pat_ticket = re.search(r'(?:TOTAL PAGADO|TOTAL DEPOSITADO|VALOR DE LA FACTURA)\s*\$?\s*([\d\.]+,\d{2})', TU)
        if pat_ticket:
            info['monto'] = _parse_monto(pat_ticket.group(1))
        
        pat_fecha_pago = re.search(r'FECHA DE PAGO\s*.*?\s*(\d{2}/\d{2}/\d{4})', TU)
        if pat_fecha_pago:
            info['fecha_vencimiento'] = _iso(pat_fecha_pago.group(1))

    return True
