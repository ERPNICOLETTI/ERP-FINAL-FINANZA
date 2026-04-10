from fastapi import FastAPI, Query, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import sys
import shutil
import io
from typing import List, Dict, Any
from pydantic import BaseModel
from PIL import Image
from PyPDF2 import PdfMerger
from erp_master import ERPMaster
from datetime import datetime

# IMPORTACIÓN ESTRUCTURADA POR DOMINIOS (DDD) 🏗️🧱🧠⚖️
from modulo_tarjetas import logica_tarjetas as tarjetas
# IMPORTACIÓN DE LIBRERÍAS DE CONTROLADOR DE ALMACENAMIENTO LOCAL
# El control cruzado ocurre aquí a nivel aplicación, FastAPI llama al motor SQLite.
import modulo_compras.storage_compras as storage
import modulo_pagos.storage_pagos as pagos_storage
from core_sistema import archiver_service
from modulo_tarjetas import parser_payway_liq, parser_patagonia, parser_naranja_xlsx

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

# ------------------------------------------------------------------------------------------
# ENDPOINTS DE API - MÓDULO COMPRAS
# ------------------------------------------------------------------------------------------

class ImportRequest(BaseModel):
    fuente: str
    path: str

class FacturaUpdate(BaseModel):
    punto_venta: str = None
    numero_comprobante: str = None

app = FastAPI(title="ERP Final API - Área Inteligencia (DDD)", version="4.0.0")

# Workspace Context
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
master = ERPMaster(WORKSPACE)

import shutil

@app.post("/api/upload/{modulo}")
async def upload_file(modulo: str, file: UploadFile = File(...)):
    """Fase de Recepción v4.6 (Tránsito Crudo)."""
    try:
        inbox_dir = os.path.join(WORKSPACE, f"modulo_{modulo}", f"inbox_{modulo}")
        os.makedirs(inbox_dir, exist_ok=True)
        file_path = os.path.join(inbox_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"status": "success", "message": f"Archivo {file.filename} recibido en Inbox."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/process")
async def process_inboxes():
    """Gatillo Maestro: Invoca la ingesta global del orquestador."""
    try:
        master.ingest_inbox()
        return {"status": "success", "message": "Procesamiento maestro finalizado"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/search")
async def spotlight_search(q: str):
    """Busqueda 360 estilo Spotlight sobre FTS5"""
    results = storage.smart_search_invoice(q)
    return {"results": results or []}

# ------------------------------------------------------------------------------------------
# ENDPOINTS DE API - MÓDULO PAGOS (v5.0.0)
# ------------------------------------------------------------------------------------------

@app.get("/api/pagos")
async def list_pagos(estado: str = None, categoria: str = None, periodo_anio: str = None, periodo_mes: str = None):
    """Listar todos los vencimientos y pagos."""
    return pagos_storage.get_pagos(estado=estado, categoria=categoria, periodo_anio=periodo_anio, periodo_mes=periodo_mes)

@app.post("/api/pagos")
async def save_pago_record(data: dict):
    """Guardar o actualizar un registro de pago."""
    pago_id = pagos_storage.save_pago(data)
    if pago_id:
        return {"status": "success", "id": pago_id}
    return {"status": "error", "message": "No se pudo guardar el pago"}


@app.get("/summary")
async def get_summary(anio: str = None):
    res_pw = tarjetas.resumen_ejecutivo(anio)
    res_fac = facturas.resumen_facturacion(anio)
    return {
        "tarjetas": res_pw,
        "facturacion": res_fac
    }

@app.get("/tarjetas/audit")
async def audit_tarjetas():
    return tarjetas.auditoria_360()

@app.get("/tarjetas/cupon/{cid}")
async def get_cupon(cid: str):
    res = tarjetas.buscar_cupon(cid)
    if res: return res
    return {"error": "Cupón no encontrado"}

@app.post("/tarjetas/importar")
async def importar_tarjetas(req: ImportRequest):
    """Gatilla una importación selectiva desde archivos locales."""
    try:
        fuente = req.fuente.upper()
        if fuente == 'PAYWAY':
            parser_payway_liq.parse_payway_liq(req.path)
            return {"status": "success", "fuente": "PAYWAY"}
        
        elif fuente == 'PATAGONIA365':
            parser_patagonia.parse_patagonia_365(req.path)
            return {"status": "success", "fuente": "PATAGONIA365"}
            
        elif fuente == 'NARANJA':
            if os.path.isdir(req.path):
                import glob
                archivos = glob.glob(os.path.join(req.path, "*.xlsx"))
                for a in archivos:
                    parser_naranja_xlsx.parse_naranja_xlsx(a)
            else:
                parser_naranja_xlsx.parse_naranja_xlsx(req.path)
            return {"status": "success", "fuente": "NARANJA"}
            
        return {"status": "error", "message": f"Fuente '{fuente}' no soportada"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/bancos/importar")
async def importar_bancos(req: ImportRequest):
    """Importar extractos bancarios al sistema."""
    try:
        fuente = req.fuente.upper()
        if fuente == 'CHUBUT':
            from modulo_bancos.parser_chubut import parse_chubut_excel
            parse_chubut_excel(req.path)
            return {"status": "success", "fuente": "CHUBUT"}
        return {"status": "error", "message": f"Banco '{fuente}' no soportado"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/bancos/sueldos")
async def get_sueldos_bancarios(anio: str = "2026"):
    """Consulta de sueldos delegada al dominio de bancos."""
    from modulo_bancos import storage_bancos
    return storage_bancos.get_sueldos(anio)

@app.get("/api/facturas")
async def list_facturas(anio: str = None, mes: str = None):
    """Listado de facturas con soporte para selección cronológica (Modo ML)."""
    return storage.get_all_facturas(anio, mes)

@app.post("/api/facturas/update/{fid}")
async def update_factura(fid: int, req: FacturaUpdate):
    """Actualiza campos específicos de una factura (Confirmación de Padding)."""
    fields = {k: v for k, v in req.dict().items() if v is not None}
    if not fields: return {"status": "ignored"}
    success = storage.update_factura_fields(fid, fields)
    return {"status": "success" if success else "error"}

@app.get("/api/compras/search")
async def search_compras_match(q: str):
    """Búsqueda elástica para feedback atómico (v4.8)."""
    if not q or len(q) < 3: return {"status": "too_short"}
    results = storage.smart_search_invoice(q)
    return {"results": results}

@app.get("/api/compras/inbox/list")
async def list_inbox_files():
    """Devuelve la lista de archivos pendientes en el Inbox (v4.9)."""
    inbox_dir = os.path.join(WORKSPACE, "modulo_compras", "inbox_compras")
    os.makedirs(inbox_dir, exist_ok=True)
    files = [f for f in os.listdir(inbox_dir) if os.path.isfile(os.path.join(inbox_dir, f)) and f.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg'))]
    return {"files": files}

@app.post("/api/compras/vincular")
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
            
            # Obtener archivo origen
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
                
                # Inyección a Base de Datos como PENDIENTE
                storage.save_factura({
                    "cuit_proveedor": cuit,
                    "proveedor": proveedor,
                    "punto_venta": pv,
                    "numero_comprobante": num,
                    "fecha": fecha,
                    "tipo_operacion": "COMPRA",
                    "tipo_comprobante": "88", # Código interno para Pendientes
                    "origen": "PENDIENTE_CALIM",
                    "status": "SALA_ESPERA",
                    "tiene_foto": 1,
                    "path_archivo": final_path
                })
            
            return {"status": "success", "message": "Enviado a Sala de Espera CALIM"}

        # --- MODO 2: Normal ---
        # 1. Recuperar datos de la factura
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

        # 3. VERIFICAR SI APLICAMOS ENGRAPADORA VIRTUAL O ARCHIVADOR NORMAL
        tiene_foto = bool(f_data.get('tiene_foto', 0))
        old_path = f_data.get('path_archivo', '')
        
        if tiene_foto and old_path and os.path.exists(old_path):
            # ENGRAPADORA VIRTUAL (Multi-página Detectado)
            prov_clean = "".join([c if c.isalnum() else "_" for c in proveedor]).strip("_")
            target_name = f"{fecha}_{prov_clean}_Factura_{pv}-{num}.pdf"
            
            final_dir = os.path.dirname(old_path).replace('\\', '/')
            new_final_path = f"{final_dir}/{target_name}"
            
            # Fusionar ambos (el previo de la bd y el nuevo entrante)
            merge_files_to_pdf(old_path, temp_path, new_final_path)
            
            # Limpieza post-ensamblaje
            if os.path.exists(temp_path): os.remove(temp_path)
            if old_path != new_final_path and os.path.exists(old_path):
                os.remove(old_path)
                
            final_path = new_final_path.replace('\\', '/')
            
        else:
            # 3. Invocar Archivador Nominal Estandar (v4.8)
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

            # 4. Renombrado Nominal: Fecha_Proveedor_Factura_PV-NUM
            if final_path and os.path.exists(final_path):
                prov_clean = "".join([c if c.isalnum() else "_" for c in proveedor]).strip("_")
                target_name = f"{fecha}_{prov_clean}_Factura_{pv}-{num}{ext.lower()}"
                
                final_dir = os.path.dirname(final_path)
                new_final_path = os.path.join(final_dir, target_name)
                
                if os.path.exists(new_final_path): os.remove(new_final_path)
                os.rename(final_path, new_final_path)
                final_path = new_final_path
            
        # El archivo temporal temp_path ya fue MOVIDO/ELIMINADO por archiver_service.archivar_documento
        # (shutil.move se encarga de la limpieza de origen)
        
        if final_path:
            # Calcular ruta relativa para el servidor estático
            # El servidor estático apunta a modulo_compras/archivos_compras
            base_archive = os.path.join(WORKSPACE, "modulo_compras", "archivos_compras")
            rel_path = os.path.relpath(final_path, base_archive)
            
            # 4. Actualizar estado y sello
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


@app.post("/sync")
async def sync_data():
    master.setup_schema()
    return {"status": "success", "message": "Estructura y FTS5 actualizados"}

# Montar servidores estáticos jerárquicos (Aislamiento v4.6)
os.makedirs(os.path.join(WORKSPACE, "modulo_compras", "archivos_compras"), exist_ok=True)
os.makedirs(os.path.join(WORKSPACE, "modulo_compras", "crudos_compras"), exist_ok=True)
os.makedirs(os.path.join(WORKSPACE, "modulo_compras", "inbox_compras"), exist_ok=True)

# Directorios de Pagos
os.makedirs(os.path.join(WORKSPACE, "modulo_pagos", "archivos_pagos"), exist_ok=True)

app.mount("/archivos/compras", StaticFiles(directory="modulo_compras/archivos_compras"), name="archivos_compras")
app.mount("/archivos/pagos", StaticFiles(directory="modulo_pagos/archivos_pagos"), name="archivos_pagos")
app.mount("/historico/compras", StaticFiles(directory="modulo_compras/crudos_compras"), name="crudos_compras")
app.mount("/inbox", StaticFiles(directory="modulo_compras/inbox_compras"), name="inbox_local")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5005)
