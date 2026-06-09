import sqlite3
import os
import re
import PyPDF2
from modulo_gastos import storage_gastos

DB_PATH = 'erp_nicoletti.db'

# Define months map for Patagonia 365
MONTHS_MAP = {
    "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AGO": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12"
}

def parse_visa_hipotecario(path):
    text = ""
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
            
    billing_period = None
    m_period = re.search(r'Liquidación de cuenta de fecha\s*(\d{2})/(\d{2})/(\d{2})', text, re.IGNORECASE)
    if m_period:
        day_p, month_p, year_p = m_period.groups()
        billing_period = f"20{year_p}-{month_p}"
    if not billing_period:
        billing_period = "2026-05"
    billing_year, billing_month = billing_period.split('-')
    
    line_re = re.compile(r'^(\d{2})-(\d{2})-(\d{2})\s+(.*)$')
    amount_re = re.compile(r'(-?)(\d+(?:\.\d{3})*,?\d{2})\s+(-?)(\d+(?:\.\d{3})*,?\d{2})\s*$')
    
    txs = []
    lines = text.split('\n')
    for line in lines:
        line_clean = line.strip('\r\n')
        m = line_re.match(line_clean.strip())
        if m:
            day, month, year, rest = m.groups()
            am = amount_re.search(rest)
            if not am:
                continue
            minus_pesos, pesos_str, minus_usd, usd_str = am.groups()
            amount_pos = rest.rfind(am.group(0))
            middle = rest[:amount_pos].strip()
            
            cuota_match = re.search(r'\b(\d{1,2}/\d{1,2})\b', middle)
            cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""
            description = re.sub(r'\b\d{1,2}/\d{1,2}\b', '', middle).strip()
            
            # Limpiar importes intermedios o base de impuestos y referencias
            description = re.sub(r'\b\d+(?:\.\d{3})*,\d{2}\s*$', '', description).strip()
            description = re.sub(r'\(\s*\d+(?:\.\d{3})*,\d{2}\s*\)\s*$', '', description).strip()
            description = re.sub(r'\s+\$\s*$', '', description).strip()
            description = re.sub(r'\s+P\s*\$?\s*$', '', description).strip()
            description = re.sub(r'^[\*K\s]+', '', description).strip()
            
            desc_upper = description.upper()
            if "PAGOS" in desc_upper or "SU PAGO" in desc_upper or "SALDO ANTERIOR" in desc_upper:
                continue
                
            is_usd = usd_str != "0,00"
            amount_val_str = usd_str if is_usd else pesos_str
            val = float(amount_val_str.replace('.', '').replace(',', '.'))
            if is_usd:
                val = round(val * 1400.0, 2)
                
            date_iso = f"{billing_year}-{billing_month}-{day}"
            fecha_compra = f"20{year}-{month}-{day}"
            
            txs.append({
                "fecha": date_iso,
                "fecha_compra": fecha_compra,
                "descripcion": f"{description}{cuota_str}".strip(),
                "monto": val,
                "fuente": "Visa Hipotecario"
            })
    return txs

def parse_visa_galicia(path):
    text = ""
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
            
    billing_period = None
    m_period = re.search(r'Cierre actual:\s*(\d{2})/(\d{2})/(\d{2})', text, re.IGNORECASE)
    if m_period:
        day_p, month_p, year_p = m_period.groups()
        billing_period = f"20{year_p}-{month_p}"
    if not billing_period:
        billing_period = "2026-05"
    billing_year, billing_month = billing_period.split('-')
    
    line_re = re.compile(r'^(\d{2})-(\d{2})-(\d{2})\s+(.*)$')
    amount_re = re.compile(r'(-?)(\d+(?:\.\d{3})*,?\d{2})\s*(-?)$')
    
    txs = []
    lines = text.split('\n')
    for line in lines:
        line_clean = line.strip('\r\n')
        m = line_re.match(line_clean.strip())
        if m:
            day, month, year, rest = m.groups()
            am = amount_re.search(rest)
            if not am:
                continue
            minus_sign_before, amount_str, minus_sign_after = am.groups()
            amount_pos = rest.rfind(am.group(0))
            middle = rest[:amount_pos].strip()
            
            # Limpiar importes intermedios de impuestos
            middle = re.sub(r'-\s*$', '', middle).strip()
            middle = re.sub(r'\d+(?:\.\d{3})*,\d{2}\s*$', '', middle).strip()

            # Buscar cuota en la descripción
            cuota_match = re.search(r'\b(\d{2}/\d{2})\b', middle)
            cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""

            # Extraer y limpiar descripción
            description = re.sub(r'\b\d{2}/\d{2}\b', '', middle).strip()
            description = re.sub(r'\b\d{6,}\b\s*$', '', description).strip() # Quitar números de referencia largos
            description = re.sub(r'^[\*K\s]+', '', description).strip() # Limpiar prefijo de tarjeta JOR/JOA
            description = re.sub(r'\s+\$\s*$', '', description).strip() # Quitar signo pesos sobrante
            
            desc_upper = description.upper()
            if "PAGOS" in desc_upper or "SU PAGO" in desc_upper or "SALDO ANTERIOR" in desc_upper:
                continue
                
            val = float(amount_str.replace('.', '').replace(',', '.'))
            date_iso = f"{billing_year}-{billing_month}-{day}"
            fecha_compra = f"20{year}-{month}-{day}"
            
            txs.append({
                "fecha": date_iso,
                "fecha_compra": fecha_compra,
                "descripcion": f"{description}{cuota_str}".strip(),
                "monto": val,
                "fuente": "Visa Galicia"
            })
    return txs

def parse_mastercard_galicia(path):
    text = ""
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
            
    billing_period = None
    cierre_date = None
    m_cierre = re.search(r'\b(20\d{2})(\d{2})(\d{2})', text)
    if m_cierre:
        year, month, day = m_cierre.groups()
        billing_period = f"{year}-{month}"
        cierre_date = f"{year}-{month}-{day}"
    else:
        m_period = re.search(r'Cierre actual:\s*(\d{2})/(\d{2})/(\d{2})', text, re.IGNORECASE)
        if m_period:
            day_p, month_p, year_p = m_period.groups()
            billing_period = f"20{year_p}-{month_p}"
            cierre_date = f"20{year_p}-{month_p}-{day_p}"
            
    if not billing_period:
        billing_period = "2026-05"
    billing_year, billing_month = billing_period.split('-')
    if not cierre_date:
        cierre_date = f"{billing_year}-{billing_month}-28"
    
    line_re = re.compile(r'^(\d{2})-([A-Za-z]{3})-(\d{2})\s+(.*)$')
    amount_re = re.compile(r'(-?)(\d+(?:\.\d{3})*,?\d{2})\s*(-?)$')
    summary_re = re.compile(
        r'^(INTERESES DE FINANCIACION|IMPUESTO DE SELLOS|I\.V\.A\.\s+\d+,\d+%|PERCEPCION IVA DTO \d+/\d+|PERCEP\.AFIP RG \d+ \d*%)\s+(-?\d+(?:\.\d{3})*,?\d{2})(?:\s+(-?\d+(?:\.\d{3})*,?\d{2}))?\s*$'
    )
    
    txs = []
    current_txs = []
    lines = text.split('\n')
    for line in lines:
        line_clean = line.strip('\r\n')
        m = line_re.match(line_clean.strip())
        if m:
            day, month, year, rest = m.groups()
            am = amount_re.search(rest)
            if not am:
                continue
            minus_sign_before, amount_str, minus_sign_after = am.groups()
            amount_pos = rest.rfind(am.group(0))
            middle = rest[:amount_pos].strip()
            
            cuota_match = re.search(r'\b(\d{1,2}/\d{1,2})\b', middle)
            cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""
            description = re.sub(r'\b\d{1,2}/\d{1,2}\b', '', middle).strip()
            is_usd = bool(re.search(r'\([A-Z]{3},', line_clean)) or not line_clean.endswith('  ')
            description = re.sub(r'\([A-Z]{3},[^)]+\)', '', description).strip()
            description = re.sub(r'\b\d{5,}\b', '', description).strip()
            description = re.sub(r'\s+\$\s*$', '', description).strip()
            description = re.sub(r'^[\*K\s]+', '', description).strip()
            
            desc_upper = description.upper()
            if "PAGOS" in desc_upper or "SU PAGO" in desc_upper or "SALDO ANTERIOR" in desc_upper:
                continue
                
            val = float(amount_str.replace('.', '').replace(',', '.'))
            if is_usd:
                val = round(val * 1400.0, 2)
            date_iso = f"{billing_year}-{billing_month}-{day}"
            month_num = MONTHS_MAP.get(month.upper(), "05")
            fecha_compra = f"20{year}-{month_num}-{day}"
            
            current_txs.append({
                "fecha": date_iso,
                "fecha_compra": fecha_compra,
                "descripcion": f"{description}{cuota_str}".strip(),
                "monto": val,
                "fuente": "Mastercard Galicia"
            })
        elif "SUBTOTAL" in line_clean and current_txs:
            for t in current_txs:
                t["owner"] = "JOR"
                txs.append(t)
            current_txs = []
        elif "TOTAL ADICIONAL DE NICOLETTI,JOAQUIN" in line_clean and current_txs:
            for t in current_txs:
                t["owner"] = "JOA"
                txs.append(t)
            current_txs = []
        else:
            m_summary = summary_re.match(line_clean.strip())
            if m_summary:
                name = m_summary.group(1)
                pesos_str = m_summary.group(2)
                usd_str = m_summary.group(3)
                
                if pesos_str.startswith('-'):
                    # Omitir abonos/créditos
                    continue
                    
                val = float(pesos_str.replace('.', '').replace(',', '.'))
                if usd_str:
                    val_usd = float(usd_str.replace('.', '').replace(',', '.'))
                    val = round(val + (val_usd * 1400.0), 2)
                    
                current_txs.append({
                    "fecha": cierre_date,
                    "fecha_compra": cierre_date,
                    "descripcion": name.strip(),
                    "monto": val,
                    "fuente": "Mastercard Galicia"
                })
            
    for t in current_txs:
        t["owner"] = "JOR"
        txs.append(t)
    return txs

def parse_tarjeta_naranja(path):
    text = ""
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
            
    billing_period = None
    day_c, month_c, year_v = "27", "05", "26"
    m_cierre = re.search(r'resumen actual cerró el (\d{2})/(\d{2})', text, re.IGNORECASE)
    m_vence = re.search(r'vence el \d{2}/\d{2}/(\d{2})', text)
    if m_cierre and m_vence:
        day_c, month_c = m_cierre.groups()
        year_v = m_vence.group(1)
        billing_period = f"20{year_v}-{month_c}"
    if not billing_period:
        billing_period = "2026-05"
    billing_year, billing_month = billing_period.split('-')
    
    line_re = re.compile(r'^(\d{2})/(\d{2})/(\d{2})\s+(.*)$')
    amount_re = re.compile(r'(\d+(?:\.\d{3})*,?\d{2})\s*$')
    
    txs = []
    iva_pending = False
    lines = text.split('\n')
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
            
            cuota_match = re.search(r'\s+(\d{2}/\d{2})\s*$', middle)
            cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""
            if cuota_match:
                middle = re.sub(r'\s+\d{2}/\d{2}\s*$', '', middle).strip()
            middle = re.sub(r'\s+\d{2}\s*$', '', middle).strip()
            middle = re.sub(r'^(?:Naranja\s+X\s+)?(?:\d{4}\s+)', '', middle).strip()
            middle = re.sub(r'^Naranja\s+X\s+', '', middle).strip()
            middle = re.sub(r'^\*', '', middle).strip()
            description = middle
            
            desc_upper = description.upper()
            if "PAGO EN PESOS" in desc_upper or "SU PAGO" in desc_upper or desc_upper == "PAGO":
                continue
                
            val = float(amount_str.replace('.', '').replace(',', '.'))
            date_iso = f"{billing_year}-{billing_month}-{day}"
            fecha_compra = f"20{year}-{month}-{day}"
            
            txs.append({
                "fecha": date_iso,
                "fecha_compra": fecha_compra,
                "descripcion": f"{description}{cuota_str}".strip(),
                "monto": val,
                "fuente": "Tarjeta Naranja"
            })
        elif iva_pending:
            am = amount_re.search(line_clean)
            if am:
                val = float(am.group(1).replace('.', '').replace(',', '.'))
                fecha_cierre = f"20{year_v}-{month_c}-{day_c}"
                txs.append({
                    "fecha": fecha_cierre,
                    "fecha_compra": fecha_cierre,
                    "descripcion": "IVA Operaciones Identificadas",
                    "monto": val,
                    "fuente": "Tarjeta Naranja"
                })
            iva_pending = False
        elif "Impuesto de Sellos" in line_clean:
            am = amount_re.search(line_clean)
            if am:
                val = float(am.group(1).replace('.', '').replace(',', '.'))
                fecha_cierre = f"20{year_v}-{month_c}-{day_c}"
                txs.append({
                    "fecha": fecha_cierre,
                    "fecha_compra": fecha_cierre,
                    "descripcion": "Impuesto de Sellos",
                    "monto": val,
                    "fuente": "Tarjeta Naranja"
                })
    return txs

def parse_patagonia_365(path):
    text = ""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
            
    billing_period = None
    m_cierre = re.search(r'Estado de cuenta:\s*(\d{2})-([A-Za-z]{3})-(\d{2})', text)
    if m_cierre:
        day_c, month_c, year_c = m_cierre.groups()
        month_num = MONTHS_MAP.get(month_c.upper(), "05")
        billing_period = f"20{year_c}-{month_num}"
    if not billing_period:
        billing_period = "2026-05"
    billing_year, billing_month = billing_period.split('-')
    
    line_re = re.compile(r'^(\d{2})-([A-Za-z]{3})-(\d{2})\s+(.*)$')
    amount_re = re.compile(r'(-?)(\d+(?:\.\d{3})*,?\d{2})\s+(-?)(\d+(?:\.\d{3})*,?\d{2})\s*$')
    
    txs = []
    lines = text.split('\n')
    for line in lines:
        line_clean = line.strip('\r\n')
        m = line_re.match(line_clean.strip())
        if m:
            day, month, year, rest = m.groups()
            am = amount_re.search(rest)
            if not am:
                continue
            minus_pesos, pesos_str, minus_usd, usd_str = am.groups()
            amount_pos = rest.rfind(am.group(0))
            middle = rest[:amount_pos].strip()
            
            cuota_match = re.search(r'\b(\d{1,2}/\d{1,2})\b', middle)
            cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""
            description = re.sub(r'\b\d{1,2}/\d{1,2}\b', '', middle).strip()
            description = re.sub(r'\b\d{5,}\b', '', description).strip()
            
            desc_upper = description.upper()
            if any(k in desc_upper for k in ["PAGOS", "SU PAGO", "SALDO ANTERIOR", "AJUSTES"]):
                continue
                
            is_usd = usd_str != "0,00"
            amount_val_str = usd_str if is_usd else pesos_str
            val = float(amount_val_str.replace('.', '').replace(',', '.'))
            if is_usd:
                val = round(val * 1400.0, 2)
                
            date_iso = f"{billing_year}-{billing_month}-{day}"
            month_num = MONTHS_MAP.get(month.upper(), "05")
            fecha_compra = f"20{year}-{month_num}-{day}"
            
            txs.append({
                "fecha": date_iso,
                "fecha_compra": fecha_compra,
                "descripcion": f"{description}{cuota_str}".strip(),
                "monto": val,
                "fuente": "Patagonia 365"
            })
    return txs

# Main logic
PDFS = {
    "Visa Hipotecario": r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\crudos_bancos\VISA_HIPOTECARIO\2026\05\UltimaLiquidacion__2_.pdf",
    "Visa Galicia": r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\crudos_bancos\VISA_GALICIA\2026\05\9bf9797a-3eab-4377-9c52-4d0ea58ee5da.pdf",
    "Mastercard Galicia": r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\crudos_bancos\MASTERCARD_GALICIA\2026\05\50d6c0d8-22a7-44e9-90ba-2c62c95abcad.pdf",
    "Tarjeta Naranja": r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\crudos_bancos\TARJETA_NARANJA\2026\05\resumen-tarjeta-naranja-1780932133.pdf",
    "Patagonia 365": r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\crudos_bancos\PATAGONIA365\2026\05\Resumen_P365_Mayo_2026.pdf"
}

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get all classifications categories rules (to classify new ones if needed)
tipos = conn.execute("SELECT id, nombre, cuenta_codigo, palabras_clave FROM gastos_tipos").fetchall()
rules = []
for t in tipos:
    kw_str = t[3] or ""
    keywords = [k.strip().lower() for k in kw_str.split(',') if k.strip()]
    keywords.append(t[1].lower())
    rules.append({
        "id": t[0],
        "nombre": t[1],
        "cuenta": t[2],
        "keywords": keywords
    })

SOURCE_PREFERENCES = {
    "Visa Hipotecario": ["JOA", "COMUN"],
    "Visa Galicia": ["JOR", "COMUN", "LDK"],
    "Mastercard Galicia": ["LDK", "COMUN", "JOR"],
    "Tarjeta Naranja": ["LDK", "COMUN", "JOR"],
    "Patagonia 365": ["LDK", "COMUN", "JOR"]
}

CARD_SPECIFIC_CATEGORIES = [
    "Gasto Tarjeta", "Intereses Tarjeta", "Tarjeta", 
    "Gastos Personales", "Gastos de Vida", 
    "Aportes de Capital", "Impuestos Comerciales"
]

all_parsed_txs = []
for source, path in PDFS.items():
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        continue
    print(f"Parsing {source}...")
    if source == "Visa Hipotecario":
        parsed = parse_visa_hipotecario(path)
    elif source == "Visa Galicia":
        parsed = parse_visa_galicia(path)
    elif source == "Mastercard Galicia":
        parsed = parse_mastercard_galicia(path)
    elif source == "Tarjeta Naranja":
        parsed = parse_tarjeta_naranja(path)
    elif source == "Patagonia 365":
        parsed = parse_patagonia_365(path)
    all_parsed_txs.extend(parsed)

updated_count = 0
inserted_count = 0

for tx in all_parsed_txs:
    monto = tx['monto']
    fecha = tx['fecha']
    fuente = tx['fuente']
    parsed_desc = tx['descripcion']
    fecha_compra = tx['fecha_compra']
    
    # 1. Search if a record with same amount, period date, and source already exists in DB
    # We match by amount, period date, and source
    cursor.execute("""
        SELECT id, gasto_tipo_id, descripcion 
        FROM gastos_registros 
        WHERE monto = ? AND fecha = ? AND fuente = ?
    """, (monto, fecha, fuente))
    matches = cursor.fetchall()
    
    match = None
    if len(matches) == 1:
        match = matches[0]
    elif len(matches) > 1:
        # Match by description overlap
        # Check if the parsed description is in the DB description or vice versa
        for m in matches:
            db_desc_clean = re.sub(r'\s*\([^)]*\)\s*$', '', m[2]).strip().lower()
            parsed_desc_clean = parsed_desc.lower()
            # Check for substring match
            if parsed_desc_clean in db_desc_clean or db_desc_clean in parsed_desc_clean:
                match = m
                break
        if not match:
            # Fallback to the first one
            match = matches[0]
            
    if match:
        reg_id, current_type_id, current_desc = match
        # Update record with clean description and correct fecha_compra, preserving gasto_tipo_id!
        cursor.execute("""
            UPDATE gastos_registros
            SET descripcion = ?, fecha_compra = ?
            WHERE id = ?
        """, (parsed_desc, fecha_compra, reg_id))
        updated_count += 1
    else:
        # Insert new record using classification
        # Filter valid rules
        pref_accounts = SOURCE_PREFERENCES[fuente]
        if fuente == "Mastercard Galicia" and "owner" in tx:
            pref_accounts = ['LDK', 'COMUN', 'JOR'] if tx['owner'] == 'JOR' else ['JOA', 'COMUN']
            
        valid_rules = []
        for r in rules:
            if r['nombre'] in CARD_SPECIFIC_CATEGORIES:
                if r['cuenta'] in pref_accounts:
                    valid_rules.append(r)
            else:
                valid_rules.append(r)
                
        # Prioritize rules
        prioritized_rules = sorted(
            valid_rules,
            key=lambda r: 0 if r['cuenta'] in pref_accounts else 1
        )
        
        # Match keywords
        matched_concept = None
        desc_lower = parsed_desc.lower()
        
        # 1. Intentar clasificar usando el historial de aprendizaje del usuario
        matched_concept = storage_gastos.buscar_clasificacion_previa(conn, parsed_desc, monto)
        
        if not matched_concept:
            # Special case for Gemini
            if fuente == "Visa Hipotecario" and "google" in desc_lower and abs(monto - 27986.0) < 10.0:
                for r in prioritized_rules:
                    if r['nombre'] == "GEMINI":
                        matched_concept = r
                        break
                        
            # Caso especial para ESCO: el más barato (102450) a JOR/ESCO Jorge, los otros a COMUN/ESCO
            if not matched_concept and "esco" in desc_lower:
                target_name = "ESCO Jorge" if abs(monto - 102450.0) < 10.0 else "ESCO"
                target_cuenta = "JOR" if target_name == "ESCO Jorge" else "COMUN"
                for r in prioritized_rules:
                    if r['nombre'] == target_name and r['cuenta'] == target_cuenta:
                        matched_concept = r
                        break

            if not matched_concept:
                for r in prioritized_rules:
                    for kw in r['keywords']:
                        if kw in desc_lower:
                            matched_concept = r
                            break
                    if matched_concept:
                        break
                        
            # Fallbacks
            if not matched_concept:
                if fuente == "Visa Hipotecario":
                    fallback_name = "Gastos Personales"
                    fallback_acc = "JOA"
                elif fuente == "Mastercard Galicia" and "owner" in tx:
                    fallback_name = "Gastos de Vida" if tx['owner'] == 'JOR' else "Gastos Personales"
                    fallback_acc = tx['owner']
                else:
                    fallback_name = "Gastos de Vida"
                    fallback_acc = "JOR"
                    
                for r in prioritized_rules:
                    if r['nombre'] == fallback_name and r['cuenta'] == fallback_acc:
                        matched_concept = r
                        break
                    
        if matched_concept:
            cursor.execute("""
                INSERT INTO gastos_registros (gasto_tipo_id, monto, fecha, descripcion, fuente, fecha_compra)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (matched_concept['id'], monto, fecha, parsed_desc, fuente, fecha_compra))
            inserted_count += 1

# 4. Mark all source files as processed in banks metadata
print("Updating import metadata...")
for source, path in PDFS.items():
    if os.path.exists(path):
        import hashlib
        hasher = hashlib.sha256()
        with open(path, 'rb') as f:
            hasher.update(f.read())
        file_hash = hasher.hexdigest()
        
        db_source_name = "TARJETA_NARANJA" if source == "Tarjeta Naranja" else ("PATAGONIA365" if source == "Patagonia 365" else source.upper().replace(" ", "_"))
        
        cursor.execute("""
            INSERT OR IGNORE INTO bancos_archivos_metadata (hash_archivo, banco, metadata_global)
            VALUES (?, ?, ?)
        """, (file_hash, db_source_name, '{"sincronizado": true}'))

conn.commit()
conn.close()

print(f"Sync complete. Updated: {updated_count} records. Inserted: {inserted_count} new records.")
