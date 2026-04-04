import pdfplumber
import os
import re
import logging
import hashlib
import json
from . import storage_tarjetas as storage

# Motor de Digitalización de Alta Precisión - Patagonia 365 💎🏗️🧱🧠
# Esta versión implementa el Diseño Híbrido y el archivado legal.

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def calculate_sha256(file_path):
    """Calcula el hash SHA-256 del archivo para el control de idempotencia."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def normalizar_importe(texto):
    """Limpia strings de moneda y los convierte a float."""
    if not texto: return 0.0
    texto = "".join(c for c in str(texto) if c in "0123456789.,-")
    if not texto: return 0.0
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."): texto = texto.replace(".", "").replace(",", ".")
        else: texto = texto.replace(",", "")
    elif "," in texto: texto = texto.replace(",", ".")
    try: return float(texto)
    except: return 0.0

def procesar_archivo(file_path):
    """Función principal (Phase 3): Ingesta el PDF de Patagonia y retorna (success, info)."""
    if not os.path.exists(file_path):
        logger.error(f"⚠️ El archivo no existe: {file_path}")
        return False, None

    logger.info(f"💎 PROCESANDO PATAGONIA (ALTA PRECISIÓN): {os.path.basename(file_path)}")
    file_hash = calculate_sha256(file_path)
    
    header = {
        "fuente": "PATAGONIA365", 
        "tipo": "MENSUAL", 
        "marca": "PATAGONIA 365", 
        "total_bruto": 0.0, 
        "total_neto": 0.0,
        "hash_archivo": file_hash,
        "path_archivo": file_path
    }
    
    text_full = ""
    fragmentos = []

    try:
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                text_full += page_text + "\n"
        
        # Regla Fase 2: Incluir texto completo para Buscador 360
        header["texto_completo_ocr"] = text_full

        # Capture Totales (Alta Precisión)
        m_totales = re.search(r'([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+Monto Presentado', text_full)
        if m_totales:
            header["total_bruto"] = normalizar_importe(m_totales.group(1))
            header["costo_arancel"] = normalizar_importe(m_totales.group(2))
            header["costo_financiero"] = normalizar_importe(m_totales.group(3))
            header["iva_21"] = normalizar_importe(m_totales.group(4))

        m_neto = re.search(r'\$\s*([\d\.,]+)', text_full)
        if m_neto: 
            header["total_neto"] = normalizar_importe(m_neto.group(1))

        m_periodo = re.search(r'Periodo Liquidado:\s+(\d{4}-\d{2})', text_full)
        if m_periodo:
            header["periodo"] = m_periodo.group(1)
            header["fecha_liquidacion"] = f"{m_periodo.group(1)}-01"
        else:
            header["fecha_liquidacion"] = "2026-01-01"

        # 3. Persistencia en Dominio Tarjetas
        liq_id = storage.save_liquidacion(header)
        
        if liq_id:
            info = {
                "modulo": "TARJETAS",
                "anio": header.get("fecha_liquidacion", "2026-01")[:4],
                "mes": header.get("fecha_liquidacion", "2026-01")[5:7],
                "entidad": "PATAGONIA365",
                "db_table": "liquidaciones_tarjetas",
                "id_insertado": liq_id
            }
            return True, info
        else:
            logger.warning(f"🚫 Archivo omitido (Hash existente): {os.path.basename(file_path)}")
            return False, None
        
    except Exception as e:
        logger.error(f"❌ Error crítico procesando Patagonia 365: {e}")
        return False, None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        procesar_archivo(sys.argv[1])
    else:
        logger.warning("Uso: python parser_patagonia.py <absolute_path>")
