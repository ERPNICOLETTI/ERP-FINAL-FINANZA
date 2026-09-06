from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
import os

from erp_api.helpers import ImportRequest
from erp_api.helpers import templates
from modulo_tarjetas import logica_tarjetas as tarjetas
from modulo_tarjetas.lectores import lector_payway_liq, lector_patagonia, lector_naranja_xlsx

router = APIRouter()


@router.get("/payway", response_class=HTMLResponse)
async def panel_payway(
    request: Request,
    fecha_desde: str = Query("2026-08-01", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    fecha_hasta: str = Query("2026-08-31", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    data = tarjetas.conciliacion_payway(fecha_desde, fecha_hasta)
    return templates.TemplateResponse(request=request, name="payway.html", context={"request": request, "data": data})

@router.get("/tarjetas/audit")
async def audit_tarjetas():
    return tarjetas.auditoria_360()


@router.get("/api/tarjetas/payway/conciliacion")
async def conciliacion_payway(
    fecha_desde: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    fecha_hasta: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    if fecha_desde > fecha_hasta:
        return {"error": "fecha_desde no puede ser posterior a fecha_hasta"}
    return tarjetas.conciliacion_payway(fecha_desde, fecha_hasta)

@router.get("/tarjetas/cupon/{cid}")
async def get_cupon(cid: str):
    res = tarjetas.buscar_cupon(cid)
    if res: return res
    return {"error": "Cupón no encontrado"}

@router.post("/tarjetas/importar")
async def importar_tarjetas(req: ImportRequest):
    """Gatilla una importación selectiva desde archivos locales."""
    try:
        fuente = req.fuente.upper()
        if fuente == 'PAYWAY':
            success, info = lector_payway_liq.procesar_archivo(req.path)
            return {"status": "success" if success else "error", "fuente": "PAYWAY", "detalle": info}
        
        elif fuente == 'PATAGONIA365':
            lector_patagonia.parse_patagonia_365(req.path)
            return {"status": "success", "fuente": "PATAGONIA365"}
            
        elif fuente == 'NARANJA':
            if os.path.isdir(req.path):
                import glob
                archivos = glob.glob(os.path.join(req.path, "*.xlsx"))
                for a in archivos:
                    lector_naranja_xlsx.parse_naranja_xlsx(a)
            else:
                lector_naranja_xlsx.parse_naranja_xlsx(req.path)
            return {"status": "success", "fuente": "NARANJA"}
            
        return {"status": "error", "message": f"Fuente '{fuente}' no soportada"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
