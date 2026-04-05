from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import os
import sys
from typing import List, Dict, Any
from pydantic import BaseModel
from erp_master import ERPMaster

# IMPORTACIÓN ESTRUCTURADA POR DOMINIOS (DDD) 🏗️🧱🧠⚖️
from modulo_tarjetas import logica_tarjetas as tarjetas
from core_sistema import db_ingesta as ingesta
from modulo_compras import motor_compras as facturas
from modulo_tarjetas import parser_payway_liq, parser_patagonia, parser_naranja_xlsx

class ImportRequest(BaseModel):
    fuente: str
    path: str

app = FastAPI(title="ERP Final API - Área Inteligencia (DDD)", version="4.0.0")

# Workspace Context
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
master = ERPMaster(WORKSPACE)

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
        <head><title>ERP API - Modo Arquitecto DDD</title></head>
        <body style="font-family: sans-serif; background: #0f172a; color: white; padding: 50px;">
            <h1 style="color: #38bdf8;">🧠 ERP Central Intelligence API</h1>
            <p>Estado: <span style="color: #10b981;">ARQUITECTURA DDD IMPLEMENTADA</span></p>
        </body>
    </html>
    """

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

@app.get("/facturas/buscar")
async def buscar_facturas(q: str):
    return facturas.buscar_global(q)

@app.post("/facturas/importar")
async def importar_facturas(req: ImportRequest):
    """Gatilla importación de AFIP o CALIM."""
    try:
        fuente = req.fuente.upper()
        if fuente == 'AFIP':
            from modulo_compras.importador_afip import parse_afip_csv
            parse_afip_csv(req.path)
            return {"status": "success", "fuente": "AFIP"}
        elif fuente == 'CALIM':
            from modulo_compras.importador_calim import parse_calim_excel
            parse_calim_excel(req.path)
            return {"status": "success", "fuente": "CALIM"}
        return {"status": "error", "message": f"Fuente '{fuente}' no soportada en facturas"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/sync")
async def sync_data():
    master.setup_schema()
    return {"status": "success", "message": "Estructura y FTS5 actualizados"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5005)
