import os
import re
import logging
import hashlib
import json
import pdfplumber
from . import storage_tarjetas as storage
from modulo_compras import storage_compras

# PARSER PAYWAY PDF - PoC Arquitectura Híbrida 💳🏗️🧠
# Extrae liquidaciones mensuales/diarias de Prisma/Payway.

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
    s = "".join(c for c in str(texto) if c in "0123456789.,-")
    if not s: return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."): s = s.replace(".", "").replace(",", ".")
        else: s = s.replace(",", "")
    elif "," in s: s = s.replace(",", ".")
    try: return float(s)
    except: return 0.0

def extraer_datos_payway(file_path):
    """Extrae datos granulares de PDFs de Prisma/Payway."""
    logger.info(f"📂 Procesando archivo: {os.path.basename(file_path)}")
    
    # Estructura inicial (Columnas Duras + Metadata en un solo dict)
    data = {
        "fuente": "PAYWAY",
        "tipo": "MENSUAL",
        "marca": "DESCONOCIDA",
        "total_bruto": 0.0,
        "costo_arancel": 0.0,
        "costo_financiero": 0.0,
        "iva_21": 0.0,
        "iva_105": 0.0,
        "retenciones": 0.0,
        "total_neto": 0.0,
        "hash_archivo": calculate_sha256(file_path),
        "establecimiento": "SIN_IDENTIFICAR",
        "path_archivo": file_path
    }
    
    text_full = ""
    ultimo_arancel = 0.0
    
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_full += page_text + "\n"
                
                # Detectar Marca (VISA/MASTER)
                if "VISA" in page_text.upper(): data["marca"] = "VISA"
                elif "MASTERCARD" in page_text.upper() or "MASTER" in page_text.upper(): data["marca"] = "MASTERCARD"
                
                for line in page_text.split("\n"):
                    # 1. Capturar Aranceles
                    m_arancel = re.search(r'Arancel\s*\$\s*([\d\.,]+)', line)
                    if m_arancel:
                        monto = normalizar_importe(m_arancel.group(1))
                        data["costo_arancel"] += monto
                        ultimo_arancel = monto
                        continue

                    # 2. Capturar Deducciones x Proximidad
                    m_deduc = re.search(r'Deduc\.Impositivas\s*\$\s*([\d\.,]+)', line)
                    if m_deduc and ultimo_arancel > 0:
                        monto_deduc = normalizar_importe(m_deduc.group(1))
                        tasa = monto_deduc / (ultimo_arancel if ultimo_arancel != 0 else 1)
                        if abs(tasa - 0.21) < 0.05: data["iva_21"] += monto_deduc
                        elif abs(tasa - 0.105) < 0.05: data["iva_105"] += monto_deduc
                        else: data["retenciones"] += monto_deduc
                        ultimo_arancel = 0 
                        continue

                    # 3. Ventas Brutas
                    m_venta = re.search(r'Venta Tj\..*?\$\s*([\d\.,]+)', line)
                    if m_venta:
                        data["total_bruto"] += normalizar_importe(m_venta.group(1))

        # --- Extracción de Resumen Final (Verdad Absoluta) ---
        resumen_iva_21 = re.findall(r'IVA\s*\(?21,00%?\)?\s*:?\s*\$\s*([\d\.,]+)', text_full)
        if resumen_iva_21:
            data["iva_21"] = sum(normalizar_importe(val) for val in resumen_iva_21)

        resumen_iva_105 = re.findall(r'IVA\s*\(?10,50%?\)?\s*:?\s*\$\s*([\d\.,]+)', text_full)
        if resumen_iva_105:
            data["iva_105"] = sum(normalizar_importe(val) for val in resumen_iva_105)

        # Fecha y Neto
        m_emision = re.search(r'FECHA DE EMISION:\s*(\d{2}/\d{2}/\d{4})', text_full)
        if m_emision:
            data["fecha_liquidacion"] = re.sub(r'(\d{2})/(\d{2})/(\d{4})', r'\3-\2-\1', m_emision.group(1))
            data["periodo"] = data["fecha_liquidacion"][:7]

        m_neto = re.search(r'A FAVOR DEL COMERCIO\s*\$\s*([\d\.,]+)', text_full)
        if m_neto:
            data["total_neto"] = normalizar_importe(m_neto.group(1))

        m_est = re.search(r'Nro\. Establecimiento:\s*(\d+)', text_full)
        if m_est:
            data["establecimiento"] = m_est.group(1)

        # Regla Fase 2: Incluir texto completo para Buscador 360 (Diseño Híbrido)
        data["texto_completo_ocr"] = text_full

        return data
        
    except Exception as e:
        logger.error(f"❌ Error extrayendo datos del PDF: {e}")
        return None

def procesar_archivo(filepath):
    """Función principal (Phase 3): Orquesta la ingesta híbrida del archivo."""
    if not os.path.exists(filepath):
        logger.error(f"⚠️ El archivo no existe: {filepath}")
        return False, None

    try:
        # 1. Extracción (Híbrida: Columnas Duras + Metadata + OCR)
        data = extraer_datos_payway(filepath)
        if not data:
            return False, None

        # 2. Persistencia en Dominio Tarjetas (Modular)
        liq_id = storage.save_liquidacion(data)
        
        if liq_id:
            logger.info(f"✨ Liquidación {data['marca']} guardada con ID: {liq_id}")
            
            # 3. Registro de Impuestos (Cross-Module Service)
            if data["iva_21"] > 0 or data["iva_105"] > 0:
                storage_compras.registrar_impuesto({
                    "modulo": "TARJETAS",
                    "fuente": "PAYWAY",
                    "fecha": data.get("fecha_liquidacion"),
                    "neto_gravado": data.get("costo_arancel", 0),
                    "iva_21": data["iva_21"],
                    "iva_105": data["iva_105"],
                    "descripcion": f"Liq. Payway {data['marca']} - Per: {data.get('periodo')}",
                    "extern_id": liq_id,
                    "hash_archivo": data["hash_archivo"]
                })
            
            # Retornar Tupla (success, info) para el Orquestador/Archivador
            info = {
                "modulo": "TARJETAS",
                "anio": data.get("fecha_liquidacion", "0000-00-00")[:4],
                "mes": data.get("fecha_liquidacion", "0000-00-00")[5:7],
                "entidad": "PAYWAY",
                "db_table": "liquidaciones_tarjetas", # Cabecera
                "id_insertado": liq_id
            }
            return True, info
        else:
            logger.warning(f"🚫 Archivo omitido (posible duplicado de hash): {os.path.basename(filepath)}")
            return False, None

    except Exception as e:
        logger.error(f"❌ Error crítico en el procesamiento de: {filepath}. Motivo: {e}")
        return False, None

if __name__ == "__main__":
    # Prueba de concepto manual
    import sys
    if len(sys.argv) > 1:
        procesar_archivo(sys.argv[1])
    else:
        logger.warning("Uso: python parser_payway_liq.py <absolute_path>")
