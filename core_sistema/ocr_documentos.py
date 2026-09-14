"""Lectura local por página, sin SQL ni transmisión de documentos."""
import io
import os
import shutil
from pathlib import Path

VERSION = 'tesseract-documentos/1.1'


def leer(content, extension):
    import fitz
    import pytesseract
    import zxingcpp
    from PIL import Image, ImageOps
    command = os.environ.get('ERP_TESSERACT') or shutil.which('tesseract')
    command = command or r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if not Path(command).is_file():
        raise RuntimeError('Falta Tesseract: configurá ERP_TESSERACT.')
    pytesseract.pytesseract.tesseract_cmd = command
    data = Path(__file__).parent / 'tessdata'
    os.environ['TESSDATA_PREFIX'] = str(data)
    config = '--psm 3'
    for lang in ('spa', 'eng'):
        if not (data / f'{lang}.traineddata').is_file():
            raise RuntimeError(f'Falta modelo OCR {lang} en {data}')
    pages = []
    doc = fitz.open(stream=content, filetype='pdf') if extension == '.pdf' else None
    try:
        count = len(doc) if doc else 1
        for number in range(count):
            native = doc[number].get_text('text') if doc else ''
            if native.strip():
                # OCR también: una capa digital parcial no prueba que todo fue leído.
                native = native.strip()
            if doc:
                pix = doc[number].get_pixmap(dpi=250, alpha=False)
                img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            else:
                with Image.open(io.BytesIO(content)) as source:
                    img = ImageOps.exif_transpose(source).convert('RGB')
            img = ImageOps.autocontrast(ImageOps.grayscale(img))
            codes = [b.text for b in zxingcpp.read_barcodes(img) if b.valid]
            result = pytesseract.image_to_data(img, lang='spa+eng', config=config,
                output_type=pytesseract.Output.DICT, timeout=120)
            words, lines = [], {}
            for i, text in enumerate(result['text']):
                if not text.strip():
                    continue
                word = {key: result[key][i] for key in ('left','top','width','height','conf')}
                word['text'] = text
                words.append(word)
                key = tuple(result[k][i] for k in ('block_num','par_num','line_num'))
                lines.setdefault(key, []).append(text)
            sparse = pytesseract.image_to_string(img, lang='spa+eng',
                config='--psm 11', timeout=120)
            pages.append({'pagina': number + 1, 'texto_nativo': native,
                'texto_alternativo': sparse, 'codigos': codes,
                'texto': '\n'.join(' '.join(line) for line in lines.values()),
                'ancho': img.width, 'alto': img.height, 'palabras': words,
                'advertencias': [] if words else ['SIN_TEXTO_LEGIBLE']})
        return {'version': VERSION, 'motor': str(pytesseract.get_tesseract_version()),
                'idiomas': 'spa+eng', 'dpi': 250, 'paginas': pages}
    finally:
        if doc:
            doc.close()
