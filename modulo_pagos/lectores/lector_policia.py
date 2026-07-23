import re

# LECTOR PUNTUAL: POLICIA (SECRETARIA DE TRABAJO) v6.0.0 🏛️🧠

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
    """Extrae periodo, montos y vencimientos para POLICIA."""
    # 1. Extraer periodo (Formato YYYYMM)
    m = re.search(r'PER[IÍI]ODO[:\s]+(\d{4})(\d{2})\b', TU)
    if m:
        info['periodo_anio'] = m.group(1)
        info['periodo_mes']  = m.group(2)

    # 2. Extraer vencimientos y monto total
    # Vencimiento del Período Original (FECHA VENCIMIENTO: DD/MM/YYYY)
    pat_vto1 = re.search(r'FECHA\s+VENCIMIENTO:\s*(\d{2}/\d{2}/\d{4})', TU)
    # Vencimiento de la Boleta Re-emitida / Cupón (Vencimiento: DD/MM/YYYY)
    pat_vto2 = re.search(r'(?:Nro\.\s*de\s*Tasa.*?|\b)VENCIMIENTO:\s*(\d{2}/\d{2}/\d{4})', TU, re.IGNORECASE)
    
    # Buscar todas las apariciones de "Vencimiento: DD/MM/YYYY"
    vencimientos_hallados = re.findall(r'(\d{2}/\d{2}/\d{4})', TU)
    
    pat_monto = re.search(r'(?:TOTAL|TAL)\s+A\s+PAGAR\s*\$?\s*([\d\.]+,\d{2})', TU, re.IGNORECASE)
    if not pat_monto:
        pat_monto = re.search(r'MONTO\s+TOTAL\s*\$?\s*([\d\.]+,\d{2})', TU, re.IGNORECASE)
    
    if pat_vto1:
        info['fecha_vencimiento'] = _iso(pat_vto1.group(1))
    
    if pat_vto2:
        vto2_iso = _iso(pat_vto2.group(1))
        if vto2_iso != info.get('fecha_vencimiento'):
            info['fecha_vencimiento_2'] = vto2_iso
        else:
            # Buscar otra fecha de vencimiento distinta si la hay
            for f_str in vencimientos_hallados:
                f_iso = _iso(f_str)
                if f_iso and f_iso != info.get('fecha_vencimiento'):
                    info['fecha_vencimiento_2'] = f_iso
                    break

    if pat_monto:
        info['monto'] = _parse_monto(pat_monto.group(1))

    # 3. Formato Comprobante
    if not info['monto']:
        pat_ticket = re.search(r'(?:TOTAL PAGADO|TOTAL DEPOSITADO|VALOR DE LA FACTURA)\s*\$?\s*([\d\.]+,\d{2})', TU)
        if pat_ticket:
            info['monto'] = _parse_monto(pat_ticket.group(1))
        
        pat_fecha_pago = re.search(r'FECHA DE PAGO\s*.*?\s*(\d{2}/\d{2}/\d{4})', TU)
        if pat_fecha_pago:
            info['fecha_vencimiento'] = _iso(pat_fecha_pago.group(1))

    return True
