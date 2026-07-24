import os
import re
import logging
import hashlib
import json
import pdfplumber
from modulo_tarjetas import storage_tarjetas as storage
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
                
                # Detectar Marca se hará al final sobre el texto acumulado para evitar colisiones
                
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

        # Regex robusta para Neto
        m_neto = re.search(r'A FAVOR DEL COMERCIO\s*\$\s*([\d\.,]+)', text_full)
        if m_neto:
            data["total_neto"] = normalizar_importe(m_neto.group(1))
        else:
            # Fallback para resúmenes mensuales
            m_neto_alt = re.search(r'SALDO\s*\$\s*SALDO\s*U\$S\n([\d\.,]+)', text_full)
            if m_neto_alt:
                data["total_neto"] = normalizar_importe(m_neto_alt.group(1))
            else:
                m_neto_alt2 = re.search(r'SALDO\s*\$\s*.*?\n([\d\.,]+)', text_full)
                if m_neto_alt2:
                    data["total_neto"] = normalizar_importe(m_neto_alt2.group(1))

        # Fallback para Bruto si no se extrajo anteriormente
        if data["total_bruto"] == 0.0:
            m_bruto_alt = re.search(r'TOTAL\s*PRESENTADO\s*\$\s*TOTAL\s*PRESENTADO\s*U\$S\n.*?\n.*?\n([\d\.,]+)', text_full)
            if m_bruto_alt:
                data["total_bruto"] = normalizar_importe(m_bruto_alt.group(1))

        m_est = re.search(r'ESTABLECIMIENTO\s*[:\-\s\?]*\s*(\d+)', text_full, re.IGNORECASE)
        if m_est:
            data["establecimiento"] = m_est.group(1)

        # Determinar marca mediante mapeo estricto de Número de Establecimiento oficial
        est_val = data.get("establecimiento", "")
        if "29271756" in est_val or est_val.endswith("1756"):
            data["marca"] = "MASTERCARD"
        elif "29271707" in est_val or est_val.endswith("1707"):
            data["marca"] = "VISA"
        else:
            # Fallback por texto dominante
            text_upper = text_full.upper()
            count_visa = text_upper.count("VISA")
            count_master = text_upper.count("MASTERCARD") + text_upper.count("MASTER ")
            if count_master > count_visa:
                data["marca"] = "MASTERCARD"
            else:
                data["marca"] = "VISA"

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
            
            # 2.1 Extraer y guardar detalles diarios de la liquidación
            try:
                detalles = []
                # Dividir el texto por bloques de transacción
                bloques = data["texto_completo_ocr"].split("____________________________")
                
                # Obtener año de la fecha de liquidación
                anio_liq = data.get("fecha_liquidacion", "2026")[:4]
                
                for b in bloques:
                    if "Total del" in b:
                        m_fecha = re.search(r'FECHA DE PAGO\s*(\d{2}/\d{2})', b, re.IGNORECASE)
                        fecha_pago = m_fecha.group(1) + f"/{anio_liq}" if m_fecha else data.get("fecha_liquidacion")
                        
                        m_liq = re.search(r'Liq\.\s*N[oº\s]?\s*(\d+)', b, re.IGNORECASE)
                        nro_liq = m_liq.group(1) if m_liq else ""
                        
                        m_lote = re.search(r'Lote\s*N[oº\s]?\s*(\d+)', b, re.IGNORECASE)
                        lote = m_lote.group(1) if m_lote else ""
                        
                        m_totals = re.search(r'Total\s*del\s*d[ií]a\s*\$\s*([\d\.,]+)\s*\$\s*([\d\.,]+)\s*\$\s*([\d\.,]+)', b, re.IGNORECASE)
                        if m_totals:
                            bruto = normalizar_importe(m_totals.group(1))
                            descuentos = normalizar_importe(m_totals.group(2))
                            neto = normalizar_importe(m_totals.group(3))
                            
                            detalles.append({
                                'fecha_pago': fecha_pago,
                                'nro_liq': nro_liq,
                                'lote': lote,
                                'bruto': bruto,
                                'descuentos': descuentos,
                                'neto': neto
                            })
                            
                if detalles:
                    storage.save_liquidacion_detalles(liq_id, detalles)
                    logger.info(f"✨ Se insertaron {len(detalles)} lotes diarios detallados en la liquidación ID {liq_id}")
            except Exception as det_err:
                logger.error(f"⚠️ Error al extraer detalles diarios de liquidación: {det_err}")
            
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
