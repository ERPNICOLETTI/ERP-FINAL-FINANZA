from fastapi import APIRouter, Request, Query, Form
from fastapi.responses import HTMLResponse
from datetime import datetime
import os

import modulo_gastos.storage_gastos as storage_gastos
from erp_api.helpers import templates, aprender_palabra_clave

router = APIRouter()

# ------------------------------------------------------------------------------------------
# ENDPOINTS DE API - TIPOS DE GASTOS (CATEGORIAS)
# ------------------------------------------------------------------------------------------

@router.get("/tipos_gastos")
async def tipos_gastos_page(request: Request):
    return templates.TemplateResponse(request=request, name="tipos_gastos.html", context={"request": request})

@router.get("/api/tipos_gastos/list")
async def list_tipos_gastos(request: Request, cuenta_codigo: str = Query(None)):
    categorias = storage_gastos.get_gastos_tipos(cuenta_codigo)
    return templates.TemplateResponse(request=request, name="tipos_gastos_list.html", context={"request": request, "categorias": categorias})

@router.get("/api/tipos_gastos/form")
async def form_tipo_gasto(request: Request, id: int = None, cuenta_codigo: str = Query(None)):
    cat = None
    selected_cuenta = cuenta_codigo
    if id:
        cat = storage_gastos.get_gasto_tipo_by_id(id)
        if cat:
            selected_cuenta = cat['cuenta_codigo']
    cuentas = storage_gastos.get_cuentas()
    return templates.TemplateResponse(request=request, name="tipos_gastos_form.html", context={
        "request": request, 
        "cat": cat, 
        "cuentas": cuentas,
        "selected_cuenta": selected_cuenta
    })

@router.post("/api/tipos_gastos/save")
async def save_tipo_gasto(request: Request, id: str = Form(""), nombre: str = Form(...), tipo: str = Form(...), emoji: str = Form(""), palabras_clave: str = Form(""), cuenta_codigo: str = Form(None)):
    color_css = "rgba(156, 163, 175, 0.2); color: #9ca3af" # Default gray
    if cuenta_codigo == "LDK":
        color_css = "rgba(16, 185, 129, 0.2); color: #10b981"
    elif cuenta_codigo == "JOA":
        color_css = "rgba(56, 189, 248, 0.2); color: #38bdf8"
    elif cuenta_codigo == "JOR":
        color_css = "rgba(244, 114, 182, 0.2); color: #f472b6"
    elif cuenta_codigo == "COMUN":
        color_css = "rgba(234, 179, 8, 0.2); color: #eab308"

    data = {
        "nombre": nombre,
        "tipo": tipo,
        "emoji": emoji,
        "color_css": color_css,
        "palabras_clave": palabras_clave,
        "cuenta_codigo": cuenta_codigo if cuenta_codigo else None
    }
    if id:
        data["id"] = int(id)
    storage_gastos.save_gasto_tipo(data)
    
    categorias = storage_gastos.get_gastos_tipos()
    return templates.TemplateResponse(request=request, name="tipos_gastos_list.html", context={"request": request, "categorias": categorias})

@router.delete("/api/tipos_gastos/{id}")
async def delete_tipo_gasto(request: Request, id: int):
    storage_gastos.delete_gasto_tipo(id)
    categorias = storage_gastos.get_gastos_tipos()
    return templates.TemplateResponse(request=request, name="tipos_gastos_list.html", context={"request": request, "categorias": categorias})


# ------------------------------------------------------------------------------------------
# ENDPOINTS DE API - CUENTAS MAESTRAS [NUEVO v1.0]
# ------------------------------------------------------------------------------------------

@router.get("/cuentas")
async def cuentas_page(request: Request):
    return templates.TemplateResponse(request=request, name="cuentas.html", context={"request": request})

@router.get("/api/cuentas/list")
async def list_cuentas(request: Request):
    cuentas = storage_gastos.get_cuentas()
    return templates.TemplateResponse(request=request, name="cuentas_list.html", context={"request": request, "cuentas": cuentas})

@router.get("/api/cuentas/form")
async def form_cuenta(request: Request, id: int = None):
    cuenta = None
    if id:
        cuentas = storage_gastos.get_cuentas()
        for c in cuentas:
            if c['id'] == id:
                cuenta = c
                break
    return templates.TemplateResponse(request=request, name="cuentas_form.html", context={"request": request, "cat": cuenta})

@router.post("/api/cuentas/save")
async def save_cuenta(request: Request, id: str = Form(""), nombre: str = Form(...), codigo: str = Form(...), emoji: str = Form(""), color_css: str = Form(""), descripcion: str = Form("")):
    data = {
        "nombre": nombre,
        "codigo": codigo.upper().strip(),
        "emoji": emoji,
        "color_css": color_css,
        "descripcion": descripcion
    }
    if id:
        data["id"] = int(id)
    storage_gastos.save_cuenta(data)
    
    cuentas = storage_gastos.get_cuentas()
    return templates.TemplateResponse(request=request, name="cuentas_list.html", context={"request": request, "cuentas": cuentas})

@router.delete("/api/cuentas/{id}")
async def delete_cuenta(request: Request, id: int):
    storage_gastos.delete_cuenta(id)
    
    cuentas = storage_gastos.get_cuentas()
    return templates.TemplateResponse(request=request, name="cuentas_list.html", context={"request": request, "cuentas": cuentas})


# ------------------------------------------------------------------------------------------
# ENDPOINTS DE API - REGISTRO DE GASTOS MANUALES
# ------------------------------------------------------------------------------------------

@router.get("/gastos", response_class=HTMLResponse)
async def gastos_page(request: Request):
    cuentas = storage_gastos.get_cuentas()
    return templates.TemplateResponse(request=request, name="gastos.html", context={"request": request, "cuentas": cuentas})

@router.get("/api/gastos/list")
async def list_gastos(request: Request, cuenta_codigo: str = Query(None), mes: str = Query(None), fuente: str = Query(None), q: str = Query(None)):
    anio = None
    mes_str = None
    if mes and "-" in mes:
        anio, mes_str = mes.split("-")
    elif mes:
        anio = str(datetime.now().year)
        mes_str = mes
        
    registros = storage_gastos.get_gastos_registros(cuenta_codigo, anio, mes_str, fuente, q)
    return templates.TemplateResponse(request=request, name="gastos_list.html", context={"request": request, "registros": registros})

@router.get("/api/gastos/form")
async def form_gasto(request: Request, id: int = None, cuenta_codigo: str = None):
    reg = None
    current_cuenta = cuenta_codigo
    if id:
        reg = storage_gastos.get_gasto_registro_by_id(id)
        if reg:
            current_cuenta = reg['cuenta_codigo']
            
    cuentas = storage_gastos.get_cuentas()
    tipos_gastos = storage_gastos.get_gastos_tipos(current_cuenta) if current_cuenta else []
    return templates.TemplateResponse(request=request, name="gastos_form.html", context={
        "request": request, 
        "reg": reg, 
        "cuentas": cuentas, 
        "tipos_gastos": tipos_gastos,
        "selected_cuenta": current_cuenta
    })

@router.get("/api/gastos/form/tipos")
async def form_gasto_tipos(request: Request, cuenta_codigo: str = Query(None), cuenta_codigo_form: str = Query(None)):
    code = cuenta_codigo_form or cuenta_codigo
    tipos_gastos = storage_gastos.get_gastos_tipos(code)
    options_html = '<option value="">Seleccionar tipo...</option>'
    for t in tipos_gastos:
        options_html += f'<option value="{t["id"]}">{t["nombre"]} {t["emoji"] if t["emoji"] else ""}</option>'
    options_html += '<option value="NUEVO">➕ [Crear Concepto Nuevo...]</option>'
    return HTMLResponse(content=options_html)

@router.post("/api/gastos/save")
async def save_gasto_record(
    request: Request, 
    id: str = Form(""), 
    gasto_tipo_id: str = Form(...), 
    cuenta_codigo_form: str = Form(None),
    nuevo_concepto_nombre: str = Form(""),
    nuevo_concepto_emoji: str = Form(""),
    monto: float = Form(...), 
    fecha: str = Form(...), 
    descripcion: str = Form(""), 
    fuente: str = Form("Manual"),
    fecha_compra: str = Form(None),
    cuenta_codigo: str = Form(None), 
    mes: str = Form(None)
):
    if gasto_tipo_id == "NUEVO":
        if nuevo_concepto_nombre.strip():
            nombre_clean = nuevo_concepto_nombre.strip()
            existing = None
            all_types = storage_gastos.get_gastos_tipos(cuenta_codigo_form)
            for t in all_types:
                if t['nombre'].lower() == nombre_clean.lower():
                    existing = t
                    break
            
            if existing:
                gasto_tipo_id = existing['id']
            else:
                color_css = "rgba(156, 163, 175, 0.2); color: #9ca3af"
                if cuenta_codigo_form == "LDK":
                    color_css = "rgba(16, 185, 129, 0.2); color: #10b981"
                elif cuenta_codigo_form == "JOA":
                    color_css = "rgba(56, 189, 248, 0.2); color: #38bdf8"
                elif cuenta_codigo_form == "JOR":
                    color_css = "rgba(244, 114, 182, 0.2); color: #f472b6"
                elif cuenta_codigo_form == "COMUN":
                    color_css = "rgba(234, 179, 8, 0.2); color: #eab308"
                    
                new_type_id = storage_gastos.save_gasto_tipo({
                    "cuenta_codigo": cuenta_codigo_form,
                    "nombre": nombre_clean,
                    "tipo": "EGRESO",
                    "emoji": nuevo_concepto_emoji.strip() if nuevo_concepto_emoji.strip() else "💸",
                    "color_css": color_css,
                    "palabras_clave": ""
                })
                gasto_tipo_id = new_type_id
        else:
            raise ValueError("El nombre del nuevo concepto no puede estar vacío.")
    else:
        gasto_tipo_id = int(gasto_tipo_id)

    data = {
        "gasto_tipo_id": gasto_tipo_id,
        "monto": monto,
        "fecha": fecha,
        "descripcion": descripcion,
        "fuente": fuente,
        "fecha_compra": fecha_compra if fecha_compra else fecha
    }
    if id:
        data["id"] = int(id)
        try:
            original = storage_gastos.get_gasto_registro_by_id(int(id))
            if original and original['gasto_tipo_id'] != gasto_tipo_id:
                aprender_palabra_clave(gasto_tipo_id, original['descripcion'])
        except Exception as e:
            print(f"Error en aprendizaje automático de gastos: {e}")
    storage_gastos.save_gasto_registro(data)
    
    anio = None
    mes_str = None
    if mes and "-" in mes:
        anio, mes_str = mes.split("-")
        
    registros = storage_gastos.get_gastos_registros(cuenta_codigo if cuenta_codigo else None, anio, mes_str)
    response = templates.TemplateResponse(request=request, name="gastos_list.html", context={"request": request, "registros": registros})
    response.headers["HX-Trigger"] = "reload-gastos"
    return response

@router.delete("/api/gastos/{id}")
async def delete_gasto_record(request: Request, id: int, cuenta_codigo: str = Query(None), mes: str = Query(None)):
    storage_gastos.delete_gasto_registro(id)
    
    if not cuenta_codigo or not mes:
        try:
            form_data = await request.form()
            if not cuenta_codigo:
                cuenta_codigo = form_data.get("cuenta_codigo")
            if not mes:
                mes = form_data.get("mes")
        except Exception:
            pass
            
    anio = None
    mes_str = None
    if mes and "-" in mes:
        anio, mes_str = mes.split("-")
        
    registros = storage_gastos.get_gastos_registros(cuenta_codigo if cuenta_codigo else None, anio, mes_str)
    response = templates.TemplateResponse(request=request, name="gastos_list.html", context={"request": request, "registros": registros})
    response.headers["HX-Trigger"] = "reload-gastos"
    return response

@router.post("/api/gastos/sincronizar")
async def sincronizar_gastos(
    request: Request,
    cuenta_codigo: str = Form(None),
    mes: str = Form(None)
):
    from modulo_bancos.lectores import (
        lector_visa_hipotecario, 
        lector_visa_galicia,
        lector_mastercard_galicia,
        lector_naranja_pdf,
        lector_patagonia_pdf
    )
    from erp_master import detectar_parser_pdf
    
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inbox_dir = os.path.join(api_dir, "modulo_bancos", "inbox_bancos")
    crudos_dir = os.path.join(api_dir, "modulo_bancos", "crudos_bancos")
    
    files_to_process = []
    
    if os.path.exists(inbox_dir):
        for root, _, files in os.walk(inbox_dir):
            for file in files:
                if file.upper().endswith(".PDF"):
                    files_to_process.append(os.path.join(root, file))
                    
    for sub in ["VISA_HIPOTECARIO", "VISA_GALICIA", "MASTERCARD_GALICIA", "TARJETA_NARANJA", "PATAGONIA365"]:
        subdir = os.path.join(crudos_dir, sub)
        if os.path.exists(subdir):
            for root, _, files in os.walk(subdir):
                for file in files:
                    if file.upper().endswith(".PDF"):
                        files_to_process.append(os.path.join(root, file))
                        
    procesados = 0
    for filepath in files_to_process:
        try:
            detected_type = detectar_parser_pdf(filepath)
            if detected_type == "VISA_HIPOTECARIO":
                success, info = lector_visa_hipotecario.procesar_archivo(filepath, force_reprocess=True)
                if success:
                    procesados += 1
            elif detected_type == "VISA_GALICIA":
                success, info = lector_visa_galicia.procesar_archivo(filepath, force_reprocess=True)
                if success:
                    procesados += 1
            elif detected_type == "MASTERCARD_GALICIA":
                success, info = lector_mastercard_galicia.procesar_archivo(filepath, force_reprocess=True)
                if success:
                    procesados += 1
            elif detected_type == "TARJETA_NARANJA":
                success, info = lector_naranja_pdf.procesar_archivo(filepath, force_reprocess=True)
                if success:
                    procesados += 1
            elif detected_type == "PATAGONIA365_PDF":
                success, info = lector_patagonia_pdf.procesar_archivo(filepath, force_reprocess=True)
                if success:
                    procesados += 1
        except Exception as e:
            print(f"Error procesando {filepath} durante sincronización: {e}")
            
    anio = None
    mes_str = None
    if mes and "-" in mes:
        anio, mes_str = mes.split("-")
        
    registros = storage_gastos.get_gastos_registros(cuenta_codigo if cuenta_codigo else None, anio, mes_str)
    
    response = templates.TemplateResponse(
        request=request, 
        name="gastos_list.html", 
        context={"request": request, "registros": registros}
    )
    response.headers["HX-Trigger"] = "reload-gastos"
    return response

@router.get("/api/gastos/resumen")
async def get_gastos_resumen_view(request: Request, mes: str = Query(...)):
    if not mes or "-" not in mes:
        return HTMLResponse(content='<div style="color: #888;">Selecciona un mes para ver el resumen...</div>')
        
    anio, mes_str = mes.split("-")
    resumen = storage_gastos.get_gastos_resumen(anio, mes_str)
    
    por_cuenta = {}
    total_general = 0.0
    for r in resumen:
        cc = r['cuenta_codigo']
        if cc not in por_cuenta:
            por_cuenta[cc] = {"tipos": [], "total": 0.0}
        por_cuenta[cc]["tipos"].append(r)
        por_cuenta[cc]["total"] += r['total']
        total_general += r['total']
        
    cuentas = storage_gastos.get_cuentas()
    cuenta_map = {c['codigo']: c for c in cuentas}
    
    return templates.TemplateResponse(request=request, name="gastos_resumen.html", context={
        "request": request,
        "por_cuenta": por_cuenta,
        "cuenta_map": cuenta_map,
        "total_general": total_general,
        "periodo_label": f"{mes_str}/{anio}"
    })
