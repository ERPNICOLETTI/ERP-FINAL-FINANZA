from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import os
import sys
from typing import List, Dict, Any
from pydantic import BaseModel
from erp_master import ERPMaster

# IMPORTACIÓN ESTRUCTURADA POR ÁREAS 🏗️🧱🧠⚖️
from core import tarjetas
from core import facturas
from core import ingesta
from parsers import parser_payway_liq, parser_patagonia

class ImportRequest(BaseModel):
    fuente: str
    path: str

app = FastAPI(title="ERP Final API - Área Inteligencia", version="3.1.0")

# Workspace Context
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
master = ERPMaster(WORKSPACE)

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
        <head><title>ERP API - Modo Cerebro</title></head>
        <body style="font-family: sans-serif; background: #0f172a; color: white; padding: 50px;">
            <h1 style="color: #38bdf8;">🧠 ERP Central Intelligence API</h1>
            <p>Estado: <span style="color: #10b981;">MODULARIZADO Y SEGURO</span></p>
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
        if req.fuente.upper() == 'PAYWAY':
            parser_payway_liq.parse_payway_liq(req.path)
            return {"status": "success", "fuente": "PAYWAY"}
        elif req.fuente.upper() == 'PATAGONIA365':
            parser_patagonia.parse_patagonia_365(req.path)
            return {"status": "success", "fuente": "PATAGONIA365"}
        return {"status": "error", "message": "Fuente no soportada"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/facturas/buscar")
async def buscar_facturas(q: str):
    return facturas.buscar_global(q)

@app.get("/facturas/discrepancias")
async def get_discrepancias():
    return facturas.reporte_discrepancias()

@app.post("/sync")
async def sync_data():
    master.setup_schema()
    return {"status": "success", "message": "Estructura y FTS5 actualizados"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5005)
