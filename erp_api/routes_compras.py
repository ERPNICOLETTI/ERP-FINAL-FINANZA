from fastapi import APIRouter, Request, Form, Query, UploadFile, File
import os
import shutil
from datetime import datetime

from erp_api.helpers import templates, FacturaUpdate, merge_files_to_pdf
import modulo_compras.storage_compras as storage
from core_sistema import archiver_service

router = APIRouter()

# Solve WORKSPACE locally to match the root path
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@router.get("/api/facturas")
async def list_facturas(request: Request, anio: str = None, mes: str = None, estado: str = "all", q: str = None):
    """Listado de facturas con soporte HTMX y Jinja2."""
    data = storage.get_all_compras_facturas(anio, mes)
    
    procesados = []
    for f in data:
        if q:
            term = q.lower()
            if term not in str(f.get('proveedor', '')).lower() and \
               term not in str(f.get('cuit_proveedor', '')).lower() and \
               term not in str(f.get('numero_comprobante', '')).lower():
                continue
                
        tiene_foto = bool(f.get('tiene_foto') or f.get('path_archivo'))
        if estado == "pending" and tiene_foto: continue
        if estado == "completed" and not tiene_foto: continue
        
        procesados.append(f)
        
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request=request, name="tabla_compras.html", context={"request": request, "facturas": procesados})
    
    return procesados

@router.post("/api/facturas/update/{fid}")
async def update_factura(fid: int, req: FacturaUpdate):
    """Actualiza campos específicos de una factura (Confirmación de Padding)."""
    fields = {k: v for k, v in req.dict().items() if v is not None}
    if not fields: return {"status": "ignored"}
    success = storage.update_factura_fields(fid, fields)
    return {"status": "success" if success else "error"}

@router.get("/api/compras/search")
async def search_compras_match(q: str):
    """Búsqueda elástica para feedback atómico (v4.8)."""
    if not q or len(q) < 3: return {"status": "too_short"}
    results = storage.smart_search_invoice(q)
    return {"results": results}

@router.get("/api/compras/inbox/list")
async def list_inbox_files():
    """Devuelve la lista de archivos pendientes en el Inbox (v4.9)."""
    inbox_dir = os.path.join(WORKSPACE, "modulo_compras", "inbox_compras")
    os.makedirs(inbox_dir, exist_ok=True)
    files = [f for f in os.listdir(inbox_dir) if os.path.isfile(os.path.join(inbox_dir, f)) and f.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg'))]
    return {"files": files}

@router.post("/api/compras/vincular")
async def vincular_archivo_factura(
    id_factura: int = Query(0), 
    file: UploadFile = File(None),
    inbox_filename: str = Form(None),
    is_pending_calim: str = Form("false"),
    proveedor_nombre: str = Form(""),
    numero_factura: str = Form("")
):
    """Vincula físicamente un archivo a una factura, o archiva en espera (v4.9)."""
    try:
        temp_dir = os.path.join(WORKSPACE, "modulo_compras", "inbox_compras")
        os.makedirs(temp_dir, exist_ok=True)
        
        # --- MODO 1: Excepción (Pendiente CALIM) ---
        if is_pending_calim.lower() == "true":
            if not inbox_filename and not file:
                return {"status": "error", "message": "No hay archivo para Sala de Espera"}
                
            cuit = "00000000000"
            proveedor = proveedor_nombre.strip().upper() if proveedor_nombre else "PENDIENTE_CALIM"
            fecha = datetime.now().strftime("%Y-%m-%d")
            pv = "XX"
            num = numero_factura.strip() if numero_factura else str(int(datetime.now().timestamp()))
            
            if inbox_filename:
                temp_path = os.path.join(temp_dir, inbox_filename)
                _, ext = os.path.splitext(inbox_filename)
                if not os.path.exists(temp_path): return {"status": "error"}
            else:
                _, ext = os.path.splitext(file.filename)
                temp_path = os.path.join(temp_dir, f"temp_upload_calim_{num}{ext}")
                with open(temp_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            
            entidad_vault = f"{cuit} - PENDIENTES CALIM"
            final_path = archiver_service.archivar_documento(
                temp_path, "compras", fecha[:4], fecha[5:7], entidad_vault, use_vault=True, overwrite=True, subcategoria="Facturas"
            ).replace('\\', '/')
            
            if final_path and os.path.exists(final_path):
                prov_clean = "".join([c if c.isalnum() else "_" for c in proveedor]).strip("_")
                target_name = f"{fecha}_{prov_clean}_Factura_{pv}-{num}{ext.lower()}"
                final_dir = os.path.dirname(final_path).replace('\\', '/')
                new_final_path = f"{final_dir}/{target_name}"
                
                if os.path.exists(new_final_path): os.remove(new_final_path)
                os.rename(final_path, new_final_path)
                final_path = new_final_path.replace('\\', '/')
                
                storage.save_factura({
                    "cuit_proveedor": cuit,
                    "proveedor": proveedor,
                    "punto_venta": pv,
                    "numero_comprobante": num,
                    "fecha": fecha,
                    "tipo_operacion": "COMPRA",
                    "tipo_comprobante": "88",
                    "origen": "PENDIENTE_CALIM",
                    "status": "SALA_ESPERA",
                    "tiene_foto": 1,
                    "path_archivo": final_path
                })
            
            return {"status": "success", "message": "Enviado a Sala de Espera CALIM"}

        # --- MODO 2: Normal ---
        f_data = storage.get_factura_by_id(id_factura)
        if not f_data: return {"status": "error", "message": "Factura no encontrada"}
        
        cuit = f_data.get('cuit_proveedor')
        proveedor = f_data.get('proveedor') or 'DESCONOCIDO'
        fecha = f_data.get('fecha') or '2026-01-01'
        pv = f_data.get('punto_venta') or '00000'
        num = f_data.get('numero_comprobante') or '00000000'
        
        if inbox_filename:
            temp_path = os.path.join(temp_dir, inbox_filename)
            _, ext = os.path.splitext(inbox_filename)
            if not os.path.exists(temp_path): return {"status": "error", "message": "Archivo de inbox perdido"}
        else:
            _, ext = os.path.splitext(file.filename)
            temp_path = os.path.join(temp_dir, f"temp_upload_{id_factura}{ext}")
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

        tiene_foto = bool(f_data.get('tiene_foto', 0))
        old_path = f_data.get('path_archivo', '')
        
        if tiene_foto and old_path and os.path.exists(old_path):
            prov_clean = "".join([c if c.isalnum() else "_" for c in proveedor]).strip("_")
            target_name = f"{fecha}_{prov_clean}_Factura_{pv}-{num}.pdf"
            
            final_dir = os.path.dirname(old_path).replace('\\', '/')
            new_final_path = f"{final_dir}/{target_name}"
            
            merge_files_to_pdf(old_path, temp_path, new_final_path)
            
            if os.path.exists(temp_path): os.remove(temp_path)
            if old_path != new_final_path and os.path.exists(old_path):
                os.remove(old_path)
                
            final_path = new_final_path.replace('\\', '/')
            
        else:
            entidad_vault = f"{cuit} - {proveedor}" if cuit else proveedor
            final_path = archiver_service.archivar_documento(
                temp_path, 
                "compras", 
                fecha[:4], 
                fecha[5:7], 
                entidad_vault,
                use_vault=True,
                overwrite=True,
                subcategoria="Facturas"
            ).replace('\\', '/')

            if final_path and os.path.exists(final_path):
                prov_clean = "".join([c if c.isalnum() else "_" for c in proveedor]).strip("_")
                target_name = f"{fecha}_{prov_clean}_Factura_{pv}-{num}{ext.lower()}"
                
                final_dir = os.path.dirname(final_path)
                new_final_path = os.path.join(final_dir, target_name)
                
                if os.path.exists(new_final_path): os.remove(new_final_path)
                os.rename(final_path, new_final_path)
                final_path = new_final_path
            
        if final_path:
            base_archive = os.path.join(WORKSPACE, "modulo_compras", "archivos_compras")
            rel_path = os.path.relpath(final_path, base_archive).replace('\\', '/')
            
            storage.update_factura_fields(id_factura, {
                "path_archivo": rel_path,
                "tiene_foto": 1,
                "status": "ARCHIVADO"
            })
            
            return {
                "status": "success", 
                "message": "Archivo vinculado y archivado por CUIT",
                "rel_path": rel_path
            }
        
        return {"status": "error", "message": "Fallo al archivar documento físicamente"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
