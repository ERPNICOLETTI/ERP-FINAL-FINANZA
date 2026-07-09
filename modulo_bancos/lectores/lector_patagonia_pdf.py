import os
import re
import hashlib
import json
import logging
import sqlite3
import pdfplumber
from modulo_gastos import storage_gastos
from modulo_bancos import storage_bancos

logger = logging.getLogger(__name__)

MONTHS_MAP = {
    "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AGO": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12"
}

def calculate_sha256(file_path):
    """Calcula el hash SHA-256 del archivo para control de idempotencia."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def procesar_archivo(file_path, force_reprocess=False):
    """
    Parsea el resumen de Tarjeta Patagonia 365 en formato PDF.
    Inserta transacciones e impuestos para la cuenta de Jorgelina (JOR).
    """
    if not os.path.exists(file_path):
        logger.error(f"⚠️ El archivo no existe: {file_path}")
        return False, None

    logger.info(f"💳 Procesando Resumen Patagonia 365 PDF: {os.path.basename(file_path)}")
    file_hash = calculate_sha256(file_path)

    # Control de Idempotencia por hash de archivo
    conn = storage_bancos.get_db_connection()
    exists = conn.execute("SELECT 1 FROM bancos_archivos_metadata WHERE hash_archivo = ?", (file_hash,)).fetchone()
    conn.close()
    
    if exists and not force_reprocess:
        logger.warning(f"🚫 El archivo {os.path.basename(file_path)} ya fue procesado previamente. Ignorando...")
        return False, None

    try:
        # Extraer texto completo del PDF usando pdfplumber debido a fallas de PyPDF2
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"

        # Conexión para obtener la taxonomía
        db_path = storage_bancos.DB_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        tipos = conn.execute("SELECT id, nombre, cuenta_codigo, palabras_clave FROM gastos_tipos").fetchall()
        conn.close()

        # Ordenar reglas (las específicas primero, genéricas al final)
        specific_rules = []
        generic_rules = []
        
        for t in tipos:
            kw_str = t['palabras_clave'] or ""
            keywords = [k.strip().lower() for k in kw_str.split(',') if k.strip()]
            keywords.append(t['nombre'].lower())
            
            rule = {
                "id": t['id'],
                "nombre": t['nombre'],
                "cuenta": t['cuenta_codigo'],
                "keywords": keywords
            }
            if t['nombre'] in ["Aportes de Capital", "Impuestos Comerciales", "Gastos Personales", "Gastos de Vida"]:
                generic_rules.append(rule)
            else:
                specific_rules.append(rule)
                
        rules = specific_rules + generic_rules

        lines = text.split('\n')
        
        # 1. Detectar período de facturación y fecha de cierre
        billing_period = None
        m_cierre = re.search(r'Estado de cuenta:\s*(\d{2})-([A-Za-z]{3})-(\d{2})', text)
        if m_cierre:
            day_c, month_c, year_c = m_cierre.groups()
            month_num = MONTHS_MAP.get(month_c.upper(), "05")
            billing_period = f"20{year_c}-{month_num}"
            
        if not billing_period:
            billing_period = "2026-05" # Fallback
            
        billing_year, billing_month = billing_period.split('-')

        # 2. Procesar líneas
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
                
                # Extraer descripción
                amount_pos = rest.rfind(am.group(0))
                middle = rest[:amount_pos].strip()
                
                # Buscar cuota en la descripción (ej: 5/6 o 16/18)
                cuota_match = re.search(r'\b(\d{1,2}/\d{1,2})\b', middle)
                cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""
                
                # Limpiar
                description = re.sub(r'\b\d{1,2}/\d{1,2}\b', '', middle).strip()
                description = re.sub(r'\b\d{5,}\b', '', description).strip() # Quitar nro de comprobante largo
                
                desc_upper = description.upper()
                # Omitir pagos, saldo anterior y ajustes
                if any(k in desc_upper for k in ["PAGOS", "SU PAGO", "SALDO ANTERIOR", "AJUSTES"]):
                    continue
                    
                # Determinar si es en dólares (columna usd es distinta de 0,00)
                is_usd = usd_str != "0,00"
                amount_val_str = usd_str if is_usd else pesos_str
                
                val = float(amount_val_str.replace('.', '').replace(',', '.'))
                if is_usd:
                    val = round(val * 1400.0, 2)
                    
                # Formatear fecha usando el período de facturación del resumen
                date_iso = f"{billing_year}-{billing_month}-{day}"
                
                month_num = MONTHS_MAP.get(month.upper(), "05")
                fecha_compra = f"20{year}-{month_num}-{day}"
                txs.append({
                    "fecha": date_iso,
                    "descripcion": f"{description}{cuota_str}".strip(),
                    "monto": val,
                    "fecha_compra": fecha_compra
                })

        registros_agregados = 0

        # Filtrar reglas: categorias de tarjeta y personales restringidas al titular y comunas
        # Para reglas específicas (como compras), permitimos de cualquier cuenta para soportar compras cruzadas/aprendizaje
        pref_accounts = ["LDK", "COMUN", "JOR"]
        valid_rules = []
        for r in rules:
            if r['nombre'] in ('Gasto Tarjeta', 'Intereses Tarjeta', 'Tarjeta', 'Gastos Personales', 'Gastos de Vida', 'Aportes de Capital', 'Impuestos Comerciales'):
                if r['cuenta'] in pref_accounts:
                    valid_rules.append(r)
            else:
                valid_rules.append(r)
        
        # Priorizar las reglas específicas del titular y comunas primero
        prioritized_rules = sorted(
            valid_rules,
            key=lambda r: 0 if r['cuenta'] in pref_accounts else 1
        )

        for tx in txs:
            # 1. Intentar clasificar usando el historial de aprendizaje del usuario
            conn_learning = storage_bancos.get_db_connection()
            try:
                matched_concept = storage_gastos.buscar_clasificacion_previa(conn_learning, tx['descripcion'], tx['monto'])
            finally:
                conn_learning.close()
                
            # Evitar contaminación de cuentas personales (ej: de JOA a JOR o viceversa)
            if matched_concept and matched_concept['cuenta'] not in pref_accounts:
                matched_concept = None
                
            if not matched_concept:
                desc_lower = tx['descripcion'].lower()
                # Caso especial para ESCO: el más barato (102450) a JOR/ESCO Jorge, los otros a COMUN/ESCO
                if "esco" in desc_lower:
                    target_name = "ESCO Jorge" if abs(tx['monto'] - 102450.0) < 10.0 else "ESCO"
                    target_cuenta = "JOR" if target_name == "ESCO Jorge" else "COMUN"
                    for r in prioritized_rules:
                        if r['nombre'] == target_name and r['cuenta'] == target_cuenta:
                            matched_concept = r
                            break

                if not matched_concept:
                    # Clasificar según palabras clave (limpiando puntos de abreviaciones)
                    desc_clean = desc_lower.replace('.', '')
                    for r in prioritized_rules:
                        for kw in r['keywords']:
                            kw_clean = kw.replace('.', '')
                            if kw_clean in desc_clean:
                                matched_concept = r
                                break
                        if matched_concept:
                            break
                        
                # Fallback especial para impuestos, percepciones e intereses de tarjeta
                if not matched_concept:
                    desc_clean = desc_lower.replace('.', '')
                    if any(k in desc_clean for k in ["iva", "sello", "percep", "afip", "rg", "sellado", "tasas"]):
                        for r in prioritized_rules:
                            if r['nombre'] in ('Gastos Tarjeta', 'Tarjeta') and r['cuenta'] in pref_accounts:
                                matched_concept = r
                                break
                    elif any(k in desc_clean for k in ["interes", "financia"]):
                        for r in prioritized_rules:
                            if r['nombre'] in ('Intereses Tarjeta', 'Tarjeta') and r['cuenta'] in pref_accounts:
                                matched_concept = r
                                break

                # Fallback general a Gastos de Vida (JOR)
                if not matched_concept:
                    for r in valid_rules:
                        if r['nombre'] == "Gastos de Vida" and r['cuenta'] == "JOR":
                            matched_concept = r
                            break
                            
                # Fallback definitivo
                if not matched_concept and valid_rules:
                    for r in valid_rules:
                        if r['cuenta'] == "JOR":
                            matched_concept = r
                            break
 
            if matched_concept:
                tx_fecha_compra = tx.get('fecha_compra') or tx['fecha']
                # Comprobar si ya existe el mismo registro para evitar duplicados
                conn_tx = storage_bancos.get_db_connection()
                try:
                    matches = conn_tx.execute(
                        "SELECT id, descripcion, fecha_compra, gasto_tipo_id FROM gastos_registros WHERE monto = ? AND fecha = ? AND fuente = ?",
                        (tx['monto'], tx['fecha'], "Patagonia 365")
                    ).fetchall()
                finally:
                    conn_tx.close()

                exists_tx = False
                for m in matches:
                    if storage_gastos.normalize_desc(m['descripcion']) == storage_gastos.normalize_desc(tx['descripcion']):
                        if m['fecha_compra'] == tx_fecha_compra or m['fecha_compra'] == tx['fecha']:
                            # Si es un registro migrado/antiguo, lo actualizamos con la fecha_compra real y la descripcion limpia
                            conn_tx = storage_bancos.get_db_connection()
                            try:
                                conn_tx.execute(
                                    "UPDATE gastos_registros SET fecha_compra = ?, descripcion = ? WHERE id = ?",
                                    (tx_fecha_compra, tx['descripcion'], m['id'])
                                )
                                conn_tx.commit()
                            finally:
                                conn_tx.close()
                            exists_tx = True
                            break
                        elif m['fecha_compra'] == tx_fecha_compra:
                            exists_tx = True
                            break

                if exists_tx:
                    logger.info(f"⏭️ Registro de gasto omitido/actualizado (ya existe): {tx['descripcion']} ($ {tx['monto']}) el {tx['fecha']} (Compra: {tx_fecha_compra})")
                    continue
 
                storage_gastos.save_gasto_registro({
                    "gasto_tipo_id": matched_concept["id"],
                    "monto": tx['monto'],
                    "fecha": tx['fecha'],
                    "descripcion": tx['descripcion'],
                    "fuente": "Patagonia 365",
                    "fecha_compra": tx.get('fecha_compra') or tx['fecha']
                })
                registros_agregados += 1

        # Registrar metadatos del archivo procesado para idempotencia
        if registros_agregados > 0:
            conn = storage_bancos.get_db_connection()
            conn.execute('''
                INSERT OR IGNORE INTO bancos_archivos_metadata (hash_archivo, banco, metadata_global)
                VALUES (?, ?, ?)
            ''', (
                file_hash, 
                "PATAGONIA365", 
                json.dumps({"registros_importados": registros_agregados, "fecha_proceso": f"{billing_year}-{billing_month}-01"}, ensure_ascii=False)
            ))
            conn.commit()
            conn.close()
            
        info = {
            "modulo": "BANCOS",
            "anio": billing_year,
            "mes": billing_month,
            "entidad": "PATAGONIA365",
            "db_table": "bancos_movimientos",
            "id_insertado": 0
        }
        return True, info
    except Exception as e:
        logger.error(f"❌ Error procesando Patagonia 365 PDF: {e}")
        return False, None
