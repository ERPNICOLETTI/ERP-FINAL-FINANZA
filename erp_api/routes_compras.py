from fastapi import APIRouter, Request, Form, Query, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import hashlib
import logging
from erp_api.helpers import templates, FacturaUpdate
from modulo_compras import storage_compras as storage, evidencias
from modulo_compras import storage_compras_scan as scan_storage, lector_facturas_scan
from pydantic import BaseModel, Field, StrictInt

router = APIRouter()
WORKSPACE = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


@router.get('/api/compras/ocr')
def list_ocr():
    return storage.listar_scans()


@router.get('/api/compras/ocr/bandeja')
def scan_bandeja():
    return scan_storage.bandeja()


@router.post('/api/compras/ocr/cargar')
def scan_cargar(file: UploadFile = File(...)):
    try:
        name = Path((file.filename or '').replace('\\','/')).name
        content = file.file.read(25*1024*1024+1)
        if len(content)>25*1024*1024:
            raise ValueError('Máximo 25 MB por archivo.')
        return lector_facturas_scan.procesar_contenido(content,name)
    except Exception as exc:
        logger.exception('Carga OCR fallida')
        raise HTTPException(400,str(exc))


@router.post('/api/compras/ocr/{scan_id}/reintentar')
def scan_reintentar(scan_id: int):
    try:
        scan, content, _ = scan_storage.original(scan_id)
        return lector_facturas_scan.procesar_contenido(content,scan['nombre_original'])
    except ValueError as exc:
        raise HTTPException(400,str(exc))


class ScanRevision(BaseModel):
    paginas: list[StrictInt] = Field(min_length=1,max_length=100)
    accion: str
    factura_id: StrictInt = 0
    nota: str = Field(min_length=1,max_length=2000)
    datos: dict = Field(default_factory=dict)
    permitir_adjunto: bool = False


@router.post('/api/compras/ocr/{scan_id}/revisar')
def scan_revisar(scan_id: int, revision: ScanRevision):
    try:
        return scan_storage.revisar(scan_id,**revision.model_dump())
    except ValueError as exc:
        raise HTTPException(400,str(exc))


@router.get('/api/compras/ocr/{scan_id}/historial')
def scan_historial(scan_id: int):
    return scan_storage.historial(scan_id)


@router.get('/compras/ocr')
def review_ocr(request: Request):
    return templates.TemplateResponse(request=request, name='compras_ocr.html', context={})


@router.get('/api/compras/ocr/{scan_id}/original')
def original_ocr(scan_id: int):
    value = storage.scan_original(scan_id)
    root = (WORKSPACE / 'modulo_compras/crudos_compras/EVIDENCIAS').resolve()
    path = Path(value).resolve() if value else root
    if not value or not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, 'Original no disponible')
    return FileResponse(path)


def inbox_path(name):
    root = (WORKSPACE / 'modulo_compras/inbox_compras').resolve()
    path = (root / name).resolve()
    if path.parent != root:
        raise ValueError('Nombre de archivo de buzón inválido.')
    return path


def visual_state(f):
    try:
        path = evidencias.resolve_visual(f.get('path_archivo'))
        exists = bool(path and path.is_file())
    except ValueError:
        exists = False
    f['archivo_disponible'] = exists
    f['archivo_url'] = f"/api/compras/archivo/{f['id']}" if exists else None
    return f


@router.get('/api/facturas')
async def list_facturas(request: Request, anio: str = None, mes: str = None, estado: str = 'all', q: str = None):
    rows = []
    for f in storage.get_all_compras_facturas(anio, mes):
        visual_state(f)
        if q and not any(q.lower() in str(f.get(k) or '').lower() for k in ('proveedor','cuit_proveedor','numero_comprobante')):
            continue
        if estado == 'pending' and f['archivo_disponible']: continue
        if estado == 'completed' and not f['archivo_disponible']: continue
        rows.append(f)
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse(request=request, name='tabla_compras.html', context={'request':request,'facturas':rows})
    return rows


@router.get('/api/compras/archivo/{fid}')
async def archivo(fid: int):
    f = storage.get_factura_by_id(fid)
    if not f: raise HTTPException(404, 'Factura no encontrada')
    try: path = evidencias.resolve_visual(f.get('path_archivo'))
    except ValueError: raise HTTPException(404, 'Adjunto fuera de la bóveda')
    if not path or not path.is_file(): raise HTTPException(404, 'Adjunto no disponible')
    return FileResponse(path)


@router.post('/api/facturas/update/{fid}')
async def update_factura(fid: int, req: FacturaUpdate):
    fields = {k:v for k,v in req.dict().items() if v is not None}
    if not fields: return {'status':'ignored'}
    return {'status':'success' if storage.update_factura_fields(fid,fields) else 'error'}


@router.get('/api/compras/search')
async def search_compras_match(q: str):
    return {'results':storage.smart_search_invoice(q) if len(q.strip()) >= 3 else []}


@router.post('/api/compras/importar-multiples')
def importar_multiples(files: list[UploadFile] = File(...)):
    """El mismo lector ARCA/CALIM actualizado, sólo para los archivos seleccionados."""
    from modulo_compras import lector_arca_comprobantes, lector_calim_compras
    results = []
    for upload in files:
        name = Path((upload.filename or '').replace('\\','/')).name
        try:
            ext = Path(name).suffix.lower()
            if ext not in {'.csv','.zip','.xlsx'}:
                raise ValueError('ARCA: CSV/ZIP; CALIM: XLSX. Los PDF/fotos van al visor.')
            content = upload.file.read()
            if not content: raise ValueError('El archivo está vacío.')
            digest = hashlib.sha256(content).hexdigest()
            path = evidencias.immutable_write(WORKSPACE / 'modulo_compras/crudos_compras/IMPORTACIONES_WEB' / digest / name, content)
            reader = lector_calim_compras if ext == '.xlsx' else lector_arca_comprobantes
            success, info = reader.procesar_archivo(str(path))
            results.append({'archivo':name,'status':'success' if success else 'error', **info})
        except Exception as exc:
            logger.exception('Importación de Compras fallida: %s', name)
            results.append({'archivo':name,'status':'error','error':str(exc)})
    ok = sum(r['status']=='success' for r in results)
    return {'status':'success' if ok == len(results) and results else 'partial' if ok else 'error',
        'message':f'{ok} de {len(results)} archivos procesados.', 'resultados':results}


@router.get('/api/compras/inbox/list')
async def list_inbox_files():
    root = WORKSPACE / 'modulo_compras/inbox_compras'
    return {'files':sorted(p.name for p in root.iterdir() if p.is_file() and p.suffix.lower() in evidencias.EXTENSIONS) if root.exists() else []}


@router.post('/api/compras/vincular')
def vincular_archivo_factura(id_factura: int = Query(0), file: UploadFile = File(None),
    inbox_filename: str = Form(None), is_pending_calim: str = Form('false'),
    proveedor_nombre: str = Form(''), numero_factura: str = Form('')):
    try:
        source = None
        if inbox_filename:
            source = inbox_path(inbox_filename)
            content, name = source.read_bytes(), source.name
        elif file:
            content, name = file.file.read(), Path((file.filename or '').replace('\\','/')).name
        else:
            raise ValueError('Cargá un archivo primero.')
        result = storage.vincular_evidencia(content,name,id_factura,proveedor_nombre,numero_factura,is_pending_calim.lower()=='true')
        if source:
            if hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(content).digest():
                source.unlink()
        return result
    except Exception as exc:
        logger.exception('No se pudo vincular el comprobante')
        return {'status':'error','message':str(exc)}
