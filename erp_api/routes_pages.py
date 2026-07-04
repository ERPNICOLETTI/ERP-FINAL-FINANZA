from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from erp_api.helpers import templates
import modulo_gastos.storage_gastos as storage_gastos

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def home_dashboard(request: Request):
    """Renderiza el dashboard inicial con soporte para contexto dinámico."""
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@router.get("/compras", response_class=HTMLResponse)
async def vista_compras(request: Request):
    return templates.TemplateResponse(request=request, name="compras.html", context={"request": request})

@router.get("/bancos", response_class=HTMLResponse)
async def vista_bancos(request: Request):
    cuentas = storage_gastos.get_cuentas()
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    # sqlite3 is imported inside storage_bancos
    import sqlite3
    conn.row_factory = sqlite3.Row
    categorias = [dict(r) for r in conn.execute("SELECT * FROM categorias_maestras ORDER BY tipo, nombre").fetchall()]
    conn.close()
    return templates.TemplateResponse(request=request, name="bancos.html", context={"request": request, "cuentas": cuentas, "categorias": categorias})

@router.get("/pagos", response_class=HTMLResponse)
async def vista_pagos(request: Request):
    return templates.TemplateResponse(request=request, name="pagos.html", context={"request": request})
