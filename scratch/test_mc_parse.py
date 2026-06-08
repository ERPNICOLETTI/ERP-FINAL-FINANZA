import re

MONTHS_MAP = {
    "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AGO": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12"
}

def dry_run():
    filepath = r"C:\Users\essao\Desktop\ERP FINAL\scratch\mastercard_text.txt"
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
        
    lines = text.split('\n')
    
    # 1. Detect billing period
    billing_period = None
    for line in lines:
        m_cierre = re.search(r'\b(20\d{2})(\d{2})\d{2}\b', line)
        if m_cierre:
            year, month = m_cierre.groups()
            billing_period = f"{year}-{month}"
            break
    if not billing_period:
        billing_period = "2026-05"
        
    billing_year, billing_month = billing_period.split('-')
    print(f"Período Detectado: {billing_period}")
    
    # 2. Parse lines
    line_re = re.compile(r'^(\d{2})-([A-Za-z]{3})-(\d{2})\s+(.*)$')
    amount_re = re.compile(r'(-?)(\d+(?:\.\d{3})*,?\d{2})\s*$')
    
    blocks = []
    current_txs = []
    
    for line in lines:
        line_clean = line.strip('\r\n') # Keep trailing spaces for column detection
        m = line_re.match(line_clean.strip())
        if m:
            day, month, year, rest = m.groups()
            
            am = amount_re.search(rest)
            if not am:
                continue
                
            minus_sign, amount_str = am.groups()
            if minus_sign: # Omitir pagos/abonos
                continue
                
            amount_pos = rest.rfind(amount_str)
            middle = rest[:amount_pos].strip()
            
            # Limpiar importes de cuotas intermedios o basura
            middle = re.sub(r'-\s*$', '', middle).strip()
            middle = re.sub(r'\d+(?:\.\d{3})*,\d{2}\s*$', '', middle).strip()
            
            # Buscar cuota
            cuota_match = re.search(r'\b(\d{2}/\d{2})\b', middle)
            cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""
            
            # Limpiar descripción
            description = re.sub(r'\b\d{2}/\d{2}\b', '', middle).strip()
            
            # Determinar si es USD (si no termina con espacio extra en el crudo o si tiene moneda extranjera)
            is_usd = bool(re.search(r'\([A-Z]{3},', line_clean)) or not line_clean.endswith('  ')
            
            description = re.sub(r'\([A-Z]{3},[^)]+\)', '', description).strip()
            description = re.sub(r'\b\d{5,}\b', '', description).strip() # Quitar nro comprobante de 5+ digitos
            
            # Formatear fecha
            month_num = MONTHS_MAP.get(month.upper(), "05")
            date_iso = f"20{year}-{month_num}-{day}"
            
            val = float(amount_str.replace('.', '').replace(',', '.'))
            if is_usd:
                val = round(val * 1400.0, 2)
                
            tx_data = {
                "fecha": date_iso,
                "descripcion": f"{description}{cuota_str}".strip(),
                "monto": val,
                "is_usd": is_usd,
                "raw_line": line_clean
            }
            current_txs.append(tx_data)
            
        elif "SUBTOTAL" in line_clean and current_txs:
            # Primer subtotal pertenece a JOR
            print(f"\n[BLOCK JOR] ({len(current_txs)} consumos):")
            for tx in current_txs:
                print(f"  - {tx['fecha']} | {tx['descripcion']} | $ {tx['monto']} {'(USD)' if tx['is_usd'] else ''}")
            blocks.append(("JOR", current_txs))
            current_txs = []
            
        elif "TOTAL ADICIONAL DE NICOLETTI,JOAQUIN" in line_clean and current_txs:
            print(f"\n[BLOCK JOA] ({len(current_txs)} consumos):")
            for tx in current_txs:
                print(f"  - {tx['fecha']} | {tx['descripcion']} | $ {tx['monto']} {'(USD)' if tx['is_usd'] else ''}")
            blocks.append(("JOA", current_txs))
            current_txs = []
            
if __name__ == "__main__":
    dry_run()
