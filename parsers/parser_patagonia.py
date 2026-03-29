import pdfplumber
import os
import re
import sys

# Motor de Digitalización Total - Patagonia 365 💎🏗️🧱🧠
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import ingesta

def normalizar_importe(texto):
    if not texto: return 0.0
    texto = str(texto).replace("$", "").replace(" ", "").strip()
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."): texto = texto.replace(".", "").replace(",", ".")
        else: texto = texto.replace(",", "")
    elif "," in texto: texto = texto.replace(",", ".")
    try: return float(texto)
    except: return 0.0

def parse_patagonia_365(file_path):
    print(f"💎 DIGITALIZACIÓN 'BIT A BIT' PATAGONIA: {os.path.basename(file_path)}")
    
    header = {"fuente": "PATAGONIA365", "tipo": "MENSUAL", "marca": "PATAGONIA 365"}
    fragmentos = []

    try:
        with pdfplumber.open(file_path) as pdf:
            text_full = ""
            for i, page in enumerate(pdf.pages):
                lines = (page.extract_text() or "").split("\n")
                for line in lines:
                    text_full += line + "\n"
                    # Si la línea tiene contenido real, la guardamos
                    clean_line = line.strip()
                    if len(clean_line) > 5:
                        frag = {
                            "fecha": None,
                            "descripcion": clean_line,
                            "monto_bruto": 0.0,
                            "metadata_raw": {"pagina": i+1, "raw_text": clean_line}
                        }
                        # Detectar si hay números para intentar extraer el neto
                        m_digit = re.findall(r'[\d\.,]+', clean_line)
                        if m_digit:
                            frag["monto_neto"] = normalizar_importe(m_digit[-1])
                        
                        fragmentos.append(frag)

        # Periodo del nombre de archivo
        m_p = re.search(r'(\d{4})(\d{2})', os.path.basename(file_path))
        if m_p:
            header["periodo"] = f"{m_p.group(1)}-{m_p.group(2)}"
            header["fecha_liquidacion"] = f"{m_p.group(1)}-{m_p.group(2)}-01"

        # Totales del Header (Digitalizados)
        m_neto = re.search(r'Importe Neto a Liquidar\s+\$\s*([\d\.,\s]+)', text_full)
        if m_neto: header["total_neto"] = normalizar_importe(m_neto.group(1).replace(" ", ""))
        
        # PERSISTENCIA EN DOS CAPAS
        liq_id = ingesta.persistir_liquidacion(header)
        if liq_id:
            ingesta.persistir_liquidacion_detalle(liq_id, fragmentos)
            print(f"🧱 Éxito: Header ID {liq_id} guardado con {len(fragmentos)} detalles atómicos.")
        
    except Exception as e:
        print(f"Error en Digitalización Patagonia: {e}")

if __name__ == "__main__":
    PDF = r"C:\Users\essao\Downloads\LiqMensual202601.pdf"
    if os.path.exists(PDF):
        parse_patagonia_365(PDF)
