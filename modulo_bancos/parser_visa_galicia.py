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
    Parsea el resumen de tarjeta Visa de Banco Galicia (Jorgelina).
    Extrae consumos e inserta en la base de datos de Gastos (cuenta JOR).
    """
    if not os.path.exists(file_path):
        logger.error(f"⚠️ El archivo no existe: {file_path}")
        return False, None

    logger.info(f"💳 Procesando Resumen Visa Galicia: {os.path.basename(file_path)}")
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

        # Regex para capturar transacciones y montos
        line_re = re.compile(r'^(\d{2})-(\d{2})-(\d{2})\s+(.*)$')
        amount_re = re.compile(r'(-?)(\d+(?:\.\d{3})*,?\d{2})\s*$')

        lines = text.split('\n')
        
        # Obtener el período de facturación buscando la fecha de cierre del resumen
        billing_period = None
        for line in lines:
            # Galicia Visa usualmente tiene un string YYYYMMDD cerca de la pagina 1
            m_cierre = re.search(r'\b(20\d{2})(\d{2})\d{2}\b', line)
            if m_cierre:
                year, month = m_cierre.groups()
                billing_period = f"{year}-{month}"
                break
                
        if not billing_period:
            billing_period = "2026-05" # Fallback
            
        billing_year, billing_month = billing_period.split('-')

        registros_agregados = 0

        for line in lines:
            line_clean = line.strip()
            m = line_re.match(line_clean)
            if not m:
                continue
                
            day, month, year, rest = m.groups()
            
            # Buscar el importe en la línea
            am = amount_re.search(rest)
            if not am:
                continue
                
            minus_sign, amount_str = am.groups()
            
            # Omitir abonos/pagos de la tarjeta (valores negativos en consumos)
            if minus_sign:
                continue

            amount_pos = rest.rfind(amount_str)
            middle = rest[:amount_pos].strip()
            
            # Limpiar importes intermedios de impuestos
            middle = re.sub(r'-\s*$', '', middle).strip()
            middle = re.sub(r'\d+(?:\.\d{3})*,\d{2}\s*$', '', middle).strip()

            # Buscar cuota en la descripción (ej: "05/06")
            cuota_match = re.search(r'\b(\d{2}/\d{2})\b', middle)
            cuota_str = f" {cuota_match.group(1)}" if cuota_match else ""

            # Extraer y limpiar descripción
            description = re.sub(r'\b\d{2}/\d{2}\b', '', middle).strip()
            description = re.sub(r'\b\d{6,}\b\s*$', '', description).strip() # Quitar números de referencia largos
            description = re.sub(r'^(\*|K)\*?', '', description).strip() # Limpiar prefijo de tarjeta JOR
            description = re.sub(r'\s+\$\s*$', '', description).strip() # Quitar signo pesos sobrante
            
            # Formatear fecha de la transacción usando el período de facturación del resumen
            date_iso = f"{billing_year}-{billing_month}-{day}"
            
            # Convertir valor de string a float
            val = float(amount_str.replace('.', '').replace(',', '.'))
            
            # Clasificar transacción
            matched_concept = None
            desc_lower = description.lower()
            
            # Filtrar reglas: categorias de tarjeta y personales restringidas al titular y comunas
            # Para reglas específicas (como compras), permitimos de cualquier cuenta para soportar compras cruzadas/aprendizaje
            pref_accounts = ["JOR", "COMUN", "LDK"]
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
            
            # Caso especial para ESCO: el más barato (102450) a JOR/ESCO Jorge, los otros a COMUN/ESCO
            if "esco" in desc_lower:
                target_name = "ESCO Jorge" if abs(val - 102450.0) < 10.0 else "ESCO"
                target_cuenta = "JOR" if target_name == "ESCO Jorge" else "COMUN"
                for r in prioritized_rules:
                    if r['nombre'] == target_name and r['cuenta'] == target_cuenta:
                        matched_concept = r
                        break
            
            if not matched_concept:
                # Intentar clasificar según palabras clave de las categorías
                for r in prioritized_rules:
                    for kw in r['keywords']:
                        if kw in desc_lower:
                            matched_concept = r
                            break
                    if matched_concept:
                        break
            
            # Fallback general a Gastos de Vida (JOR)
            if not matched_concept:
                for r in valid_rules:
                    if r['nombre'] == "Gastos de Vida" and r['cuenta'] == "JOR":
                        matched_concept = r
                        break
            
            # Insertar registro en gastos_registros
            if matched_concept:
                # Comprobar si ya existe el mismo registro para evitar duplicación
                fecha_compra = f"20{year}-{month}-{day}"
                conn_tx = storage_bancos.get_db_connection()
                try:
                    exists_tx = conn_tx.execute(
                        "SELECT 1 FROM gastos_registros WHERE monto = ? AND fecha = ? AND descripcion = ? AND fuente = ? AND fecha_compra = ?",
                        (val, date_iso, f"{description}{cuota_str}".strip(), "Visa Galicia", fecha_compra)
                    ).fetchone()
                finally:
                    conn_tx.close()

                if exists_tx:
                    logger.info(f"⏭️ Registro de gasto omitido (ya existe): {description}{cuota_str} ($ {val}) el {date_iso} (Compra: {fecha_compra})")
                    continue

                storage_gastos.save_gasto_registro({
                    "gasto_tipo_id": matched_concept["id"],
                    "monto": val,
                    "fecha": date_iso,
                    "descripcion": f"{description}{cuota_str}".strip(),
                    "fuente": "Visa Galicia",
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
                "VISA_GALICIA", 
                json.dumps({"registros_importados": registros_agregados, "fecha_proceso": f"{billing_year}-{billing_month}-01"}, ensure_ascii=False)
            ))
            conn.commit()
            conn.close()
            
        info = {
            "modulo": "BANCOS",
            "anio": billing_year,
            "mes": billing_month,
            "entidad": "VISA_GALICIA",
            "db_table": "bancos_movimientos",
            "id_insertado": 0
        }
        return True, info
    except Exception as e:
        logger.error(f"❌ Error procesando Visa Galicia: {e}")
        return False, None
