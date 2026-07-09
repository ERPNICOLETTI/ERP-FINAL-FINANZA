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
