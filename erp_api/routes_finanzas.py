from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

from modulo_tarjetas import storage_finanzas as storage

router = APIRouter()
WORKSPACE = r"c:\Users\essao\Desktop\ERP FINAL"
templates = Jinja2Templates(directory=os.path.join(WORKSPACE, "frontend"))

@router.get("/finanzas", response_class=HTMLResponse)
async def view_finanzas(request: Request):
    """Renderiza la vista principal del panel de finanzas y conciliación."""
    return templates.TemplateResponse("finanzas.html", {"request": request})

@router.get("/api/finanzas/reporte", response_class=HTMLResponse)
async def api_get_reporte(
    request: Request,
    periodo_anio: str = Query("2026"),
    periodo_mes: str = Query(""),
    q: str = Query(""),
):
    """Devuelve las filas de la tabla de conciliación de cobros mediante HTMX."""
    movimientos = storage.obtener_reporte_conciliacion(periodo_anio, periodo_mes, q)
    return templates.TemplateResponse(
        "tabla_finanzas.html",
        {
            "request": request,
            "movimientos": movimientos
        }
    )

@router.get("/api/finanzas/kpis", response_class=HTMLResponse)
async def api_get_kpis(
    request: Request,
    periodo_anio: str = Query("2026"),
    periodo_mes: str = Query(""),
):
    """Devuelve las tarjetas KPI para el panel superior de finanzas."""
    kpis = storage.obtener_kpis_finanzas(periodo_anio, periodo_mes)
    
    html = f"""
    <div class="kpi-card">
        <h3>Ventas Totales Local</h3>
        <p class="monto-kpi">${kpis['total_ventas']:,.2f}</p>
        <span class="sub-kpi">Efectivo + Tarjeta</span>
    </div>
    <div class="kpi-card">
        <h3>Ventas con Tarjeta</h3>
        <p class="monto-kpi">${kpis['ventas_tarjetas']:,.2f}</p>
        <span class="sub-kpi">Posnet y Mercado Pago</span>
    </div>
    <div class="kpi-card warning">
        <h3>Retenciones y Aranceles</h3>
        <p class="monto-kpi">${kpis['comisiones_aranceles']:,.2f}</p>
        <span class="sub-kpi">Descontado por procesadoras</span>
    </div>
    <div class="kpi-card success">
        <h3>Tasa de Acreditación</h3>
        <p class="monto-kpi">{kpis['tasa_acreditacion']}%</p>
        <span class="sub-kpi">Conciliado con Bancos</span>
    </div>
    """
    return HTMLResponse(content=html)
