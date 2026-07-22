import os
import re

# LECTOR ORQUESTADOR: PAGOS v6.0.0 (Strategy Router) 🧠🧾

def procesar_pago(filepath=None, text_content=None):
    """
    Identifica la firma del pago y delega el parseo al lector puntual correspondiente.
    """
    if not text_content and (not filepath or not os.path.exists(filepath)):
        return False, None

    info = {
        'modulo':            'PAGOS',
        'categoria':         'SINDICALES',
        'concepto':          'DESCONOCIDO',
        'periodo_mes':       None,
        'periodo_anio':      None,
        'monto':             None,
        'fecha_vencimiento': None,
        'monto_2':           None,
        'fecha_vencimiento_2': None,
        'es_comprobante':    False,
        'codigo_barras':     None,
        'meta_json':         {}
    }

    try:
        if text_content:
            full_text = text_content
        elif filepath and any(filepath.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
            import pytesseract
            from PIL import Image
            
            # Configuración de Tesseract local de seguridad
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            tessdata_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'core_sistema', 'tessdata'))
            os.environ['TESSDATA_PREFIX'] = tessdata_dir
            
            img = Image.open(filepath)
            full_text = pytesseract.image_to_string(img, lang='spa+eng')
        else:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                if not pdf.pages:
                    return False, None
                full_text = ""
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        full_text += t + "\n"
            
            # Fallback OCR si es PDF escaneado
            if not full_text or len(re.sub(r'[^a-zA-Z0-9]', '', full_text)) < 50:
                try:
                    import pypdfium2 as pdfium
                    import pytesseract
                    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                    tessdata_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'core_sistema', 'tessdata'))
                    os.environ['TESSDATA_PREFIX'] = tessdata_dir
                    
                    doc = pdfium.PdfDocument(filepath)
                    try:
                        ocr_text = []
                        for page_idx in range(min(len(doc), 3)):
                            page = doc[page_idx]
                            bitmap = page.render(scale=2)
                            pil_img = bitmap.to_pil()
                            text_page = pytesseract.image_to_string(pil_img, lang='spa+eng')
                            if text_page.strip():
                                ocr_text.append(text_page)
                        if ocr_text:
                            full_text += "\n" + "\n".join(ocr_text)
                    finally:
                        doc.close()
                except Exception as ocr_err:
                    pass

        info['meta_json']['full_text'] = full_text
        TU = full_text.upper()

        # 0. Código de barras
        text_clean = re.sub(r'\s+', '', full_text)
        barras_match = re.search(r'(\d{40,65})', text_clean)
        if barras_match:
            info['codigo_barras'] = barras_match.group(1)

        # 1. Router a Lector Estrategia
        if "INACAP" in TU:
            info['concepto'] = 'INACAP'
            from modulo_pagos.lectores.lector_inacap import procesar as run_inacap
            run_inacap(TU, info)
        elif "FAECYS" in TU:
            info['concepto'] = 'FAECYS'
            from modulo_pagos.lectores.lector_faecys import procesar as run_faecys
            run_faecys(TU, info)
        elif re.search(r'\bSEC\b', TU) or "SINDICATO DE EMPLEADOS DE COMERCIO" in TU:
            info['concepto'] = 'SEC'
            from modulo_pagos.lectores.lector_sec import procesar as run_sec
            run_sec(TU, info)
        elif "TRABAJO - TASAS" in TU or "SECRETARIA DE TRABAJO" in TU or "MINISTERIO DE TRABAJO" in TU:
            info['concepto'] = 'POLICIA'
            from modulo_pagos.lectores.lector_policia import procesar as run_policia
            run_policia(TU, info)
        elif "FORMULARIO F.931" in TU or "F931" in TU or "OBLIGACION MENSUAL/ANUAL" in TU or "(301)" in TU or "(351)" in TU:
            info['concepto'] = '931'
            info['categoria'] = 'IMPUESTOS'
            from modulo_pagos.lectores.lector_afip_931 import procesar as run_afip_931
            run_afip_931(TU, info)
        elif "SERVICOOP" in TU:
            info['concepto']  = 'SERVICOOP'
            info['categoria'] = 'SERVICIOS'
        elif "RED UNO" in TU or "REDUNO" in TU:
            info['concepto']  = 'REDUNO'
            info['categoria'] = 'SERVICIOS'
        else:
            info['concepto'] = 'SINDICAL_GENERICO'

        info['es_comprobante'] = False
        return True, info

    except Exception as e:
        print(f"❌ [ORQUESTADOR-PAGOS] Error: {e}")
        return False, None
