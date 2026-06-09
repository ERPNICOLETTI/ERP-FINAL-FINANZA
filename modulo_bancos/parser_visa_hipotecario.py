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

def calculate_sha256(file_path):
    """Calcula el hash SHA-256 del archivo para control de idempotencia."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def procesar_archivo(file_path, force_reprocess=False):
    """
    Parsea el resumen de tarjeta Visa del Banco Hipotecario (Joaquín).
    Filtra consumos de mayo, pesifica USD a 1400 e inserta en la base de datos de Gastos.
    """
    if not os.path.exists(file_path):
        logger.error(f"⚠️ El archivo no existe: {file_path}")
        return False, None

    logger.info(f"💳 Procesando Resumen Visa Hipotecario: {os.path.basename(file_path)}")
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

        # Conexión para crear conceptos necesarios y actualizar palabras clave
        db_path = storage_bancos.DB_PATH
        conn = sqlite3.connect(db_path)
        
        # Crear conceptos minimalistas de tarjeta y ropa si no existen
        conn.execute("INSERT OR IGNORE INTO gastos_tipos (cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave) VALUES ('JOA', 'Ropa', 'EGRESO', '👕', 'rgba(56, 189, 248, 0.2); color: #38bdf8', 'REVOLUTION STORE')")
        conn.execute("INSERT OR IGNORE INTO gastos_tipos (cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave) VALUES ('JOA', 'Tarjeta', 'EGRESO', '💳', 'rgba(56, 189, 248, 0.2); color: #38bdf8', 'IMPUESTO DE SELLOS, INTERESES FINANCIACION, DB IVA, IVA RG, DB.RG')")
        
        # Sincronizar palabras clave específicas
        conn.execute("UPDATE gastos_tipos SET palabras_clave = 'PLANOVALO' WHERE nombre = 'Maverick' AND (palabras_clave IS NULL OR palabras_clave = '')")
        conn.execute("UPDATE gastos_tipos SET palabras_clave = 'SPOTIFY' WHERE nombre = 'Spotify' AND (palabras_clave IS NULL OR palabras_clave = '')")
        conn.execute("UPDATE gastos_tipos SET palabras_clave = 'GEMINI' WHERE nombre = 'GEMINI' AND (palabras_clave IS NULL OR palabras_clave = '')")
        conn.execute("UPDATE gastos_tipos SET palabras_clave = 'CRUNCHYROLL,crunchyro' WHERE nombre = 'Crunchyroll'")
        conn.execute("UPDATE gastos_tipos SET palabras_clave = 'SERVICOOP,PROV SERV PU' WHERE nombre = 'Servicoop' AND cuenta_codigo = 'COMUN'")
        conn.commit()

        # Obtener conceptos actualizados
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
            if t['nombre'] in ["Aportes de Capital", "Impuestos Comerciales", "Gastos Personales"]:
                generic_rules.append(rule)
            else:
                specific_rules.append(rule)
                
        rules = specific_rules + generic_rules

        # Regex para capturar transacciones y montos
        line_re = re.compile(r'^\s*(\d{2})\.(\d{2})\.(\d{2})\s+(?:(\d{6}\*?)\s+)?(.*)$')
        amount_re = re.compile(r'(\d+(?:\.\d{3})*(?:,\d{2}))(-?)\s*(?:_)?\s*$')

        lines = text.split('\n')
        
        # Obtener el período de facturación buscando "CIERRE ACTUAL:"
        billing_period = None
        for line in lines:
            m_cierre = re.search(r'CIERRE\s+ACTUAL:\s*(\d{1,2})\s+([a-zA-ZáéíóúÁÉÍÓÚ]{3,4})\s+(\d{2})', line, re.IGNORECASE)
            if m_cierre:
                day, mon_abbr, year_short = m_cierre.groups()
                mon_lower = mon_abbr.lower()[:3]
                months_map = {
                    'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04', 'may': '05', 'jun': '06',
                    'jul': '07', 'ago': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12'
                }
                month_iso = months_map.get(mon_lower, '05')
                billing_period = f"20{year_short}-{month_iso}"
                break
                
        if not billing_period:
            # Fallback a buscar la fecha de consumo más reciente
            latest_period = None
            for line in lines:
                line_clean = line.strip()
                m = line_re.match(line_clean)
                if m:
                    day, month, year = m.groups()[:3]
                    period = f"20{year}-{month}"
                    if not latest_period or period > latest_period:
                        latest_period = period
            billing_period = latest_period if latest_period else "2026-05"
            
        billing_year, billing_month = billing_period.split('-')

        registros_agregados = 0

        for line in lines:
            line_clean = line.strip()
            m = line_re.match(line_clean)
            if not m:
                continue
                
            day, month, year, comp, rest = m.groups()
            
            # Buscar el importe en la línea
            am = amount_re.search(rest)
            if not am:
                continue
                
            amount_str, minus_sign = am.groups()
            
            # Omitir abonos/pagos de la tarjeta (valores negativos en consumos)
            if minus_sign:
                continue

            # Buscar cuota en la descripción (ej: "Cuota  05/06")
            cuota_match = re.search(r'Cuota\s+(\d+/\d+)', rest, re.IGNORECASE)
            cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""

            # Extraer y limpiar descripción
            amount_pos = rest.rfind(amount_str)
            description = rest[:amount_pos].strip()
            description = re.sub(r'\s+USD\s+\d+,\d+\s*$', '', description)
            description = re.sub(r'\s+Cuota\s+\d+/\d+\s*$', '', description)
            
            # Limpiar importes intermedios o base de impuestos y referencias
            description = re.sub(r'\b\d+(?:\.\d{3})*,\d{2}\s*$', '', description).strip()
            description = re.sub(r'\(\s*\d+(?:\.\d{3})*,\d{2}\s*\)\s*$', '', description).strip()
            description = re.sub(r'\s+\$\s*$', '', description).strip()
            description = re.sub(r'\s+P\s*\$?\s*$', '', description).strip()
            description = re.sub(r'^[\*K\s]+', '', description).strip()
            
            description = description.strip()
            
            # Formatear fecha reemplazando año/mes por el período de facturación para consolidar en el resumen
            date_iso = f"{billing_year}-{billing_month}-{day}"
            
            # Convertir valor de string a float
            val = float(amount_str.replace('.', '').replace(',', '.'))
            
            # Pesificar si es transacción en dólares (tipo de cambio 1400)
            is_usd = "USD" in rest or "DOLARES" in rest or "USD" in line_clean
            if is_usd:
                val = round(val * 1400.0, 2)

            # Clasificar transacción
            matched_concept = None
            desc_lower = description.lower()
            pref_accounts = ["JOA", "COMUN"]
            
            # 1. Intentar clasificar usando el historial de aprendizaje del usuario
            conn_learning = storage_bancos.get_db_connection()
            try:
                matched_concept = storage_gastos.buscar_clasificacion_previa(conn_learning, description, val)
            finally:
                conn_learning.close()
                
            # Evitar contaminación de cuentas personales (ej: de JOR a JOA o viceversa)
            if matched_concept and matched_concept['cuenta'] not in pref_accounts:
                matched_concept = None
                
            if not matched_concept:
                # Filtrar reglas: categorias de tarjeta y personales restringidas al titular y comunas
                # Para reglas específicas (como compras), permitimos de cualquier cuenta para soportar compras cruzadas/aprendizaje
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
                
                # Caso especial: Google USD 19.99 (Gemini)
                if "google" in desc_lower and abs(val - 27986.0) < 10.0:
                    for r in prioritized_rules:
                        if r['nombre'] == "GEMINI":
                            matched_concept = r
                            break

                # Caso especial para ESCO: el más barato (102450) a JOR/ESCO Jorge, los otros a COMUN/ESCO
                if not matched_concept and "esco" in desc_lower:
                    target_name = "ESCO Jorge" if abs(val - 102450.0) < 10.0 else "ESCO"
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

                # Fallback para Google / Instagram USD no clasificados
                if not matched_concept and ("google" in desc_lower or "instagra" in desc_lower):
                    for r in valid_rules:
                        if r['nombre'] == "Gastos Personales" and r['cuenta'] == "JOA":
                            matched_concept = r
                            break
                
                # Fallback general a Gastos Personales (JOA)
                if not matched_concept:
                    for r in valid_rules:
                        if r['nombre'] == "Gastos Personales" and r['cuenta'] == "JOA":
                            matched_concept = r
                            break
            
            # Insertar registro en gastos_registros
            if matched_concept:
                fecha_compra = f"20{year}-{month}-{day}"
                conn_tx = storage_bancos.get_db_connection()
                try:
                    # Buscar coincidencias de monto, fecha y fuente
                    matches = conn_tx.execute(
                        "SELECT id, descripcion, fecha_compra, gasto_tipo_id FROM gastos_registros WHERE monto = ? AND fecha = ? AND fuente = ?",
                        (val, date_iso, "Visa Hipotecario")
                    ).fetchall()
                finally:
                    conn_tx.close()

                exists_tx = False
                for m in matches:
                    if storage_gastos.normalize_desc(m['descripcion']) == storage_gastos.normalize_desc(description):
                        if m['fecha_compra'] == fecha_compra or m['fecha_compra'] == date_iso:
                            # Si es un registro migrado/antiguo, lo actualizamos con la fecha_compra real y la descripcion limpia
                            conn_tx = storage_bancos.get_db_connection()
                            try:
                                conn_tx.execute(
                                    "UPDATE gastos_registros SET fecha_compra = ?, descripcion = ? WHERE id = ?",
                                    (fecha_compra, f"{description}{cuota_str}".strip(), m['id'])
                                )
                                conn_tx.commit()
                            finally:
                                conn_tx.close()
                            exists_tx = True
                            break
                        elif m['fecha_compra'] == fecha_compra:
                            exists_tx = True
                            break

                if exists_tx:
                    logger.info(f"⏭️ Registro de gasto omitido/actualizado (ya existe): {description}{cuota_str} ($ {val}) el {date_iso} (Compra: {fecha_compra})")
                    continue

                storage_gastos.save_gasto_registro({
                    "gasto_tipo_id": matched_concept["id"],
                    "monto": val,
                    "fecha": date_iso,
                    "descripcion": f"{description}{cuota_str}".strip(),
                    "fuente": "Visa Hipotecario",
                    "fecha_compra": fecha_compra
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
                "VISA_HIPOTECARIO", 
                json.dumps({"registros_importados": registros_agregados, "fecha_proceso": f"{billing_year}-{billing_month}-01"}, ensure_ascii=False)
            ))
            conn.commit()
            conn.close()
            
            info = {
                "modulo": "BANCOS",
                "anio": billing_year,
                "mes": billing_month,
                "entidad": "VISA_HIPOTECARIO",
                "db_table": "bancos_movimientos",
                "id_insertado": 0 # Safe dummy ID
            }
            return True, info
            
        # Si no hubo registros agregados nuevos pero se analizó correctamente, también retornamos éxito
        info = {
            "modulo": "BANCOS",
            "anio": billing_year,
            "mes": billing_month,
            "entidad": "VISA_HIPOTECARIO",
            "db_table": "bancos_movimientos",
            "id_insertado": 0
        }
        return True, info
    except Exception as e:
        logger.error(f"❌ Error procesando Visa Hipotecario: {e}")
        return False, None
