import pdfplumber
import os
import re
import sys

# Añadir path raíz para importar core
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
    """
    EXTRACTOR DE DATOS DE PATAGONIA 365 (PDF).
    Su UNICA tarea es leer el archivo y devolver un objeto normalizado.
    """
    print(f"📄 Procesando PDF Patagonia: {os.path.basename(file_path)}")
    data = {"fuente": "PATAGONIA365", "tipo": "MENSUAL", "marca": "PATAGONIA 365"}
    
    try:
        with pdfplumber.open(file_path) as pdf:
            text = "".join(p.extract_text() + "\n" for p in pdf.pages)
        
        # Periodo
        m_p = re.search(r'(\d{4})(\d{2})', os.path.basename(file_path))
        if m_p:
            data["periodo"] = f"{m_p.group(1)}-{m_p.group(2)}"
            data["fecha_liquidacion"] = f"{m_p.group(1)}-{m_p.group(2)}-01"

        # Lógica de extracción de montos
        # (Mejorada para no depender de la DB dentro del parser)
        matches = re.findall(r'\$\s*([\d\.,\s]+)', text)
        if matches:
            for m in reversed(matches):
                val = normalizar_importe(m.replace(" ", ""))
                if val > 1000:
                    data["total_neto"] = val
                    break
        
        # Otros montos por Regex... (omitiendo detalle por brevedad para el ejemplo de orden)
        
        # PASA LOS DATOS AL LADRILLERO (INGESTOR)
        ingesta.persistir_liquidacion(data)
        print("🧱 Ladrillo colocado en la DB con éxito.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    PDF = r"C:\Users\essao\Downloads\LiqMensual202601.pdf"
    if os.path.exists(PDF):
        parse_patagonia_365(PDF)
