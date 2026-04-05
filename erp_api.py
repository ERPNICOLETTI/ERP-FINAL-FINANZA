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
async def list_facturas():
    """Listado total de facturas para la Bóveda de Compras."""
    return storage.get_all_facturas()

@app.post("/api/facturas/update/{fid}")
async def update_factura(fid: int, req: FacturaUpdate):
    """Actualiza campos específicos de una factura (Confirmación de Padding)."""
    fields = {k: v for k, v in req.dict().items() if v is not None}
    if not fields: return {"status": "ignored"}
    success = storage.update_factura_fields(fid, fields)
    return {"status": "success" if success else "error"}

@app.post("/api/compras/vincular")
async def vincular_archivo_factura(id_factura: int = Query(...), file: UploadFile = File(...)):
    """Vincula físicamente un archivo a una factura existente en DB."""
    try:
        # 1. Obtener datos de la factura para jerarquía
        conn = storage.get_db_connection()
        f = conn.execute("SELECT fecha, proveedor FROM facturas WHERE id = ?", (id_factura,)).fetchone()
        conn.close()
        
        if not f: return {"status": "error", "message": "Factura no encontrada"}
        
        # 2. Guardar temporalmente en crudos para que archiver_service haga su magia
        temp_dir = os.path.join(WORKSPACE, "modulo_compras", "crudos_compras")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, file.filename)
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 3. Invocar Archivador Legal (Ley de Localía v4.6)
        # archivar_documento usa: filepath, modulo, anio, mes, entidad
        fecha = f['fecha'] # YYYY-MM-DD
        final_path = archiver_service.archivar_documento(
            temp_path, 
            "compras", 
            fecha[:4], 
            fecha[5:7], 
            f['proveedor']
        )
        
        if final_path:
            # Calcular ruta relativa para el servidor estático
            # El servidor estático apunta a modulo_compras/archivos_compras
            base_archive = os.path.join(WORKSPACE, "modulo_compras", "archivos_compras")
            rel_path = os.path.relpath(final_path, base_archive)
            
            # 4. Actualizar base de datos via storage
            storage.update_record_path(id_factura, rel_path, "facturas")
            
            return {
                "status": "success", 
                "message": "Vinculación legal exitosa",
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
