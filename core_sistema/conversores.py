import os
import json
import pandas as pd
import pdfplumber

# CORE SISTEMA - CONVERSORES DE FORMATO DE INGESTA 🧠🔄📄

def convertir_pdf_a_markdown(filepath):
    """
    Lee un archivo PDF usando pdfplumber y extrae su texto en formato Markdown,
    intentando conservar la estructura de tablas si están presentes.
    """
    markdown_content = []
    
    with pdfplumber.open(filepath) as pdf:
        for i, page in enumerate(pdf.pages):
            markdown_content.append(f"\n## Página {i + 1}\n")
            
            # Intentar extraer tablas
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    if not table: continue
                    # Filtrar filas vacías
                    table = [row for row in table if any(cell is not None for cell in row)]
                    if not table: continue
                    
                    # Crear tabla de markdown
                    headers = [str(cell or "").strip().replace("\n", " ") for cell in table[0]]
                    markdown_content.append("| " + " | ".join(headers) + " |")
                    markdown_content.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    
                    for row in table[1:]:
                        cells = [str(cell or "").strip().replace("\n", " ") for cell in row]
                        # Rellenar celdas faltantes si la fila es corta
                        if len(cells) < len(headers):
                            cells += [""] * (len(headers) - len(cells))
                        elif len(cells) > len(headers):
                            cells = cells[:len(headers)]
                        markdown_content.append("| " + " | ".join(cells) + " |")
                    markdown_content.append("") # Línea vacía después de la tabla
            
            # Extraer el texto normal (excluyendo lo que ya se pudo estructurar)
            text = page.extract_text()
            if text:
                markdown_content.append(text)
                
    # Extraer texto limpio usando pypdf como resguardo para PDFs con capas superpuestas (evita scrambling)
    try:
        import pypdf
        reader = pypdf.PdfReader(filepath)
        pypdf_text = []
        for page_idx, page in enumerate(reader.pages):
            t = page.extract_text()
            if t:
                pypdf_text.append(f"\n## Texto Limpio (Página {page_idx + 1})\n")
                pypdf_text.append(t)
        if pypdf_text:
            markdown_content.append("\n" + "\n".join(pypdf_text))
    except Exception as e:
        pass
        
    # Si el texto acumulado es demasiado corto, es probable que sea un PDF escaneado. Aplicamos OCR.
    import re
    texto_plano_acumulado = "".join(markdown_content)
    letras_y_num = re.sub(r'[^a-zA-Z0-9]', '', texto_plano_acumulado)
    if len(letras_y_num) < 50:
        try:
            import pypdfium2 as pdfium
            import pytesseract
            from PIL import Image
            
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            tessdata_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'tessdata'))
            os.environ['TESSDATA_PREFIX'] = tessdata_dir
            
            doc = pdfium.PdfDocument(filepath)
            try:
                ocr_text = []
                # Procesamos máximo las primeras 3 páginas para optimizar rendimiento
                for page_idx in range(min(len(doc), 3)):
                    page = doc[page_idx]
                    bitmap = page.render(scale=2)
                    pil_img = bitmap.to_pil()
                    text_page = pytesseract.image_to_string(pil_img, lang='spa+eng')
                    if text_page.strip():
                        ocr_text.append(f"\n## Texto OCR (Página {page_idx + 1})\n")
                        ocr_text.append(text_page)
                
                if ocr_text:
                    markdown_content.append("\n".join(ocr_text))
            finally:
                doc.close()
        except Exception as e:
            # Silencioso para que no rompa el flujo si Tesseract no está instalado localmente o falla
            print(f"⚠️ [OCR-FALLBACK] Error al procesar PDF {os.path.basename(filepath)} con OCR: {e}")
                 
    return "\n".join(markdown_content)


def convertir_imagen_a_markdown(filepath):
    """
    Lee una imagen (.png, .jpg, .jpeg, .webp) usando pytesseract OCR o PIL
    y extrae todo su texto en formato Markdown para la ingesta raw.
    """
    markdown_content = [f"\n## CONTENIDO IMAGEN ({os.path.basename(filepath)})\n"]
    try:
        import pytesseract
        from PIL import Image
        
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        tessdata_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'tessdata'))
        if os.path.exists(tessdata_dir):
            os.environ['TESSDATA_PREFIX'] = tessdata_dir
        
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img, lang='spa+eng')
        if text.strip():
            markdown_content.append(text)
    except Exception as e:
        print(f"⚠️ [OCR-IMAGEN] Error al procesar imagen {os.path.basename(filepath)} con OCR: {e}")
        
    return "\n".join(markdown_content)


def convertir_excel_a_json(filepath):
    """
    Lee un archivo Excel (.xlsx, .xls) usando pandas y lo convierte a un JSON estructurado.
    Soporta múltiples pestañas (sheets).
    """
    excel_file = pd.ExcelFile(filepath)
    resultado = {"sheets": {}}
    
    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        # Reemplazar valores NaN por None para generar un JSON limpio (null)
        df = df.where(pd.notnull(df), None)
        # Convertir a lista de registros
        records = df.to_dict(orient="records")
        resultado["sheets"][sheet_name] = records
        
    return json.dumps(resultado, ensure_ascii=False, indent=2)


def leer_csv_a_texto(filepath):
    """
    Lee un archivo CSV como texto plano, probando múltiples codificaciones.
    """
    encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
    for encoding in encodings:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"No se pudo decodificar el archivo CSV {filepath} con ninguna de las codificaciones probadas.")
