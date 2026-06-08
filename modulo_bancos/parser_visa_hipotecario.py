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
            
            # Caso especial: Google USD 19.99 (Gemini)
            if "google" in desc_lower and abs(val - 27986.0) < 10.0:
                for r in rules:
                    if r['nombre'] == "GEMINI":
                        matched_concept = r
                        break
            
            if not matched_concept:
                for r in rules:
                    for kw in r['keywords']:
                        if kw in desc_lower:
                            matched_concept = r
                            break
                    if matched_concept:
                        break
            
            # Fallback para Google / Instagram USD no clasificados
            if not matched_concept and ("google" in desc_lower or "instagra" in desc_lower):
                for r in rules:
                    if r['nombre'] == "Gastos Personales" and r['cuenta'] == "JOA":
                        matched_concept = r
                        break
            
            # Fallback general a Gastos Personales (JOA)
            if not matched_concept:
                for r in rules:
                    if r['nombre'] == "Gastos Personales" and r['cuenta'] == "JOA":
                        matched_concept = r
                        break
            
            # Insertar registro en gastos_registros
            if matched_concept:
                # Comprobar si ya existe el mismo registro para evitar duplicación
                conn_tx = storage_bancos.get_db_connection()
                try:
                    exists_tx = conn_tx.execute(
                        "SELECT 1 FROM gastos_registros WHERE gasto_tipo_id = ? AND monto = ? AND fecha = ? AND descripcion = ? AND fuente = ?",
                        (matched_concept["id"], val, date_iso, f"{description}{cuota_str}", "Visa Hipotecario")
                    ).fetchone()
                finally:
                    conn_tx.close()

                if exists_tx:
                    logger.info(f"⏭️ Registro de gasto omitido (ya existe): {description}{cuota_str} ($ {val}) el {date_iso}")
                    continue

                storage_gastos.save_gasto_registro({
                    "gasto_tipo_id": matched_concept["id"],
                    "monto": val,
                    "fecha": date_iso,
                    "descripcion": f"{description}{cuota_str}",
                    "fuente": "Visa Hipotecario"
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
