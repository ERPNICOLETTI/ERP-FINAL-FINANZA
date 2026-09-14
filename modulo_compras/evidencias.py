"""Archivos inmutables y derivados visuales de Compras. Sin SQL."""
import hashlib
import io
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.webp'}


def validate(content, name):
    ext = Path(name).suffix.lower()
    if ext not in EXTENSIONS or not content:
        raise ValueError('Usá un PDF o una imagen PNG/JPG/WEBP no vacía.')
    if ext == '.pdf':
        from PyPDF2 import PdfReader
        if not PdfReader(io.BytesIO(content)).pages:
            raise ValueError('El PDF no contiene páginas.')
    else:
        from PIL import Image
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
    return ext


def immutable_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError('Colisión de archivo: se conservó el documento existente.')
    return path


def resolve_visual(path):
    if not path:
        return None
    vault = (ROOT / 'modulo_compras/archivos_compras').resolve()
    candidate = Path(str(path).replace('\\', '/'))
    if not candidate.is_absolute():
        candidate = vault / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(vault):
        raise ValueError('El adjunto debe pertenecer a la bóveda de Compras.')
    return candidate


def publish(factura, content, ext, previous=None):
    """Genera una versión nueva; nunca modifica el adjunto anterior."""
    if previous:
        from PyPDF2 import PdfReader, PdfWriter
        from PIL import Image, ImageOps
        writer = PdfWriter()
        for data, suffix in [(previous.read_bytes(), previous.suffix.lower()), (content, ext)]:
            if suffix != '.pdf':
                out = io.BytesIO()
                with Image.open(io.BytesIO(data)) as img:
                    ImageOps.exif_transpose(img).convert('RGB').save(out, format='PDF')
                data = out.getvalue()
            reader = PdfReader(io.BytesIO(data))
            for page in reader.pages:
                writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        content, ext = out.getvalue(), '.pdf'
    clean = lambda value: re.sub(r'[^\w.-]+', '_', str(value or 'SIN_DATO'))[:32]
    date = str(factura['fecha'])[:10]
    folder = ROOT / 'modulo_compras/archivos_compras/Facturas' / (
        clean(factura.get('cuit_proveedor')) + ' - ' + clean(factura['proveedor'])) / date[:4] / date[5:7]
    digest = hashlib.sha256(content).hexdigest()
    name = f"{date}_Factura_{clean(factura.get('punto_venta'))}-{clean(factura['numero_comprobante'])}_{digest[:20]}{ext}"
    return immutable_write(folder / name, content).as_posix()


def seleccionar_paginas(content, ext, paginas):
    """Derivado de páginas elegidas; no reemplaza el original ni agrupa por inferencia."""
    if ext != '.pdf':
        if paginas != [1]:
            raise ValueError('Una imagen tiene una sola página.')
        return content, ext
    from PyPDF2 import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(content))
    if any(p < 1 or p > len(reader.pages) for p in paginas):
        raise ValueError('Página fuera del documento.')
    if paginas == list(range(1,len(reader.pages)+1)):
        return content, ext
    writer = PdfWriter()
    for p in paginas:
        writer.add_page(reader.pages[p-1])
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue(), '.pdf'
