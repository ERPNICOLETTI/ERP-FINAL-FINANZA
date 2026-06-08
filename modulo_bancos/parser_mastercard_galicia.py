import os
import re
import hashlib
import json
import logging
import sqlite3
import PyPDF2
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
    Parsea el resumen de tarjeta Mastercard de Banco Galicia.
    Separa consumos entre Jorgelina (JOR) y Joaquín (JOA) dinámicamente.
    Extrae consumos e inserta en la base de datos de Gastos.
    """
    if not os.path.exists(file_path):
        logger.error(f"⚠️ El archivo no existe: {file_path}")
        return False, None

    logger.info(f"💳 Procesando Resumen Mastercard Galicia: {os.path.basename(file_path)}")
    file_hash = calculate_sha256(file_path)

    # Control de Idempotencia por hash de archivo
    conn = storage_bancos.get_db_connection()
    exists = conn.execute("SELECT 1 FROM bancos_archivos_metadata WHERE hash_archivo = ?", (file_hash,)).fetchone()
    conn.close()
    
    if exists and not force_reprocess:
        logger.warning(f"🚫 El archivo {os.path.basename(file_path)} ya fue procesado previamente. Ignorando...")
        return False, None

    try:
        # Extraer texto completo del PDF
        text = ""
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"

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
        
        # 1. Detectar período de facturación buscando la fecha de emisión en la cabecera
        billing_period = None
        for line in lines:
            m_cierre = re.search(r'\b(20\d{2})(\d{2})\d{2}', line)
            if m_cierre:
                year, month = m_cierre.groups()
                billing_period = f"{year}-{month}"
                break
                
        if not billing_period:
            billing_period = "2026-05" # Fallback
            
        billing_year, billing_month = billing_period.split('-')

        # 2. Procesar líneas y separar por bloques de tarjeta JOR/JOA
        line_re = re.compile(r'^(\d{2})-([A-Za-z]{3})-(\d{2})\s+(.*)$')
        amount_re = re.compile(r'(-?)(\d+(?:\.\d{3})*,?\d{2})\s*$')
        
        blocks = []
        current_txs = []

        for line in lines:
            line_clean = line.strip('\r\n') # Mantener espacios finales para detectar si es USD
            m = line_re.match(line_clean.strip())
            
            if m:
                day, month, year, rest = m.groups()
                
                am = amount_re.search(rest)
                if not am:
                    continue
                    
                minus_sign, amount_str = am.groups()
                if minus_sign: # Omitir pagos/abonos de la tarjeta
                    continue
                    
                amount_pos = rest.rfind(amount_str)
                middle = rest[:amount_pos].strip()
                
                # Limpiar importes de cuotas intermedios o basura
                middle = re.sub(r'-\s*$', '', middle).strip()
                middle = re.sub(r'\d+(?:\.\d{3})*,\d{2}\s*$', '', middle).strip()
                
                # Buscar cuota en la descripción
                cuota_match = re.search(r'\b(\d{2}/\d{2})\b', middle)
                cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""
                
                # Limpiar descripción
                description = re.sub(r'\b\d{2}/\d{2}\b', '', middle).strip()
                
                # Determinar si es USD (no termina con dos espacios o tiene indicador de moneda extranjera)
                is_usd = bool(re.search(r'\([A-Z]{3},', line_clean)) or not line_clean.endswith('  ')
                
                # Limpiar referencias de moneda extranjera e importes entre paréntesis
                description = re.sub(r'\([A-Z]{3},[^)]+\)', '', description).strip()
                description = re.sub(r'\b\d{5,}\b', '', description).strip() # Quitar nro comprobante
                description = re.sub(r'\s+\$\s*$', '', description).strip() # Quitar signo pesos sobrante
                
                # Formatear fecha usando el período de facturación del resumen
                date_iso = f"{billing_year}-{billing_month}-{day}"
                
                # Convertir valor
                val = float(amount_str.replace('.', '').replace(',', '.'))
                if is_usd:
                    val = round(val * 1400.0, 2)
                    
                month_num = MONTHS_MAP.get(month.upper(), "05")
                fecha_compra = f"20{year}-{month_num}-{day}"
                current_txs.append({
                    "fecha": date_iso,
                    "descripcion": f"{description}{cuota_str}".strip(),
                    "monto": val,
                    "is_usd": is_usd,
                    "fecha_compra": fecha_compra
                })
                
            elif "SUBTOTAL" in line_clean and current_txs:
                # El primer subtotal pertenece a JOR (Jorgelina)
                blocks.append(("JOR", current_txs))
                current_txs = []
                
            elif "TOTAL ADICIONAL DE NICOLETTI,JOAQUIN" in line_clean and current_txs:
                # El subtotal del adicional de Joaquín
                blocks.append(("JOA", current_txs))
                current_txs = []

        registros_agregados = 0

        # 3. Clasificar e insertar en la base de datos
        for owner, txs in blocks:
            # Filtrar reglas: categorias de tarjeta y personales restringidas al titular y comunas
            # Para reglas específicas (como compras), permitimos de cualquier cuenta para soportar compras cruzadas/aprendizaje
            pref_accounts = ['LDK', 'COMUN', 'JOR'] if owner == 'JOR' else ['JOA', 'COMUN']
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
                matched_concept = None
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
                    # Clasificar según palabras clave
                    for r in prioritized_rules:
                        for kw in r['keywords']:
                            if kw in desc_lower:
                                matched_concept = r
                                break
                        if matched_concept:
                            break
                        
                # Fallback general
                if not matched_concept:
                    fallback_name = "Gastos de Vida" if owner == "JOR" else "Gastos Personales"
                    for r in valid_rules:
                        if r['nombre'] == fallback_name and r['cuenta'] == owner:
                            matched_concept = r
                            break
                            
                # Fallback definitivo en caso de que no encuentre la categoría por nombre
                if not matched_concept and valid_rules:
                    for r in valid_rules:
                        if r['cuenta'] == owner:
                            matched_concept = r
                            break
                            
                if matched_concept:
                    # Comprobar si ya existe el mismo registro para evitar duplicados
                    conn_tx = storage_bancos.get_db_connection()
                    try:
                        exists_tx = conn_tx.execute(
                            "SELECT 1 FROM gastos_registros WHERE monto = ? AND fecha = ? AND descripcion = ? AND fuente = ? AND fecha_compra = ?",
                            (tx['monto'], tx['fecha'], tx['descripcion'], "Mastercard Galicia", tx['fecha_compra'])
                        ).fetchone()
                    finally:
                        conn_tx.close()

                    if exists_tx:
                        logger.info(f"⏭️ Registro de gasto omitido (ya existe): {tx['descripcion']} ($ {tx['monto']}) el {tx['fecha']} (Compra: {tx['fecha_compra']})")
                        continue

                    storage_gastos.save_gasto_registro({
                        "gasto_tipo_id": matched_concept["id"],
                        "monto": tx['monto'],
                        "fecha": tx['fecha'],
                        "descripcion": tx['descripcion'],
                        "fuente": "Mastercard Galicia",
                        "fecha_compra": tx['fecha_compra']
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
                "MASTERCARD_GALICIA", 
                json.dumps({"registros_importados": registros_agregados, "fecha_proceso": f"{billing_year}-{billing_month}-01"}, ensure_ascii=False)
            ))
            conn.commit()
            conn.close()
            
        info = {
            "modulo": "BANCOS",
            "anio": billing_year,
            "mes": billing_month,
            "entidad": "MASTERCARD_GALICIA",
            "db_table": "bancos_movimientos",
            "id_insertado": 0
        }
        return True, info
    except Exception as e:
        logger.error(f"❌ Error procesando Mastercard Galicia: {e}")
        return False, None
