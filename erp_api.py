from fastapi import FastAPI, Query, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import sys
from typing import List, Dict, Any
from pydantic import BaseModel
from erp_master import ERPMaster

# IMPORTACIÓN ESTRUCTURADA POR DOMINIOS (DDD) 🏗️🧱🧠⚖️
from modulo_tarjetas import logica_tarjetas as tarjetas
from core_sistema import db_ingesta as ingesta
from modulo_compras import motor_compras as facturas
from modulo_compras import storage_compras as storage
from core_sistema import archiver_service
from modulo_tarjetas import parser_payway_liq, parser_patagonia, parser_naranja_xlsx

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
    results = ingesta.search_360(q)
    return {"results": results or []}

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

@app.post("/api/compras/vincular")
async def vincular_archivo_factura(id_factura: int = Query(...), file: UploadFile = File(...)):
    """Vincula físicamente un archivo a una factura existente en DB."""
    try:
        # 1. Obtener datos de la factura para jerarquía
        # 1. Recuperar datos de la factura para carpetas CUIT
        f_data = storage.get_factura_by_id(id_factura)
        if not f_data: return {"status": "error", "message": "Factura no encontrada"}
        
        cuit = f_data.get('cuit_proveedor', '00000000000')
        proveedor = f_data.get('proveedor', 'DESCONOCIDO')
        fecha = f_data.get('fecha', '2026-01-01')
        pv = f_data.get('punto_venta', '00000')
        num = f_data.get('numero_comprobante', '00000000')
        
        # 2. Guardar temporalmente
        temp_dir = os.path.join(WORKSPACE, "modulo_compras", "inbox_compras")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Sanitizar extensión
        _, ext = os.path.splitext(file.filename)
        temp_path = os.path.join(temp_dir, f"temp_upload_{id_factura}{ext}")
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 3. Invocar Archivador Nominal (v4.8)
        entidad_vault = f"{cuit} - {proveedor}"
        final_path = archiver_service.archivar_documento(
            temp_path, 
            "compras", 
            fecha[:4], 
            fecha[5:7], 
            entidad_vault,
            use_vault=True,
            overwrite=True
        )

        # 4. Renombrado Nominal: Fecha_Proveedor_Factura_PV-NUM
        if final_path and os.path.exists(final_path):
            # Sanitizar nombre de proveedor para evitar caracteres ilegales en Windows
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

app.mount("/archivos/compras", StaticFiles(directory="modulo_compras/archivos_compras"), name="archivos_compras")
app.mount("/historico/compras", StaticFiles(directory="modulo_compras/crudos_compras"), name="crudos_compras")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5005)
