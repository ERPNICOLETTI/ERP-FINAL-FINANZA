import re

# LECTOR PUNTUAL: INACAP v6.0.0 🧾🧠

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
    """Extrae periodo, montos y vencimientos para INACAP."""
    # 1. Extraer periodo
    m = re.search(r'PER[IÍI]ODO[:\s]+(\d{2})/(\d{4})', TU)
    if m:
        info['periodo_mes']  = m.group(1)
        info['periodo_anio'] = m.group(2)

    # 2. Extraer vencimientos y monto total
    pat_vto1 = re.search(r'(?:VENCIMIENTO DEL PER[IÍI]ODO|VENCIMIENTO):\s*(\d{2}/\d{2}/\d{4})', TU)
    pat_vto2 = re.search(r'FECHA DE PAGO INDICADA:\s*(\d{2}/\d{2}/\d{4})', TU)
    # Buscar todas las apariciones de importes tras MONTO TOTAL o al final del bloque
    matches_monto = re.findall(r'MONTO TOTAL.*?\$\s*([\d\.]+,\d{2})', TU)
    if not matches_monto:
        matches_monto = re.findall(r'\$\s*([\d\.]+,\d{2})', TU)
    if matches_monto:
        # Tomar el valor numérico mayor para asegurar tomar el Monto Total final con intereses
        parsed_vals = [_parse_monto(v) for v in matches_monto if _parse_monto(v) is not None]
        if parsed_vals:
            info['monto'] = max(parsed_vals)

    # 3. Formato Comprobante
    if not info['monto']:
        pat_ticket = re.search(r'(?:TOTAL PAGADO|TOTAL DEPOSITADO|VALOR DE LA FACTURA)\s*\$?\s*([\d\.]+,\d{2})', TU)
        if pat_ticket:
            info['monto'] = _parse_monto(pat_ticket.group(1))
        
        pat_fecha_pago = re.search(r'FECHA DE PAGO\s*.*?\s*(\d{2}/\d{2}/\d{4})', TU)
        if pat_fecha_pago:
            info['fecha_vencimiento'] = _iso(pat_fecha_pago.group(1))

    return True
