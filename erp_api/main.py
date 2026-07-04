from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from erp_master import ERPMaster

# 1. Initialize FastAPI app
app = FastAPI(title="ERP Final API - Área Inteligencia (DDD)", version="4.0.0")

# 2. Setup Workspace
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
master = ERPMaster(WORKSPACE)

# Ensure folders exist
os.makedirs(os.path.join(WORKSPACE, "modulo_compras", "archivos_compras"), exist_ok=True)
os.makedirs(os.path.join(WORKSPACE, "modulo_compras", "crudos_compras"), exist_ok=True)
os.makedirs(os.path.join(WORKSPACE, "modulo_compras", "inbox_compras"), exist_ok=True)
os.makedirs(os.path.join(WORKSPACE, "modulo_pagos", "archivos_pagos"), exist_ok=True)

# 3. Mount Static Folders
app.mount("/archivos/compras", StaticFiles(directory=os.path.join(WORKSPACE, "modulo_compras/archivos_compras")), name="archivos_compras")
app.mount("/archivos/pagos", StaticFiles(directory=os.path.join(WORKSPACE, "modulo_pagos/archivos_pagos")), name="archivos_pagos")
app.mount("/historico/compras", StaticFiles(directory=os.path.join(WORKSPACE, "modulo_compras/crudos_compras")), name="crudos_compras")
app.mount("/inbox", StaticFiles(directory=os.path.join(WORKSPACE, "modulo_compras/inbox_compras")), name="inbox_local")

# 4. Import and Include APIRouters
from erp_api.routes_pages import router as pages_router
from erp_api.routes_gastos import router as gastos_router
from erp_api.routes_bancos import router as bancos_router
from erp_api.routes_tarjetas import router as tarjetas_router
from erp_api.routes_compras import router as compras_router
from erp_api.routes_pagos import router as pagos_router

# Include routes (the order can be important if we have catch-all/legacy mounts)
app.include_router(pages_router)
app.include_router(gastos_router)
app.include_router(bancos_router)
app.include_router(tarjetas_router)
app.include_router(compras_router)
app.include_router(pagos_router)

# 5. Core Actions
@app.post("/sync")
async def sync_data():
    master.setup_schema()
    return {"status": "success", "message": "Estructura y FTS5 actualizados"}

# 6. Legacy Front-end static files mounts (mount at the end to avoid routing conflicts)
app.mount("/static", StaticFiles(directory=os.path.join(WORKSPACE, "frontend")), name="static_frontend")
app.mount("/", StaticFiles(directory=os.path.join(WORKSPACE, "frontend"), html=True), name="frontend_legacy")
