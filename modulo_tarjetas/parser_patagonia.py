import pdfplumber
import os
import re
import sys

# Motor de Digitalización de Alta Precisión - Patagonia 365 💎🏗️🧱🧠
# Importación local de Storage (Ownership)
from . import storage_tarjetas as storage
from core_sistema import db_ingesta

def normalizar_importe(texto):
    if not texto: return 0.0
    # Limpiar solo caracteres válidos para números: dígitos, punto y coma
    texto = "".join(c for c in str(texto) if c in "0123456789.,-")
    if not texto: return 0.0
    
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."): texto = texto.replace(".", "").replace(",", ".")
        else: texto = texto.replace(",", "")
    elif "," in texto: texto = texto.replace(",", ".")
    try: return float(texto)
    except: return 0.0

def parse_patagonia_365(file_path):
    print(f"💎 PROCESANDO PATAGONIA (ALTA PRECISIÓN): {os.path.basename(file_path)}")
    
    header = {"fuente": "PATAGONIA365", "tipo": "MENSUAL", "marca": "PATAGONIA 365", "total_bruto": 0.0, "total_neto": 0.0}
    fragmentos = []

    try:
        with pdfplumber.open(file_path) as pdf:
            text_full = ""
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                text_full += page_text + "\n"
                
                lines = page_text.split("\n")
                for line in lines:
                    clean_line = line.strip()
                    if not clean_line: continue
                    
                    # 1. CAPTURA DE LIQUIDACIONES DIARIAS (BITS)
                    # Formato: 07192356 06/02/2026 27/01/2026 74.900,00 2.247,00 5.992,00 0,00 1.101,03 65.559,97
                    m_liq = re.search(r'^(\d{8})\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)$', clean_line)
                    if m_liq:
                        frag = {
                            "fecha": m_liq.group(2),
                            "descripcion": f"Liq {m_liq.group(1)} (Present. {m_liq.group(3)})",
                            "monto_bruto": normalizar_importe(m_liq.group(4)),
                            "arancel": normalizar_importe(m_liq.group(5)),
                            "financiero": normalizar_importe(m_liq.group(6)),
                            "iva": normalizar_importe(m_liq.group(7)),
                            "retenciones": normalizar_importe(m_liq.group(8)),
                            "monto_neto": normalizar_importe(m_liq.group(9)),
                            "metadata_raw": {"nro_liq": m_liq.group(1), "pagina": i+1}
                        }
                        fragmentos.append(frag)
                    else:
                        # Guardamos cualquier otra línea como "ruido útil"
                        fragmentos.append({
                            "fecha": None,
                            "descripcion": clean_line,
                            "monto_bruto": 0.0,
                            "metadata_raw": {"pagina": i+1, "raw_text": clean_line}
                        })

        # 2. CAPTURA DE TOTALES DEL HEADER (ALTA PRECISIÓN)
        # Buscar "664.400,00 19.932,00 57.607,00 0,00 Monto Presentado"
        m_totales = re.search(r'([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+Monto Presentado', text_full)
        if m_totales:
            header["total_bruto"] = normalizar_importe(m_totales.group(1))
            header["costo_arancel"] = normalizar_importe(m_totales.group(2))
            header["costo_financiero"] = normalizar_importe(m_totales.group(3))
            header["iva_21"] = normalizar_importe(m_totales.group(4))

        # Buscar el Neto Final ($ 576.626,54)
        m_neto = re.search(r'\$\s*([\d\.,]+)', text_full)
        if m_neto: 
            header["total_neto"] = normalizar_importe(m_neto.group(1))

        # Buscar el Periodo
        m_periodo = re.search(r'Periodo Liquidado:\s+(\d{4}-\d{2})', text_full)
        if m_periodo:
            header["periodo"] = m_periodo.group(1)
            header["fecha_liquidacion"] = f"{m_periodo.group(1)}-01"

        # 3. PERSISTENCIA MODULAR
        liq_id = storage.save_liquidacion(header)
        if liq_id:
            storage.save_liquidacion_detalle(liq_id, fragmentos)
            print(f"🧱 Éxito: Liquidación Patagonia {header.get('periodo')} digitalizada con {len(fragmentos)} bits.")
            
            # 4. Notificar al Core para actualizar el índice de búsqueda global
            db_ingesta.update_search_index()
        
    except Exception as e:
        print(f"Error procesando Patagonia: {e}")

if __name__ == "__main__":
    import glob
    # Procesar todos los de la carpeta downloads que coincidan
    archivos = glob.glob(r"C:\Users\essao\Downloads\LiqMensual*.pdf")
    for a in archivos:
        parse_patagonia_365(a)
