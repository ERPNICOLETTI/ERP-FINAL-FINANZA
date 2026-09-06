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

@router.get("/joa", response_class=HTMLResponse)
async def vista_joa(request: Request):
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    import sqlite3
    conn.row_factory = sqlite3.Row
    # JOA usa un catálogo unificado: primero sus tipos personales/compartidos y
    # luego las categorías bancarias que todavía no tengan equivalente.
    categorias_por_nombre = {}
    tipos_joa = conn.execute("""
        SELECT nombre, tipo, emoji
        FROM gastos_tipos
        WHERE cuenta_codigo IN ('JOA', 'COMUN', 'JOR')
        ORDER BY CASE cuenta_codigo WHEN 'JOA' THEN 1 WHEN 'COMUN' THEN 2 ELSE 3 END,
                 tipo, nombre
    """).fetchall()
    for row in tipos_joa:
        categorias_por_nombre.setdefault(row["nombre"].strip().casefold(), dict(row))
    for row in conn.execute("SELECT nombre, tipo, emoji FROM categorias_maestras ORDER BY tipo, nombre"):
        categorias_por_nombre.setdefault(row["nombre"].strip().casefold(), dict(row))
    categorias = sorted(
        categorias_por_nombre.values(), key=lambda item: (item.get("tipo") or "OTRO", item["nombre"].casefold())
    )
    meses_es = (
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    )
    resumenes_tarjeta = []
    summary_rows = conn.execute("""
        SELECT id, periodo, fecha_cierre, cantidad_consumos AS consumos,
               conciliado
        FROM gastos_tarjeta_resumenes
        WHERE fuente='Visa Hipotecario' AND titular_codigo='JOA'
        ORDER BY fecha_cierre DESC, id DESC
    """).fetchall()
    for row in summary_rows:
        year, month = row["periodo"].split("-")
        close_day = row["fecha_cierre"][8:10]
        resumenes_tarjeta.append({
            "value": str(row["id"]),
            "label": f"{meses_es[int(month) - 1]} {year} · cierre {close_day}/{month}",
            "consumos": row["consumos"],
            "conciliado": bool(row["conciliado"]),
        })
    # Compatibilidad visual mientras se migra un histórico leído por la versión
    # anterior, que no persistía cabeceras de resumen.
    if not resumenes_tarjeta:
        for row in conn.execute("""
            SELECT substr(fecha, 1, 7) AS periodo, COUNT(*) AS consumos
            FROM gastos_registros
            WHERE fuente='Visa Hipotecario' AND fecha GLOB '????-??-*'
            GROUP BY substr(fecha, 1, 7)
            ORDER BY periodo DESC
        """):
            year, month = row["periodo"].split("-")
            resumenes_tarjeta.append({
                "value": f"period:{row['periodo']}",
                "label": f"{meses_es[int(month) - 1]} {year} · histórico",
                "consumos": row["consumos"],
                "conciliado": False,
            })
    conn.close()

    # Solo las cuentas de Joaquín
    cuentas_joa = [
        {"codigo": "CA$ ...9087", "nombre": "Hipotecario (Caja Ahorro $ - JOA)"},
        {"codigo": "CA U$D ...2646", "nombre": "Hipotecario (Caja Ahorro U$D - JOA)"}
    ]
    return templates.TemplateResponse(
        request=request,
        name="joa.html",
        context={
            "request": request, "cuentas": cuentas_joa, "categorias": categorias,
            "resumenes_tarjeta": resumenes_tarjeta,
        }
    )
