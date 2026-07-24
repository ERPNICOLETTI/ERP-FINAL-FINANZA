from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from erp_api.helpers import templates
from modulo_tarjetas import storage_finanzas as storage

router = APIRouter()

@router.get("/finanzas", response_class=HTMLResponse)
async def view_finanzas(request: Request):
    """Renderiza la vista principal del panel de finanzas y conciliación."""
    return templates.TemplateResponse(request=request, name="finanzas.html", context={"request": request})

@router.get("/api/finanzas/reporte", response_class=HTMLResponse)
async def api_get_reporte(
    request: Request,
    periodo_anio: str = Query("2026"),
    periodo_mes: str = Query(""),
    q: str = Query(""),
):
    """Devuelve las filas de la tabla de conciliación de cobros mediante HTMX."""
    movimientos = storage.obtener_reporte_conciliacion(periodo_anio, periodo_mes)
    return templates.TemplateResponse(
        request=request,
        name="tabla_finanzas.html",
        context={
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

@router.get("/api/finanzas/auditoria", response_class=HTMLResponse)
async def api_get_auditoria(
    request: Request,
    periodo_anio: str = Query("2026"),
    periodo_mes: str = Query(""),
):
    """Devuelve la tabla de auditoría detallada de clearing bancario."""
    data = storage.obtener_auditoria_clearing(periodo_anio, periodo_mes)
    return templates.TemplateResponse(
        request=request,
        name="auditoria_clearing.html",
        context={
            "request": request,
            "matches": data["matches"],
            "liquidaciones_huerfanas": data["liquidaciones_huerfanas"],
            "depositos_huerfanos": data["depositos_huerfanos"]
        }
    )

