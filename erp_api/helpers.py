from fastapi.templating import Jinja2Templates
import os
import io
import re
from pydantic import BaseModel
from PIL import Image
from PyPDF2 import PdfMerger

# Shared templates folder
templates = Jinja2Templates(directory="frontend")

class ImportRequest(BaseModel):
    fuente: str
    path: str

class FacturaUpdate(BaseModel):
    punto_venta: str = None
    numero_comprobante: str = None

def extraer_palabra_clave(descripcion):
    if not descripcion:
        return None
    # Limpiar prefijos y códigos comunes en descripciones de tarjetas/bancos
    kw_raw = descripcion.strip().upper()
    kw_raw = re.sub(r'^(MERPAGO\*|EBN\*|WWW\.|DLOCAL\*|K|K\*|\*)', '', kw_raw)
    
    # Separar en palabras usando espacios, números, barras, etc.
    words = [w.strip() for w in re.split(r'[\s\d/*-]', kw_raw) if w.strip()]
    
    GENERIC_EXCLUDE = {
        "PAGO", "DEBITO", "CREDITO", "TRANSF", "TRANSFERENCIA", "COMPRA", 
        "CTA", "C", "SUCURSAL", "SUC", "IVA", "IMPUESTO", "INTERES", 
        "COMISION", "MANTENIMIENTO", "RETENCION", "PERCEPCION", "REVERSION", 
        "REVERSO", "AJUSTE", "LIQ", "LIQUIDACION", "CONCEPTO", "DETALLE", 
        "MOV", "MOVIMIENTO", "EXTRACCION", "DEPOSIT", "DEPOSITO", "COBROS", 
        "COBRO", "SALDO", "PESOS", "DOLARES", "USD", "ARS", "EFE", "EFECTIVO", 
        "CHEQUE", "CH", "INTERESES", "COMISIONES", "SA", "SRL", "LTDA", "LIMITADA",
        "AUTOMATICO", "AUTOMAT", "AUTOM", "DEB", "CRE", "TRF", "TRANS", "PAG",
        "RECIBIDA", "RECIBIDO", "ENVIADA", "ENVIADO", "EMITIDA", "EMITIDO", "AUTOMATICA"
    }
    
    # Buscar la primera palabra que no esté en la lista de excluidas
    for word in words:
        if len(word) >= 3 and word not in GENERIC_EXCLUDE:
            return word
            
    # Fallback a la primera de al menos 3 letras
    for word in words:
        if len(word) >= 3:
            return word
            
    return None

def aprender_palabra_clave(gasto_tipo_id, descripcion):
    kw = extraer_palabra_clave(descripcion)
    if kw:
        from modulo_gastos import storage_gastos
        conn = storage_gastos.get_db_connection()
        try:
            row = conn.execute("SELECT palabras_clave FROM gastos_tipos WHERE id = ?", (gasto_tipo_id,)).fetchone()
            if row:
                palabras = [p.strip().upper() for p in (row['palabras_clave'] or '').split(',') if p.strip()]
                if kw not in palabras:
                    palabras.append(kw)
                    new_keywords = ", ".join(palabras)
                    conn.execute("UPDATE gastos_tipos SET palabras_clave = ? WHERE id = ?", (new_keywords, gasto_tipo_id))
                    conn.commit()
                    print(f"🧠 [APRENDIZAJE GASTO] Agregada palabra clave '{kw}' al concepto ID {gasto_tipo_id}")
        except Exception as e:
            print(f"Error en aprendizaje de gasto: {e}")
        finally:
            conn.close()

def aprender_categoria_maestra(categoria_nombre, descripcion):
    if not categoria_nombre:
        return
    kw = extraer_palabra_clave(descripcion)
    if kw:
        from modulo_bancos import storage_bancos
        conn = storage_bancos.get_db_connection()
        try:
            row = conn.execute("SELECT palabras_clave FROM categorias_maestras WHERE nombre = ?", (categoria_nombre,)).fetchone()
            if row:
                palabras = [p.strip().upper() for p in (row['palabras_clave'] or '').split(',') if p.strip()]
                if kw not in palabras:
                    palabras.append(kw)
                    new_keywords = ", ".join(palabras)
                    conn.execute("UPDATE categorias_maestras SET palabras_clave = ? WHERE nombre = ?", (new_keywords, categoria_nombre))
                    conn.commit()
                    print(f"🧠 [APRENDIZAJE BANCO] Agregada palabra clave '{kw}' a categoria maestra '{categoria_nombre}'")
        except Exception as e:
            print(f"Error en aprendizaje de categoria maestra: {e}")
        finally:
            conn.close()

def merge_files_to_pdf(existing_path: str, new_path: str, out_path: str):
    """Cerebro de la Engrapadora Virtual (v4.9.3)"""
    merger = PdfMerger()

    def add_to_merger(path):
        ext = path.lower().split('.')[-1]
        try:
            if ext == 'pdf':
                merger.append(path)
            elif ext in ['jpg', 'jpeg', 'png', 'webp']:
                img = Image.open(path).convert('RGB')
                pdf_bytes = io.BytesIO()
                img.save(pdf_bytes, format='PDF')
                pdf_bytes.seek(0)
                merger.append(pdf_bytes)
        except Exception as e:
            print(f"Error engrapando {path}: {e}")

    add_to_merger(existing_path)
    add_to_merger(new_path)

    temp_buffer = io.BytesIO()
    merger.write(temp_buffer)
    merger.close()

    with open(out_path, 'wb') as f:
        f.write(temp_buffer.getvalue())
