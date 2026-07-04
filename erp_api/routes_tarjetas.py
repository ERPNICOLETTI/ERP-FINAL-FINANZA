from fastapi import APIRouter
import os

from erp_api.helpers import ImportRequest
from modulo_tarjetas import logica_tarjetas as tarjetas
from modulo_tarjetas import parser_payway_liq, parser_patagonia, parser_naranja_xlsx

router = APIRouter()

@router.get("/tarjetas/audit")
async def audit_tarjetas():
    return tarjetas.auditoria_360()

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
