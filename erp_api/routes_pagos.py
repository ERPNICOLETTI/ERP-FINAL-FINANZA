from fastapi import APIRouter, Request, UploadFile, File
from datetime import datetime
import os
import shutil

from erp_api.helpers import templates
import modulo_pagos.storage_pagos as pagos_storage
from modulo_tarjetas import logica_tarjetas as tarjetas
import modulo_compras.storage_compras as storage
from erp_master import ERPMaster

router = APIRouter()

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
master = ERPMaster(WORKSPACE)

@router.get("/api/pagos")
async def list_pagos(request: Request, estado: str = None, categoria: str = None, periodo_anio: str = None, periodo_mes: str = None, q: str = None):
    """Listar todos los vencimientos y pagos devolviendo fragmentos HTML para HTMX."""
    pagos_db = pagos_storage.get_pagos_vencimientos(estado=estado, categoria=categoria, periodo_anio=periodo_anio, periodo_mes=periodo_mes)
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    procesados = []
    
    for p in pagos_db:
        p_dict = dict(p)
        
        if q and q.lower() not in str(p_dict.get('concepto', '')).lower() and q.lower() not in str(p_dict.get('categoria', '')).lower():
            continue
            
        priorityLabel = "Pendiente"
        priorityClass = "status-pendiente"
        suggestedAmount = p_dict.get('monto', 0)
        
        vto1 = p_dict.get('fecha_vencimiento')
        vto2 = p_dict.get('fecha_vencimiento_2')
        estado_pago = p_dict.get('estado')
        
        if estado_pago == 'PAGADO':
            priorityLabel = "PAGADO ✅"
            priorityClass = "status-pagado"
        else:
            if vto2 and hoy > vto2:
                priorityLabel = "VENCIDO 🔥"
                priorityClass = "status-vencido"
                suggestedAmount = p_dict.get('monto_2', 0)
            elif not vto2 and vto1 and hoy > vto1:
                priorityLabel = "VENCIDO 🔥"
                priorityClass = "status-vencido"
            elif vto1 and hoy == vto1:
                priorityLabel = "VENCE HOY 🔔"
                priorityClass = "status-vence-hoy"
            elif vto2 and hoy == vto2:
                priorityLabel = "VENCE HOY ⚠️"
                priorityClass = "status-vence-hoy"
                suggestedAmount = p_dict.get('monto_2', 0)
            elif vto1 and hoy > vto1 and vto2 and hoy < vto2:
                priorityLabel = "2DA OPORTUNID. 🟠"
                priorityClass = "status-vence-proximo"
                suggestedAmount = p_dict.get('monto_2', 0)
            elif vto1 and hoy < vto1:
                try:
                    d1 = datetime.strptime(vto1, "%Y-%m-%d")
                    dhoy = datetime.strptime(hoy, "%Y-%m-%d")
                    days = (d1 - dhoy).days
                    if days <= 3:
                        priorityLabel = f"Vto 1 en {days}d 🟡"
                        priorityClass = "status-vence-hoy"
                except: pass
                
        p_dict['priorityLabel'] = priorityLabel
        p_dict['priorityClass'] = priorityClass
        p_dict['suggestedAmount'] = suggestedAmount
        procesados.append(p_dict)
        
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request=request, name="tabla_pagos.html", context={"request": request, "pagos": procesados, "hoy": hoy})
    return procesados

@router.post("/api/pagos")
async def save_pago_record(data: dict):
    """Guardar o actualizar un registro de pago."""
    pago_id = pagos_storage.save_pago(data)
    if pago_id:
        return {"status": "success", "id": pago_id}
    return {"status": "error", "message": "No se pudo guardar el pago"}

@router.get("/summary")
async def get_summary(anio: str = None):
    res_pw = tarjetas.resumen_ejecutivo(anio)
    res_fac = storage.get_resumen_facturacion(anio)
    return {
        "tarjetas": res_pw,
        "facturacion": res_fac
    }

@router.post("/api/upload/{modulo}")
async def upload_file(modulo: str, file: UploadFile = File(...)):
    """Fase de Recepción v4.6 (Tránsito Crudo)."""
    try:
        inbox_dir = os.path.join(WORKSPACE, f"modulo_{modulo}", f"inbox_{modulo}")
        os.makedirs(inbox_dir, exist_ok=True)
        file_path = os.path.join(inbox_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"status": "success", "message": f"Archivo {file.filename} received en Inbox."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/process")
async def process_inboxes():
    """Gatillo Maestro: Invoca la ingesta global del orquestador."""
    try:
        master.ingest_inbox()
        return {"status": "success", "message": "Procesamiento maestro finalizado"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/search")
async def spotlight_search(q: str):
    """Busqueda 360 estilo Spotlight sobre FTS5"""
    results = storage.smart_search_invoice(q)
    return {"results": results or []}
