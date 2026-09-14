"""ELT de escaneos: original primero, extracción versionada después.

Uso: python -m modulo_compras.lector_facturas_scan ARCHIVO_O_CARPETA [...]
No modifica facturas fiscales ni mueve o elimina los archivos de entrada.
"""
import argparse
import json
import hashlib
from pathlib import Path
from core_sistema.ocr_documentos import leer, VERSION
from . import storage_compras as storage
from .facturas_scan_parser import extraer, VERSION as CAMPOS_VERSION

PIPELINE_VERSION = VERSION + '+' + CAMPOS_VERSION


def procesar_archivo(path):
    path = Path(path)
    return procesar_contenido(path.read_bytes(), path.name)


def procesar_contenido(content, name):
    staged = storage.registrar_scan(content, name, PIPELINE_VERSION)
    if staged['estado'] == 'LEIDO':
        return staged
    try:
        result = leer(content, Path(name).suffix.lower())
        for page in result['paginas']:
            page['campos'] = extraer(page)
        storage.finalizar_scan(staged['id'], result)
        return {**staged, 'estado': 'LEIDO', 'paginas': len(result['paginas'])}
    except Exception as exc:
        storage.finalizar_scan(staged['id'], None, str(exc))
        return {**staged, 'estado': 'ERROR', 'error': str(exc)}


def reanalizar_campos():
    """Nueva versión de campos sobre OCR conservado, sin volver a gastar lectura."""
    results = []
    for previous in storage.scans_para_reanalisis():
        result = json.loads(previous['resultado_json'])
        if result.get('version') != VERSION:
            continue
        content = Path(previous['path_original']).read_bytes()
        if hashlib.sha256(content).hexdigest() != previous['hash_sha256']:
            raise ValueError(f"Original alterado: extracción {previous['id']}. No se reutilizó su OCR.")
        staged = storage.registrar_scan(content, previous['nombre_original'], PIPELINE_VERSION)
        if staged['estado'] != 'LEIDO':
            for page in result['paginas']:
                page['campos'] = extraer(page)
            storage.finalizar_scan(staged['id'],result)
        results.append(staged['id'])
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--solo-campos', action='store_true')
    args = parser.parse_args()
    if args.solo_campos:
        print(json.dumps({'reanalizados':reanalizar_campos()}))
        raise SystemExit(0)
    if not args.paths:
        parser.error('Indicá archivos/carpetas o --solo-campos')
    files = set()
    for value in args.paths:
        path = Path(value)
        if path.is_dir():
            files.update(p for p in path.rglob('*') if p.suffix.lower() in {'.pdf','.jpg','.jpeg','.png','.webp'})
        else:
            files.add(path)
    failed = False
    for path in sorted(files):
        result = procesar_archivo(path)
        print(json.dumps({'archivo': path.name, **result}, ensure_ascii=False), flush=True)
        failed |= result['estado'] == 'ERROR'
    raise SystemExit(1 if failed else 0)
