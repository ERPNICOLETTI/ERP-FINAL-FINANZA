import re
import sys

# Configure UTF-8 encoding for console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def dry_run():
    filepath = r"c:\Users\essao\Desktop\ERP FINAL\scratch\naranja_text.txt"
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
        
    lines = text.split('\n')
    
    # 1. Detect billing period and closing date
    billing_period = None
    day_c, month_c, year_v = "27", "05", "26" # Fallbacks
    
    m_cierre = re.search(r'resumen actual cerró el (\d{2})/(\d{2})', text, re.IGNORECASE)
    m_vence = re.search(r'vence el \d{2}/\d{2}/(\d{2})', text)
    if m_cierre and m_vence:
        day_c, month_c = m_cierre.groups()
        year_v = m_vence.group(1)
        billing_period = f"20{year_v}-{month_c}"
        
    if not billing_period:
        billing_period = "2026-05"
        
    print(f"Período Detectado: {billing_period}")
    print(f"Fecha de Cierre Detectada: 20{year_v}-{month_c}-{day_c}")
    
    # 2. Parse lines
    line_re = re.compile(r'^(\d{2})/(\d{2})/(\d{2})\s+(.*)$')
    amount_re = re.compile(r'(\d+(?:\.\d{3})*,?\d{2})\s*$')
    
    txs = []
    iva_pending = False
    
    for line in lines:
        line_clean = line.strip('\r\n')
        
        if "IVA Operaciones Identificadas" in line_clean:
            iva_pending = True
            continue
            
        m = line_re.match(line_clean.strip())
        if m:
            day, month, year, rest = m.groups()
            
            am = amount_re.search(rest)
            if not am:
                continue
                
            amount_str = am.group(1)
            amount_pos = rest.rfind(amount_str)
            middle = rest[:amount_pos].strip()
            
            # Buscar cuota al final de middle (ej: 01/05) antes de limpiar
            cuota_match = re.search(r'\s+(\d{2}/\d{2})\s*$', middle)
            if cuota_match:
                cuota_str = f" {cuota_match.group(1)}"
                middle = re.sub(r'\s+\d{2}/\d{2}\s*$', '', middle).strip()
            else:
                cuota_str = ""
                
            # Limpiar cuota simple al final (ej: 01)
            middle = re.sub(r'\s+\d{2}\s*$', '', middle).strip()
            
            # Limpiar Naranja X y nro cupón
            middle = re.sub(r'^(?:Naranja\s+X\s+)?(?:\d{4}\s+)', '', middle).strip()
            middle = re.sub(r'^Naranja\s+X\s+', '', middle).strip()
            # Limpiar asterisco del inicio de cargos del banco
            middle = re.sub(r'^\*', '', middle).strip()
            
            description = middle
            
            # Omitir pagos
            desc_upper = description.upper()
            if "PAGO EN PESOS" in desc_upper or "SU PAGO" in desc_upper or desc_upper == "PAGO":
                continue
                
            # Formatear fecha
            date_iso = f"20{year}-{month}-{day}"
            
            val = float(amount_str.replace('.', '').replace(',', '.'))
            
            txs.append({
                "fecha": date_iso,
                "descripcion": f"{description}{cuota_str}".strip(),
                "monto": val
            })
            
        elif iva_pending:
            am = amount_re.search(line_clean)
            if am:
                val = float(am.group(1).replace('.', '').replace(',', '.'))
                txs.append({
                    "fecha": f"20{year_v}-{month_c}-{day_c}",
                    "descripcion": "IVA Operaciones Identificadas",
                    "monto": val
                })
            iva_pending = False
                
        elif "Impuesto de Sellos" in line_clean:
            am = amount_re.search(line_clean)
            if am:
                val = float(am.group(1).replace('.', '').replace(',', '.'))
                txs.append({
                    "fecha": f"20{year_v}-{month_c}-{day_c}",
                    "descripcion": "Impuesto de Sellos",
                    "monto": val
                })
                
    print(f"\nConsumos Detectados ({len(txs)}):")
    for tx in txs:
        print(f"  - {tx['fecha']} | {tx['descripcion']} | $ {tx['monto']:.2f}")

if __name__ == "__main__":
    dry_run()
