import re
import sys

# Configure UTF-8 encoding for console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

MONTHS_MAP = {
    "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AGO": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12"
}

def dry_run():
    filepath = r"c:\Users\essao\Desktop\ERP FINAL\scratch\p365_text_plumber.txt"
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
        
    lines = text.split('\n')
    
    # 1. Detect billing period
    # Estado de cuenta: 21-MAY-26
    billing_period = None
    m_cierre = re.search(r'Estado de cuenta:\s*(\d{2})-([A-Za-z]{3})-(\d{2})', text)
    if m_cierre:
        day_c, month_c, year_c = m_cierre.groups()
        month_num = MONTHS_MAP.get(month_c.upper(), "05")
        billing_period = f"20{year_c}-{month_num}"
        
    if not billing_period:
        billing_period = "2026-05"
        
    print(f"Período Detectado: {billing_period}")
    
    # 2. Parse lines
    line_re = re.compile(r'^(\d{2})-([A-Za-z]{3})-(\d{2})\s+(.*)$')
    amount_re = re.compile(r'(-?)(\d+(?:\.\d{3})*,?\d{2})\s+(-?)(\d+(?:\.\d{3})*,?\d{2})\s*$')
    
    txs = []
    
    for line in lines:
        line_clean = line.strip('\r\n')
        m = line_re.match(line_clean.strip())
        if m:
            day, month, year, rest = m.groups()
            
            am = amount_re.search(rest)
            if not am:
                continue
                
            minus_pesos, pesos_str, minus_usd, usd_str = am.groups()
            
            # Si hay signo menos, u omitimos según descripción
            amount_pos = rest.rfind(am.group(0))
            middle = rest[:amount_pos].strip()
            
            # Buscar cuota
            cuota_match = re.search(r'\b(\d{1,2}/\d{1,2})\b', middle)
            cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""
            
            # Limpiar
            description = re.sub(r'\b\d{1,2}/\d{1,2}\b', '', middle).strip()
            description = re.sub(r'\b\d{5,}\b', '', description).strip()
            
            desc_upper = description.upper()
            if any(k in desc_upper for k in ["PAGOS", "SU PAGO", "SALDO ANTERIOR", "AJUSTES"]):
                continue
                
            # Determinar si es USD (si la columna USD no es 0,00)
            is_usd = usd_str != "0,00"
            amount_val_str = usd_str if is_usd else pesos_str
            
            val = float(amount_val_str.replace('.', '').replace(',', '.'))
            if is_usd:
                val = round(val * 1400.0, 2)
                
            # Formatear fecha
            month_num = MONTHS_MAP.get(month.upper(), "05")
            date_iso = f"20{year}-{month_num}-{day}"
            
            txs.append({
                "fecha": date_iso,
                "descripcion": f"{description}{cuota_str}".strip(),
                "monto": val,
                "is_usd": is_usd
            })
            
    print(f"\nConsumos Detectados ({len(txs)}):")
    for tx in txs:
        print(f"  - {tx['fecha']} | {tx['descripcion']} | $ {tx['monto']:.2f} {'(USD)' if tx['is_usd'] else ''}")

if __name__ == "__main__":
    dry_run()
