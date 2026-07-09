import re

# LECTOR PUNTUAL: FAECYS v6.0.0 🧾🧠

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
    """Extrae periodo, montos y vencimientos para FAECYS."""
    # 1. Extraer periodo
    m = re.search(r'PER[IÍI]ODO[:\s]+(\d{2})/(\d{4})', TU)
    if m:
        info['periodo_mes']  = m.group(1)
        info['periodo_anio'] = m.group(2)

    # 2. Extraer vencimientos y montos de boleta
    patron_b1 = re.search(
        r'FECHA PRIMER VTO\.?\s*:?\s*(\d{2}/\d{2}/\d{4})\s*\$\s*([\d\.]+,\d{2})',
        TU
    )
    patron_b2 = re.search(
        r'FECHA SEGUNDO VTO\.?\s*:?\s*(\d{2}/\d{2}/\d{4})\s*\$\s*([\d\.]+,\d{2})',
        TU
    )

    if patron_b1:
        info['fecha_vencimiento'] = _iso(patron_b1.group(1))
        info['monto']             = _parse_monto(patron_b1.group(2))
    if patron_b2:
        info['fecha_vencimiento_2'] = _iso(patron_b2.group(1))
        info['monto_2']             = _parse_monto(patron_b2.group(2))

    # 3. Formato Comprobante
    if not info['monto']:
        pat_ticket = re.search(r'(?:TOTAL PAGADO|TOTAL DEPOSITADO|VALOR DE LA FACTURA)\s*\$?\s*([\d\.]+,\d{2})', TU)
        if pat_ticket:
            info['monto'] = _parse_monto(pat_ticket.group(1))
        
        pat_fecha_pago = re.search(r'FECHA DE PAGO\s*.*?\s*(\d{2}/\d{2}/\d{4})', TU)
        if pat_fecha_pago:
            info['fecha_vencimiento'] = _iso(pat_fecha_pago.group(1))

    return True
