from fastapi import FastAPI, Query, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import sys
import shutil
import io
from typing import List, Dict, Any
from pydantic import BaseModel
from PIL import Image
from PyPDF2 import PdfMerger
from erp_master import ERPMaster
from datetime import datetime

# IMPORTACIÓN ESTRUCTURADA POR DOMINIOS (DDD) 🏗️🧱🧠⚖️
from modulo_tarjetas import logica_tarjetas as tarjetas
# IMPORTACIÓN DE LIBRERÍAS DE CONTROLADOR DE ALMACENAMIENTO LOCAL
# El control cruzado ocurre aquí a nivel aplicación, FastAPI llama al motor SQLite.
import modulo_compras.storage_compras as storage
import modulo_pagos.storage_pagos as pagos_storage
import modulo_gastos.storage_gastos as storage_gastos
from core_sistema import archiver_service
from modulo_tarjetas import parser_payway_liq, parser_patagonia, parser_naranja_xlsx

def merge_files_to_pdf(existing_path: str, new_path: str, out_path: str):
    """Cerebro de la Engrapadora Virtual (v4.9.3)"""
    merger = PdfMerger()

    def add_to_merger(path):
        ext = path.lower().split('.')[-1]
        try:
            if ext == 'pdf':
                merger.append(path)
            elif ext in ['jpg', 'jpeg', 'png', 'webp']:
                img = Image.open(path).convert('RGB')
                pdf_bytes = io.BytesIO()
                img.save(pdf_bytes, format='PDF')
                pdf_bytes.seek(0)
                merger.append(pdf_bytes)
        except Exception as e:
            print(f"Error engrapando {path}: {e}")

    add_to_merger(existing_path)
    add_to_merger(new_path)

    temp_buffer = io.BytesIO()
    merger.write(temp_buffer)
    merger.close()

    with open(out_path, 'wb') as f:
        f.write(temp_buffer.getvalue())

# ------------------------------------------------------------------------------------------
# ENDPOINTS DE API - MÓDULO COMPRAS
# ------------------------------------------------------------------------------------------

class ImportRequest(BaseModel):
    fuente: str
    path: str

class FacturaUpdate(BaseModel):
    punto_venta: str = None
    numero_comprobante: str = None

app = FastAPI(title="ERP Final API - Área Inteligencia (DDD)", version="4.0.0")

# Motor de Plantillas para HTMX 🚀
templates = Jinja2Templates(directory="frontend")
# ------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------
# ENDPOINTS DE API - TIPOS DE GASTOS (CATEGORIAS)
# ------------------------------------------------------------------------------------------

@app.get("/tipos_gastos")
async def tipos_gastos_page(request: Request):
    return templates.TemplateResponse(request=request, name="tipos_gastos.html", context={"request": request})

@app.get("/api/tipos_gastos/list")
async def list_tipos_gastos(request: Request, cuenta_codigo: str = Query(None)):
    categorias = storage_gastos.get_gastos_tipos(cuenta_codigo)
    return templates.TemplateResponse(request=request, name="tipos_gastos_list.html", context={"request": request, "categorias": categorias})

@app.get("/api/tipos_gastos/form")
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

@app.post("/api/tipos_gastos/save")
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

@app.delete("/api/tipos_gastos/{id}")
async def delete_tipo_gasto(request: Request, id: int):
    storage_gastos.delete_gasto_tipo(id)
    categorias = storage_gastos.get_gastos_tipos()
    return templates.TemplateResponse(request=request, name="tipos_gastos_list.html", context={"request": request, "categorias": categorias})


# ------------------------------------------------------------------------------------------
# ENDPOINTS DE API - CUENTAS MAESTRAS [NUEVO v1.0]
# ------------------------------------------------------------------------------------------

@app.get("/cuentas")
async def cuentas_page(request: Request):
    return templates.TemplateResponse(request=request, name="cuentas.html", context={"request": request})

@app.get("/api/cuentas/list")
async def list_cuentas(request: Request):
    cuentas = storage_gastos.get_cuentas()
    return templates.TemplateResponse(request=request, name="cuentas_list.html", context={"request": request, "cuentas": cuentas})

@app.get("/api/cuentas/form")
async def form_cuenta(request: Request, id: int = None):
    cuenta = None
    if id:
        cuentas = storage_gastos.get_cuentas()
        for c in cuentas:
            if c['id'] == id:
                cuenta = c
                break
    return templates.TemplateResponse(request=request, name="cuentas_form.html", context={"request": request, "cat": cuenta})

@app.post("/api/cuentas/save")
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

@app.delete("/api/cuentas/{id}")
async def delete_cuenta(request: Request, id: int):
    storage_gastos.delete_cuenta(id)
    
    cuentas = storage_gastos.get_cuentas()
    return templates.TemplateResponse(request=request, name="cuentas_list.html", context={"request": request, "cuentas": cuentas})


# ------------------------------------------------------------------------------------------
# ENDPOINTS DE API - REGISTRO DE GASTOS MANUALES
# ------------------------------------------------------------------------------------------

@app.get("/gastos", response_class=HTMLResponse)
async def gastos_page(request: Request):
    cuentas = storage_gastos.get_cuentas()
    return templates.TemplateResponse(request=request, name="gastos.html", context={"request": request, "cuentas": cuentas})

@app.get("/api/gastos/list")
async def list_gastos(request: Request, cuenta_codigo: str = Query(None), mes: str = Query(None)):
    anio = None
    mes_str = None
    if mes and "-" in mes:
        anio, mes_str = mes.split("-")
    elif mes:
        anio = str(datetime.now().year)
        mes_str = mes
        
    registros = storage_gastos.get_gastos_registros(cuenta_codigo, anio, mes_str)
    return templates.TemplateResponse(request=request, name="gastos_list.html", context={"request": request, "registros": registros})

@app.get("/api/gastos/form")
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

@app.get("/api/gastos/form/tipos")
async def form_gasto_tipos(request: Request, cuenta_codigo: str = Query(None), cuenta_codigo_form: str = Query(None)):
    code = cuenta_codigo_form or cuenta_codigo
    tipos_gastos = storage_gastos.get_gastos_tipos(code)
    options_html = '<option value="">Seleccionar tipo...</option>'
    for t in tipos_gastos:
        options_html += f'<option value="{t["id"]}">{t["nombre"]} {t["emoji"] if t["emoji"] else ""}</option>'
    options_html += '<option value="NUEVO">➕ [Crear Concepto Nuevo...]</option>'
    return HTMLResponse(content=options_html)

@app.post("/api/gastos/save")
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
    cuenta_codigo: str = Form(None), 
    mes: str = Form(None)
):
    if gasto_tipo_id == "NUEVO":
        if nuevo_concepto_nombre.strip():
            nombre_clean = nuevo_concepto_nombre.strip()
            existing = None
            # Check if a concept with this name already exists for this account to avoid uniqueness conflict
            all_types = storage_gastos.get_gastos_tipos(cuenta_codigo_form)
            for t in all_types:
                if t['nombre'].lower() == nombre_clean.lower():
                    existing = t
                    break
            
            if existing:
                gasto_tipo_id = existing['id']
            else:
                # Generate color_css automatically based on account
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
        "fuente": fuente
    }
    if id:
        data["id"] = int(id)
    storage_gastos.save_gasto_registro(data)
    
    anio = None
    mes_str = None
    if mes and "-" in mes:
        anio, mes_str = mes.split("-")
        
    registros = storage_gastos.get_gastos_registros(cuenta_codigo if cuenta_codigo else None, anio, mes_str)
    response = templates.TemplateResponse(request=request, name="gastos_list.html", context={"request": request, "registros": registros})
    response.headers["HX-Trigger"] = "reload-gastos"
    return response

@app.delete("/api/gastos/{id}")
async def delete_gasto_record(request: Request, id: int, cuenta_codigo: str = Query(None), mes: str = Query(None)):
    storage_gastos.delete_gasto_registro(id)
    
    # Obtener filtros desde el formulario de HTMX si se enviaron en el body
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

@app.post("/api/gastos/sincronizar")
async def sincronizar_gastos(
    request: Request,
    cuenta_codigo: str = Form(None),
    mes: str = Form(None)
):
    from modulo_bancos import parser_visa_hipotecario
    
    # Resolver WORKSPACE localmente para asegurar el path
    api_dir = os.path.dirname(os.path.abspath(__file__))
    inbox_dir = os.path.join(api_dir, "modulo_bancos", "inbox_bancos")
    crudos_dir = os.path.join(api_dir, "modulo_bancos", "crudos_bancos")
    
    files_to_process = []
    
    # 1. Escanear inbox_bancos
    if os.path.exists(inbox_dir):
        for root, _, files in os.walk(inbox_dir):
            for file in files:
                f_upper = file.upper()
                if f_upper.endswith(".PDF") and ("HIPOTECARIO" in f_upper or "ULTIMALIQUIDACION" in f_upper or "LIQUIDACION" in f_upper):
                    files_to_process.append(os.path.join(root, file))
                    
    # 2. Escanear crudos_bancos/VISA_HIPOTECARIO
    visa_dir = os.path.join(crudos_dir, "VISA_HIPOTECARIO")
    if os.path.exists(visa_dir):
        for root, _, files in os.walk(visa_dir):
            for file in files:
                if file.upper().endswith(".PDF"):
                    files_to_process.append(os.path.join(root, file))
                    
    # 3. Procesar cada archivo con force_reprocess=True
    procesados = 0
    for filepath in files_to_process:
        try:
            success, info = parser_visa_hipotecario.procesar_archivo(filepath, force_reprocess=True)
            if success:
                procesados += 1
        except Exception as e:
            print(f"Error procesando {filepath} durante sincronización: {e}")
            
    # 4. Recuperar los registros filtrados
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
    # Enviar el header de HTMX para refrescar otros componentes reactivos
    response.headers["HX-Trigger"] = "reload-gastos"
    return response

@app.get("/api/gastos/resumen")
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


# Workspace Context
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
master = ERPMaster(WORKSPACE)

import shutil

@app.post("/api/upload/{modulo}")
async def upload_file(modulo: str, file: UploadFile = File(...)):
    """Fase de Recepción v4.6 (Tránsito Crudo)."""
    try:
        inbox_dir = os.path.join(WORKSPACE, f"modulo_{modulo}", f"inbox_{modulo}")
        os.makedirs(inbox_dir, exist_ok=True)
        file_path = os.path.join(inbox_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"status": "success", "message": f"Archivo {file.filename} recibido en Inbox."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/process")
async def process_inboxes():
    """Gatillo Maestro: Invoca la ingesta global del orquestador."""
    try:
        master.ingest_inbox()
        return {"status": "success", "message": "Procesamiento maestro finalizado"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/search")
async def spotlight_search(q: str):
    """Busqueda 360 estilo Spotlight sobre FTS5"""
    results = storage.smart_search_invoice(q)
    return {"results": results or []}

# ------------------------------------------------------------------------------------------
# ENDPOINTS DE API - MÓDULO PAGOS (v5.0.0)
# ------------------------------------------------------------------------------------------

@app.get("/api/pagos")
async def list_pagos(request: Request, estado: str = None, categoria: str = None, periodo_anio: str = None, periodo_mes: str = None, q: str = None):
    """Listar todos los vencimientos y pagos devolviendo fragmentos HTML para HTMX."""
    pagos_db = pagos_storage.get_pagos_vencimientos(estado=estado, categoria=categoria, periodo_anio=periodo_anio, periodo_mes=periodo_mes)
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    procesados = []
    
    for p in pagos_db:
        p_dict = dict(p)
        
        # Búsqueda por concepto/categoría
        if q and q.lower() not in str(p_dict.get('concepto', '')).lower() and q.lower() not in str(p_dict.get('categoria', '')).lower():
            continue
            
        priorityLabel = "Pendiente"
        priorityClass = "status-pendiente"
        suggestedAmount = p_dict.get('monto', 0)
        
        vto1 = p_dict.get('fecha_vencimiento')
        vto2 = p_dict.get('fecha_vencimiento_2')
        estado_pago = p_dict.get('estado')
        
        if estado_pago == 'PAGADO':
            priorityLabel = "PAGADO ✅"
            priorityClass = "status-pagado"
        else:
            if vto2 and hoy > vto2:
                priorityLabel = "VENCIDO 🔥"
                priorityClass = "status-vencido"
                suggestedAmount = p_dict.get('monto_2', 0)
            elif not vto2 and vto1 and hoy > vto1:
                priorityLabel = "VENCIDO 🔥"
                priorityClass = "status-vencido"
            elif vto1 and hoy == vto1:
                priorityLabel = "VENCE HOY 🔔"
                priorityClass = "status-vence-hoy"
            elif vto2 and hoy == vto2:
                priorityLabel = "VENCE HOY ⚠️"
                priorityClass = "status-vence-hoy"
                suggestedAmount = p_dict.get('monto_2', 0)
            elif vto1 and hoy > vto1 and vto2 and hoy < vto2:
                priorityLabel = "2DA OPORTUNID. 🟠"
                priorityClass = "status-vence-proximo"
                suggestedAmount = p_dict.get('monto_2', 0)
            elif vto1 and hoy < vto1:
                try:
                    d1 = datetime.strptime(vto1, "%Y-%m-%d")
                    dhoy = datetime.strptime(hoy, "%Y-%m-%d")
                    days = (d1 - dhoy).days
                    if days <= 3:
                        priorityLabel = f"Vto 1 en {days}d 🟡"
                        priorityClass = "status-vence-hoy"
                except: pass
                
        p_dict['priorityLabel'] = priorityLabel
        p_dict['priorityClass'] = priorityClass
        p_dict['suggestedAmount'] = suggestedAmount
        procesados.append(p_dict)
        
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request=request, name="tabla_pagos.html", context={"request": request, "pagos": procesados, "hoy": hoy})
    return procesados

@app.post("/api/pagos")
async def save_pago_record(data: dict):
    """Guardar o actualizar un registro de pago."""
    pago_id = pagos_storage.save_pago(data)
    if pago_id:
        return {"status": "success", "id": pago_id}
    return {"status": "error", "message": "No se pudo guardar el pago"}


@app.get("/summary")
async def get_summary(anio: str = None):
    res_pw = tarjetas.resumen_ejecutivo(anio)
    res_fac = storage.get_resumen_facturacion(anio)
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

@app.get("/api/bancos/movimientos")
async def list_bancos_movimientos(request: Request, cuenta: str = None, categoria: str = None, mes: str = None, q: str = None, agrupar: str = None, area: str = None):
    """Filtra y devuelve movimientos bancarios para HTMX."""
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    conn.row_factory = storage_bancos.sqlite3.Row
    
    if agrupar == "1":
        query = "SELECT MAX(id) as id, MAX(fecha) as fecha, banco, cuenta, descripcion, categoria, SUM(importe) as importe, COUNT(*) as qty, SUM(saldo) as saldo FROM bancos_movimientos WHERE 1=1"
    else:
        query = "SELECT id, fecha, banco, cuenta, descripcion, categoria, importe, saldo, 1 as qty FROM bancos_movimientos WHERE 1=1"
    
    params = []
    
    if cuenta:
        # Usamos LIKE para soportar "CHUBUT" que a veces no tiene nro de cuenta exacto aún
        query += " AND cuenta LIKE ?"
        params.append(f"%{cuenta}%")
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    if mes:
        query += " AND strftime('%m', fecha) = ?"
        params.append(mes)
    if q:
        query += " AND (descripcion LIKE ? OR CAST(importe AS TEXT) LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if area:
        conn_cat = storage_bancos.get_db_connection()
        cursor_cat = conn_cat.execute("SELECT nombre FROM gastos_tipos WHERE cuenta_codigo = ?", (area,))
        cat_names = [row[0] for row in cursor_cat.fetchall()]
        conn_cat.close()
        
        if cat_names:
            query += f" AND categoria IN ({','.join(['?'] * len(cat_names))})"
            params.extend(cat_names)
        else:
            query += " AND 1=0"
        
    if agrupar == "1":
        query += " GROUP BY descripcion, categoria ORDER BY qty DESC, fecha DESC"
    else:
        # Ordenar por fecha ascendente (lo más viejo arriba). Si hay empate, id DESC para respetar la cronología del día
        query += " ORDER BY fecha ASC, id DESC"
    
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    movimientos = [dict(r) for r in rows]
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request=request, name="tabla_bancos.html", context={"request": request, "movimientos": movimientos})
    return movimientos

@app.get("/api/bancos/movimientos/{id}/edit_categoria")
async def edit_mov_categoria(request: Request, id: int):
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    conn.row_factory = storage_bancos.sqlite3.Row
    categorias = conn.execute("SELECT nombre, emoji FROM gastos_tipos ORDER BY tipo, nombre").fetchall()
    conn.close()
    return templates.TemplateResponse(request=request, name="bancos_inline_edit.html", context={"request": request, "id": id, "categorias": categorias})

@app.put("/api/bancos/movimientos/{id}/categoria")
async def save_mov_categoria(request: Request, id: int, categoria: str = Form(...)):
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    conn.execute("UPDATE bancos_movimientos SET categoria=? WHERE id=?", (categoria, id))
    conn.commit()
    conn.row_factory = storage_bancos.sqlite3.Row
    mov = conn.execute("SELECT * FROM bancos_movimientos WHERE id=?", (id,)).fetchone()
    conn.close()
    return templates.TemplateResponse(request=request, name="bancos_badge_cell.html", context={"request": request, "mov": mov})

@app.post("/api/bancos/movimientos/bulk_categoria")
async def bulk_edit_categoria(request: Request, new_categoria: str = Form(...), cuenta: str = Form(None), categoria: str = Form(None), mes: str = Form(None), q: str = Form(None), agrupar: str = Form(None), area: str = Form(None)):
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    
    where_clause = "1=1"
    params = []
    
    if cuenta:
        where_clause += " AND cuenta LIKE ?"
        params.append(f"%{cuenta}%")
    if categoria:
        where_clause += " AND categoria = ?"
        params.append(categoria)
    if mes:
        where_clause += " AND strftime('%m', fecha) = ?"
        params.append(mes)
    if q:
        where_clause += " AND (descripcion LIKE ? OR CAST(importe AS TEXT) LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if area:
        conn_cat = storage_bancos.get_db_connection()
        cursor_cat = conn_cat.execute("SELECT nombre FROM gastos_tipos WHERE cuenta_codigo = ?", (area,))
        cat_names = [row[0] for row in cursor_cat.fetchall()]
        conn_cat.close()
        
        if cat_names:
            where_clause += f" AND categoria IN ({','.join(['?'] * len(cat_names))})"
            params.extend(cat_names)
        else:
            where_clause += " AND 1=0"
        
    query = f"UPDATE bancos_movimientos SET categoria = ? WHERE {where_clause}"
    update_params = [new_categoria] + params
    conn.execute(query, update_params)
    conn.commit()
    conn.close()
    
    # Return the updated list using the existing list function
    # Because we don't know the agrupar state, we default to non-grouped after bulk edit
    return await list_bancos_movimientos(request, cuenta, categoria, mes, q, agrupar, area)

@app.get("/api/bancos/kpis")
async def get_bancos_kpis(request: Request, cuenta: str = None, categoria: str = None, mes: str = None, q: str = None, area: str = None):
    """Devuelve los KPIs financieros actualizados según los filtros actuales."""
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    
    query = "SELECT sum(importe) FROM bancos_movimientos WHERE importe > 0"
    query_neg = "SELECT sum(importe) FROM bancos_movimientos WHERE importe < 0"
    
    params = []
    filtros = ""
    if cuenta:
        filtros += " AND cuenta LIKE ?"
        params.append(f"%{cuenta}%")
    if categoria:
        filtros += " AND categoria = ?"
        params.append(categoria)
    if mes:
        filtros += " AND strftime('%m', fecha) = ?"
        params.append(mes)
    if q:
        filtros += " AND (descripcion LIKE ? OR CAST(importe AS TEXT) LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if area:
        conn_cat = storage_bancos.get_db_connection()
        cursor_cat = conn_cat.execute("SELECT nombre FROM gastos_tipos WHERE cuenta_codigo = ?", (area,))
        cat_names = [row[0] for row in cursor_cat.fetchall()]
        conn_cat.close()
        
        if cat_names:
            filtros += f" AND categoria IN ({','.join(['?'] * len(cat_names))})"
            params.extend(cat_names)
        else:
            filtros += " AND 1=0"
        
    ingresos = conn.execute(query + filtros, params).fetchone()[0] or 0.0
    egresos = conn.execute(query_neg + filtros, params).fetchone()[0] or 0.0
    conn.close()
    
    html = f'''
        <div class="kpi-card">
            <h4>Total Ingresos 📈</h4>
            <div class="value val-positive">$ {"{:,.2f}".format(ingresos).replace(',', 'X').replace('.', ',').replace('X', '.')}</div>
        </div>
        <div class="kpi-card">
            <h4>Total Egresos 📉</h4>
            <div class="value val-negative">$ {"{:,.2f}".format(egresos).replace(',', 'X').replace('.', ',').replace('X', '.')}</div>
        </div>
        <div class="kpi-card">
            <h4>Flujo Neto ⚖️</h4>
            <div class="value" style="color: {'#10b981' if (ingresos+egresos) >= 0 else '#ef4444'}">$ {"{:,.2f}".format(ingresos + egresos).replace(',', 'X').replace('.', ',').replace('X', '.')}</div>
        </div>
    '''
    return HTMLResponse(content=html)

@app.get("/api/facturas")
async def list_facturas(request: Request, anio: str = None, mes: str = None, estado: str = "all", q: str = None):
    """Listado de facturas con soporte HTMX y Jinja2."""
    data = storage.get_all_compras_facturas(anio, mes)
    
    procesados = []
    for f in data:
        # Filtro de búsqueda (q)
        if q:
            term = q.lower()
            if term not in str(f.get('proveedor', '')).lower() and \
               term not in str(f.get('cuit_proveedor', '')).lower() and \
               term not in str(f.get('numero_comprobante', '')).lower():
                continue
                
        # Filtro por estado
        tiene_foto = bool(f.get('tiene_foto') or f.get('path_archivo'))
        if estado == "pending" and tiene_foto: continue
        if estado == "completed" and not tiene_foto: continue
        
        procesados.append(f)
        
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request=request, name="tabla_compras.html", context={"request": request, "facturas": procesados})
    
    return procesados

@app.post("/api/facturas/update/{fid}")
async def update_factura(fid: int, req: FacturaUpdate):
    """Actualiza campos específicos de una factura (Confirmación de Padding)."""
    fields = {k: v for k, v in req.dict().items() if v is not None}
    if not fields: return {"status": "ignored"}
    success = storage.update_factura_fields(fid, fields)
    return {"status": "success" if success else "error"}

@app.get("/api/compras/search")
async def search_compras_match(q: str):
    """Búsqueda elástica para feedback atómico (v4.8)."""
    if not q or len(q) < 3: return {"status": "too_short"}
    results = storage.smart_search_invoice(q)
    return {"results": results}

@app.get("/api/compras/inbox/list")
async def list_inbox_files():
    """Devuelve la lista de archivos pendientes en el Inbox (v4.9)."""
    inbox_dir = os.path.join(WORKSPACE, "modulo_compras", "inbox_compras")
    os.makedirs(inbox_dir, exist_ok=True)
    files = [f for f in os.listdir(inbox_dir) if os.path.isfile(os.path.join(inbox_dir, f)) and f.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg'))]
    return {"files": files}

@app.post("/api/compras/vincular")
async def vincular_archivo_factura(
    id_factura: int = Query(0), 
    file: UploadFile = File(None),
    inbox_filename: str = Form(None),
    is_pending_calim: str = Form("false"),
    proveedor_nombre: str = Form(""),
    numero_factura: str = Form("")
):
    """Vincula físicamente un archivo a una factura, o archiva en espera (v4.9)."""
    try:
        temp_dir = os.path.join(WORKSPACE, "modulo_compras", "inbox_compras")
        os.makedirs(temp_dir, exist_ok=True)
        
        # --- MODO 1: Excepción (Pendiente CALIM) ---
        if is_pending_calim.lower() == "true":
            if not inbox_filename and not file:
                return {"status": "error", "message": "No hay archivo para Sala de Espera"}
                
            cuit = "00000000000"
            proveedor = proveedor_nombre.strip().upper() if proveedor_nombre else "PENDIENTE_CALIM"
            fecha = datetime.now().strftime("%Y-%m-%d")
            pv = "XX"
            num = numero_factura.strip() if numero_factura else str(int(datetime.now().timestamp()))
            
            # Obtener archivo origen
            if inbox_filename:
                temp_path = os.path.join(temp_dir, inbox_filename)
                _, ext = os.path.splitext(inbox_filename)
                if not os.path.exists(temp_path): return {"status": "error"}
            else:
                _, ext = os.path.splitext(file.filename)
                temp_path = os.path.join(temp_dir, f"temp_upload_calim_{num}{ext}")
                with open(temp_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            
            entidad_vault = f"{cuit} - PENDIENTES CALIM"
            final_path = archiver_service.archivar_documento(
                temp_path, "compras", fecha[:4], fecha[5:7], entidad_vault, use_vault=True, overwrite=True, subcategoria="Facturas"
            ).replace('\\', '/')
            
            if final_path and os.path.exists(final_path):
                prov_clean = "".join([c if c.isalnum() else "_" for c in proveedor]).strip("_")
                target_name = f"{fecha}_{prov_clean}_Factura_{pv}-{num}{ext.lower()}"
                final_dir = os.path.dirname(final_path).replace('\\', '/')
                new_final_path = f"{final_dir}/{target_name}"
                
                if os.path.exists(new_final_path): os.remove(new_final_path)
                os.rename(final_path, new_final_path)
                final_path = new_final_path.replace('\\', '/')
                
                # Inyección a Base de Datos como PENDIENTE
                storage.save_factura({
                    "cuit_proveedor": cuit,
                    "proveedor": proveedor,
                    "punto_venta": pv,
                    "numero_comprobante": num,
                    "fecha": fecha,
                    "tipo_operacion": "COMPRA",
                    "tipo_comprobante": "88", # Código interno para Pendientes
                    "origen": "PENDIENTE_CALIM",
                    "status": "SALA_ESPERA",
                    "tiene_foto": 1,
                    "path_archivo": final_path
                })
            
            return {"status": "success", "message": "Enviado a Sala de Espera CALIM"}

        # --- MODO 2: Normal ---
        # 1. Recuperar datos de la factura
        f_data = storage.get_factura_by_id(id_factura)
        if not f_data: return {"status": "error", "message": "Factura no encontrada"}
        
        cuit = f_data.get('cuit_proveedor')
        proveedor = f_data.get('proveedor') or 'DESCONOCIDO'
        fecha = f_data.get('fecha') or '2026-01-01'
        pv = f_data.get('punto_venta') or '00000'
        num = f_data.get('numero_comprobante') or '00000000'
        
        if inbox_filename:
            temp_path = os.path.join(temp_dir, inbox_filename)
            _, ext = os.path.splitext(inbox_filename)
            if not os.path.exists(temp_path): return {"status": "error", "message": "Archivo de inbox perdido"}
        else:
            _, ext = os.path.splitext(file.filename)
            temp_path = os.path.join(temp_dir, f"temp_upload_{id_factura}{ext}")
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

        # 3. VERIFICAR SI APLICAMOS ENGRAPADORA VIRTUAL O ARCHIVADOR NORMAL
        tiene_foto = bool(f_data.get('tiene_foto', 0))
        old_path = f_data.get('path_archivo', '')
        
        if tiene_foto and old_path and os.path.exists(old_path):
            # ENGRAPADORA VIRTUAL (Multi-página Detectado)
            prov_clean = "".join([c if c.isalnum() else "_" for c in proveedor]).strip("_")
            target_name = f"{fecha}_{prov_clean}_Factura_{pv}-{num}.pdf"
            
            final_dir = os.path.dirname(old_path).replace('\\', '/')
            new_final_path = f"{final_dir}/{target_name}"
            
            # Fusionar ambos (el previo de la bd y el nuevo entrante)
            merge_files_to_pdf(old_path, temp_path, new_final_path)
            
            # Limpieza post-ensamblaje
            if os.path.exists(temp_path): os.remove(temp_path)
            if old_path != new_final_path and os.path.exists(old_path):
                os.remove(old_path)
                
            final_path = new_final_path.replace('\\', '/')
            
        else:
            # 3. Invocar Archivador Nominal Estandar (v4.8)
            entidad_vault = f"{cuit} - {proveedor}" if cuit else proveedor
            final_path = archiver_service.archivar_documento(
                temp_path, 
                "compras", 
                fecha[:4], 
                fecha[5:7], 
                entidad_vault,
                use_vault=True,
                overwrite=True,
                subcategoria="Facturas"
            ).replace('\\', '/')

            # 4. Renombrado Nominal: Fecha_Proveedor_Factura_PV-NUM
            if final_path and os.path.exists(final_path):
                prov_clean = "".join([c if c.isalnum() else "_" for c in proveedor]).strip("_")
                target_name = f"{fecha}_{prov_clean}_Factura_{pv}-{num}{ext.lower()}"
                
                final_dir = os.path.dirname(final_path)
                new_final_path = os.path.join(final_dir, target_name)
                
                if os.path.exists(new_final_path): os.remove(new_final_path)
                os.rename(final_path, new_final_path)
                final_path = new_final_path
            
        # El archivo temporal temp_path ya fue MOVIDO/ELIMINADO por archiver_service.archivar_documento
        # (shutil.move se encarga de la limpieza de origen)
        
        if final_path:
            # Calcular ruta relativa para el servidor estático
            # El servidor estático apunta a modulo_compras/archivos_compras
            base_archive = os.path.join(WORKSPACE, "modulo_compras", "archivos_compras")
            rel_path = os.path.relpath(final_path, base_archive)
            
            # 4. Actualizar estado y sello
            storage.update_factura_fields(id_factura, {
                "path_archivo": rel_path,
                "tiene_foto": 1,
                "status": "ARCHIVADO"
            })
            
            return {
                "status": "success", 
                "message": "Archivo vinculado y archivado por CUIT",
                "rel_path": rel_path
            }
        
        return {"status": "error", "message": "Fallo al archivar documento físicamente"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/sync")
async def sync_data():
    master.setup_schema()
    return {"status": "success", "message": "Estructura y FTS5 actualizados"}

# Montar servidores estáticos jerárquicos (Aislamiento v4.6)
os.makedirs(os.path.join(WORKSPACE, "modulo_compras", "archivos_compras"), exist_ok=True)
os.makedirs(os.path.join(WORKSPACE, "modulo_compras", "crudos_compras"), exist_ok=True)
os.makedirs(os.path.join(WORKSPACE, "modulo_compras", "inbox_compras"), exist_ok=True)

# Directorios de Pagos
os.makedirs(os.path.join(WORKSPACE, "modulo_pagos", "archivos_pagos"), exist_ok=True)

app.mount("/archivos/compras", StaticFiles(directory="modulo_compras/archivos_compras"), name="archivos_compras")
app.mount("/archivos/pagos", StaticFiles(directory="modulo_pagos/archivos_pagos"), name="archivos_pagos")
app.mount("/historico/compras", StaticFiles(directory="modulo_compras/crudos_compras"), name="crudos_compras")
app.mount("/inbox", StaticFiles(directory="modulo_compras/inbox_compras"), name="inbox_local")
# ENDPOINTS DE VISTAS (HTMX + Jinja2)
@app.get("/", response_class=HTMLResponse)
async def home_dashboard(request: Request):
    """Renderiza el dashboard inicial con soporte para contexto dinámico."""
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.get("/compras", response_class=HTMLResponse)
async def vista_compras(request: Request):
    return templates.TemplateResponse(request=request, name="compras.html", context={"request": request})

@app.get("/bancos", response_class=HTMLResponse)
async def vista_bancos(request: Request):
    cuentas = storage_gastos.get_cuentas()
    categorias = storage_gastos.get_gastos_tipos()
    return templates.TemplateResponse(request=request, name="bancos.html", context={"request": request, "cuentas": cuentas, "categorias": categorias})

@app.get("/pagos", response_class=HTMLResponse)
async def vista_pagos(request: Request):
    return templates.TemplateResponse(request=request, name="pagos.html", context={"request": request})

# Montar servidores estáticos jerárquicos (Aislamiento v4.6)
app.mount("/static", StaticFiles(directory="frontend"), name="static_frontend") # Para css/js futuros
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend_legacy")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5005)
