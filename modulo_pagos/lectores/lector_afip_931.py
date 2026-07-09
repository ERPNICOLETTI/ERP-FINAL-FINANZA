import re

# LECTOR PUNTUAL: AFIP F.931 v6.0.0 🧾🧠

def _iso(fecha_str):
    try:
        partes = fecha_str.strip().split('/')
        if len(partes) == 3:
            return f"{partes[2]}-{partes[1]}-{partes[0]}"
        return fecha_str
    except:
        return None

def procesar(TU, info):
    """Extrae periodo, montos, vencimiento y codigo de barras para AFIP F.931."""
    info['concepto'] = '931'
    info['categoria'] = 'IMPUESTOS'
    info['entidad'] = 'LDK'
    
    # 1. Extraer periodo
    # Buscar formato MM/YYYY
    m_per = re.search(r'(\d{2})/(\d{4})', TU)
    if m_per:
        info['periodo_mes'] = m_per.group(1)
        info['periodo_anio'] = m_per.group(2)
    else:
        # Fallback formato YYYY-MM
        m_per2 = re.search(r'PER[IÍI]ODO\s*:\s*(\d{4})-(\d{2})', TU)
        if m_per2:
            info['periodo_mes'] = m_per2.group(2)
            info['periodo_anio'] = m_per2.group(1)

    # 2. Extraer montos del bloque VIII
    sub_montos = {
        '301': 0.0, '302': 0.0, '351': 0.0, '352': 0.0,
        '312': 0.0, '028': 0.0, '360': 0.0, '935': 0.0, '270': 0.0
    }
    
    found_any = False
    for code in sub_montos.keys():
        patron = rf'{code}\s*-\s*.*?\s*([\d\.]+(?:,\d{{2}}))'
        m_val = re.search(patron, TU)
        if m_val:
            val_str = m_val.group(1).replace('.', '').replace(',', '.')
            sub_montos[code] = float(val_str)
            found_any = True
            
    if found_any:
        total_931 = sum(sub_montos.values())
        info['monto'] = round(total_931, 2)
        info['meta_json']['sub_montos'] = sub_montos

    # 3. Código de barras para pago
    m_bar = re.search(r'(\d{20,})', TU)
    if m_bar:
        info['codigo_barras'] = m_bar.group(1)

    # 4. Establecer Fecha de Vencimiento oficial (CUIT terminado en 1 -> Grupo 0-1-2-3)
    mes = info.get('periodo_mes')
    anio = info.get('periodo_anio')
    vencimiento_establecido = False
    
    if mes and anio:
        if anio == '2026':
            VENCIMIENTOS_931_2026 = {
                "12": "2026-01-09",
                "01": "2026-02-09",
                "02": "2026-03-09",
                "03": "2026-04-09",
                "04": "2026-05-11",
                "05": "2026-06-09",
                "06": "2026-07-13",
                "07": "2026-08-10",
                "08": "2026-09-09",
                "09": "2026-10-09",
                "10": "2026-11-09",
                "11": "2026-12-09"
            }
            if mes in VENCIMIENTOS_931_2026:
                info['fecha_vencimiento'] = VENCIMIENTOS_931_2026[mes]
                vencimiento_establecido = True
                
        if not vencimiento_establecido:
            try:
                m_int = int(mes)
                a_int = int(anio)
                next_m = m_int + 1
                next_a = a_int
                if next_m > 12:
                    next_m = 1
                    next_a += 1
                info['fecha_vencimiento'] = f"{next_a}-{str(next_m).zfill(2)}-09"
                vencimiento_establecido = True
            except:
                pass

    # Fallback por si acaso: si no se pudo calcular por período, usar fecha de presentación
    if not info.get('fecha_vencimiento'):
        m_f = re.search(r'PRESENTACI.*?N\s*:\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})', TU)
        if m_f:
            fecha_orig = m_f.group(1)
            if '/' in fecha_orig:
                info['fecha_vencimiento'] = _iso(fecha_orig)
            else:
                info['fecha_vencimiento'] = fecha_orig

    return True
