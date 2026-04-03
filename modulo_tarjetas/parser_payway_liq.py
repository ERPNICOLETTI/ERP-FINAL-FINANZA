import pandas as pd
import os
import sys
import re
import pdfplumber

# Importación local de Storage (Ownership) 💳🧱🧠
from . import storage_tarjetas as storage
from core_sistema import db_ingesta, checksum_service
from modulo_compras import storage_compras

def normalizar_importe(texto):
    if not texto: return 0.0
    s = "".join(c for c in str(texto) if c in "0123456789.,-")
    if not s: return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."): s = s.replace(".", "").replace(",", ".")
        else: s = s.replace(",", "")
    elif "," in s: s = s.replace(",", ".")
    try: return float(s)
    except: return 0.0

def parse_payway_pdf(file_path):
    """Especialista en extraer datos granulares de PDFs de Prisma/Payway."""
    print(f"🔍 [PAYWAY-PDF] Analizando con 'Ojo Fiscal' Granular: {os.path.basename(file_path)}")
    
    header = {
        "fuente": "PAYWAY", "tipo": "MENSUAL", "marca": "DESCONOCIDA",
        "total_bruto": 0.0, "total_neto": 0.0,
        "iva_21": 0.0, "iva_105": 0.0, "arancel": 0.0,
        "retenciones": 0.0, "costo_financiero": 0.0
    }
    
    fragmentos = []
    ultimo_arancel = 0.0
    text_full = ""
    
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_full += page_text + "\n"
            
            # Detectar Marca (VISA/MASTER)
            if "VISA" in page_text.upper(): header["marca"] = "VISA"
            elif "MASTERCARD" in page_text.upper() or "MASTER" in page_text.upper(): header["marca"] = "MASTER"
            
            for line in page_text.split("\n"):
                # 1. Capturar Aranceles
                m_arancel = re.search(r'Arancel\s*\$\s*([\d\.,]+)', line)
                if m_arancel:
                    monto = normalizar_importe(m_arancel.group(1))
                    header["arancel"] += monto
                    ultimo_arancel = monto
                    continue

                # 2. Capturar Deducciones x Proximidad
                m_deduc = re.search(r'Deduc\.Impositivas\s*\$\s*([\d\.,]+)', line)
                if m_deduc and ultimo_arancel > 0:
                    monto_deduc = normalizar_importe(m_deduc.group(1))
                    tasa = monto_deduc / ultimo_arancel
                    if abs(tasa - 0.21) < 0.05: header["iva_21"] += monto_deduc
                    elif abs(tasa - 0.105) < 0.05: header["iva_105"] += monto_deduc
                    else: header["retenciones"] += monto_deduc
                    ultimo_arancel = 0 # Consumir
                    continue

                # 3. Ventas Brutas
                m_venta = re.search(r'Venta Tj\..*?\$\s*([\d\.,]+)', line)
                if m_venta:
                    header["total_bruto"] += normalizar_importe(m_venta.group(1))

    # --- MOTOR DE RESUMEN FINAL (PRECISIÓN TOTAL) ---
    # Buscamos la tabla de cierre mencionada por el usuario
    resumen_iva_21 = re.findall(r'IVA\s*\(?21,00%?\)?\s*:?\s*\$\s*([\d\.,]+)', text_full)
    if resumen_iva_21:
        # Si hay un resumen al final, lo tomamos como la Verdad Absoluta (sumamos todas las ocurrencias si hay varias liquidaciones)
        header["iva_21"] = sum(normalizar_importe(val) for val in resumen_iva_21)

    resumen_iva_105 = re.findall(r'IVA\s*\(?10,50%?\)?\s*:?\s*\$\s*([\d\.,]+)', text_full)
    if resumen_iva_105:
        header["iva_105"] = sum(normalizar_importe(val) for val in resumen_iva_105)

    # Extraer Fecha y Neto
    m_emision = re.search(r'FECHA DE EMISION:\s*(\d{2}/\d{2}/\d{4})', text_full)
    if m_emision:
        header["fecha_liquidacion"] = pd.to_datetime(m_emision.group(1), dayfirst=True).strftime('%Y-%m-%d')
        header["periodo"] = header["fecha_liquidacion"][:7]

    m_neto = re.search(r'A FAVOR DEL COMERCIO\s*\$\s*([\d\.,]+)', text_full)
    if m_neto:
        header["total_neto"] = normalizar_importe(m_neto.group(1))

    return header, fragmentos

def parse_payway_liq(file_path):
    """Orquesta la ingesta con control de duplicados (Checksum)."""
    es_nuevo, hash_val = checksum_service.validar_y_registrar("TARJETAS", "FILE", os.path.basename(file_path), file_path)
    if not es_nuevo:
        print(f"🚫 [HASH] Archivo ya procesado anteriormente: {os.path.basename(file_path)}")
        return False
    
    try:
        header, fragmentos = parse_payway_pdf(file_path)
        liq_id = storage.save_liquidacion(header)
        
        if liq_id:
            # Reporte Fiscal Segregado
            if header["iva_21"] > 0:
                storage_compras.registrar_impuesto({
                    "modulo": "TARJETAS", "fuente": "PAYWAY", "fecha": header.get("fecha_liquidacion"),
                    "neto_gravado": header.get("arancel", 0), "iva_105": 0, "iva_21": header["iva_21"],
                    "descripcion": f"Comisión Payway (21%) - {header['marca']} {header.get('periodo')}",
                    "extern_id": liq_id
                })
            if header["iva_105"] > 0:
                storage_compras.registrar_impuesto({
                    "modulo": "TARJETAS", "fuente": "PAYWAY", "fecha": header.get("fecha_liquidacion"),
                    "neto_gravado": 0, "iva_105": header["iva_105"], "iva_21": 0,
                    "descripcion": f"Comisión Payway (10.5%) - {header['marca']} {header.get('periodo')}",
                    "extern_id": liq_id
                })
            print(f"✨ Éxito: Liquidación {header['marca']} ingresada con precisión del 10.5% y 21%.")
            return True
    except Exception as e:
        print(f"❌ Error en Parser Payway: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parse_payway_liq(sys.argv[1])
    else:
        print("⚠️ Uso: python parser_payway_liq.py <file_path>")
