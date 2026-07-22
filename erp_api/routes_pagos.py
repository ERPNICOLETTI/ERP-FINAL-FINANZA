from fastapi import APIRouter, Request, UploadFile, File
from datetime import datetime
import os
import shutil

from erp_api.helpers import templates
import modulo_pagos.storage_pagos as pagos_storage
from modulo_tarjetas import logica_tarjetas as tarjetas
import modulo_compras.storage_compras as storage
from erp_master import ERPMaster

router = APIRouter()

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
master = ERPMaster(WORKSPACE)

@router.get("/api/pagos")
async def list_pagos(request: Request, estado: str = None, categoria: str = None, periodo_anio: str = None, periodo_mes: str = None, q: str = None, entidad: str = None):
    """Listar todos los vencimientos y pagos devolviendo fragmentos HTML para HTMX."""
    pagos_db = pagos_storage.get_pagos_vencimientos(estado=estado, categoria=categoria, periodo_anio=periodo_anio, periodo_mes=periodo_mes, entidad=entidad)
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    procesados = []
    
    for p in pagos_db:
        p_dict = dict(p)
        
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
                suggestedAmount = p_dict.get('monto_2') if (p_dict.get('monto_2') and p_dict.get('monto_2') > 0) else p_dict.get('monto', 0)
            elif not vto2 and vto1 and hoy > vto1:
                priorityLabel = "VENCIDO 🔥"
                priorityClass = "status-vencido"
            elif vto1 and hoy == vto1:
                priorityLabel = "VENCE HOY 🔔"
                priorityClass = "status-vence-hoy"
            elif vto2 and hoy == vto2:
                priorityLabel = "VENCE HOY ⚠️"
                priorityClass = "status-vence-hoy"
                suggestedAmount = p_dict.get('monto_2') if (p_dict.get('monto_2') and p_dict.get('monto_2') > 0) else p_dict.get('monto', 0)
            elif vto1 and hoy > vto1 and vto2 and hoy < vto2:
                priorityLabel = "2DA OPORTUNID. 🟠"
                priorityClass = "status-vence-proximo"
                suggestedAmount = p_dict.get('monto_2') if (p_dict.get('monto_2') and p_dict.get('monto_2') > 0) else p_dict.get('monto', 0)
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

@router.post("/api/pagos")
async def save_pago_record(data: dict):
    """Guardar o actualizar un registro de pago."""
    pago_id = pagos_storage.save_pago(data)
    if pago_id:
        return {"status": "success", "id": pago_id}
    return {"status": "error", "message": "No se pudo guardar el pago"}

@router.get("/summary")
async def get_summary(anio: str = None):
    res_pw = tarjetas.resumen_ejecutivo(anio)
    res_fac = storage.get_resumen_facturacion(anio)
    return {
        "tarjetas": res_pw,
        "facturacion": res_fac
    }

@router.post("/api/upload/{modulo}")
async def upload_file(modulo: str, file: UploadFile = File(...)):
    """Fase de Recepción v4.6 (Tránsito Crudo)."""
    try:
        inbox_dir = os.path.join(WORKSPACE, f"modulo_{modulo}", f"inbox_{modulo}")
        os.makedirs(inbox_dir, exist_ok=True)
        file_path = os.path.join(inbox_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"status": "success", "message": f"Archivo {file.filename} received en Inbox."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/process")
async def process_inboxes():
    """Gatillo Maestro: Invoca la ingesta global del orquestador."""
    try:
        master.ingest_inbox()
        return {"status": "success", "message": "Procesamiento maestro finalizado"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/search")
async def spotlight_search(q: str):
    """Busqueda 360 estilo Spotlight sobre FTS5"""
    results = storage.smart_search_invoice(q)
    return {"results": results or []}

@router.post("/api/pagos/{pago_id}/comprobante")
async def upload_comprobante(pago_id: int, file: UploadFile = File(...)):
    """Asociar un comprobante físico a un vencimiento y marcarlo como PAGADO, validando coincidencia de datos."""
    temp_path = None
    try:
        # Validar extensión de archivo (PDF e Imágenes)
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_extensions:
            return {"status": "error", "message": "Solo se admiten comprobantes en formato PDF, JPG o PNG para la validación de seguridad."}

        conn = pagos_storage.get_db_connection()
        pago = conn.execute("SELECT * FROM pagos_vencimientos WHERE id = ?", (pago_id,)).fetchone()
        if not pago:
            conn.close()
            return {"status": "error", "message": "Pago no encontrado"}
            
        pago_dict = dict(pago)
        categoria = pago_dict.get('categoria', 'SINDICALES')
        concepto = pago_dict.get('concepto')
        anio = pago_dict.get('periodo_anio')
        mes = pago_dict.get('periodo_mes')
        monto_esperado_1 = pago_dict.get('monto') or 0
        monto_esperado_2 = pago_dict.get('monto_2') or 0
        conn.close()
        
        # 1. Guardar temporalmente para validación
        temp_dir = os.path.join(WORKSPACE, "modulo_pagos", "inbox_pagos", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"temp_val_{pago_id}_{file.filename}")
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Analizar y validar el comprobante
        from modulo_pagos.lectores.lector_pagos import procesar_pago
        ok_parse, parsed_info = procesar_pago(filepath=temp_path)
        
        if not ok_parse or not parsed_info:
            if os.path.exists(temp_path): os.remove(temp_path)
            return {"status": "error", "message": "No se pudo analizar el contenido del comprobante para su validación de seguridad."}

        text_content = parsed_info.get('meta_json', {}).get('full_text', '').upper()
        
        # --- VALIDACIÓN 0: COINCIDENCIA POR CÓDIGO DE BARRAS ESPECÍFICO DE ESTA BOLETA ---
        import re
        barcode_matched = False
        codigo_barras_db = pago_dict.get('codigo_barras')
        if codigo_barras_db and text_content:
            db_digits = "".join(re.findall(r'\d+', str(codigo_barras_db)))
            file_digits = "".join(re.findall(r'\d+', text_content))
            
            # Exigir coincidencia de código de barras completo (no fragmentos genéricos como el CUIT)
            if len(db_digits) >= 30 and len(file_digits) >= 30:
                if db_digits == file_digits or db_digits in file_digits:
                    barcode_matched = True
        
        if barcode_matched:
            print(f"🔒 [PAGOS-VALIDACION] Match atómico por código de barras exacto detectado para ID {pago_id}. Aprobando comprobante.")
        else:
            concept_keywords = {
                'SEC': ['SEC', 'COMERCIO'],
                'FAECYS': ['FAECYS'],
                'INACAP': ['INACAP'],
                'POLICIA': ['POLICIA DEL TRABAJO', 'TASA RETRIBUTIVA'],
                '931': ['931', 'S.U.S.S.', 'AUTONOMOS', 'SICOSS']
            }
            
            if text_content:
                current_kws = concept_keywords.get(concepto, [])
                has_current_kw = any(kw in text_content for kw in current_kws)
                
                if not has_current_kw:
                    for other_concept, other_kws in concept_keywords.items():
                        if other_concept != concepto:
                            if any(kw in text_content for kw in other_kws):
                                if os.path.exists(temp_path): os.remove(temp_path)
                                return {"status": "error", "message": f"El comprobante parece corresponder a {other_concept} (se detectó su palabra clave), pero estás cargándolo en la boleta de {concepto}."}

            # --- VALIDACIÓN 2: PRESENCIA DEL MONTO ESPERADO EN EL TEXTO O PARSER ---
            if text_content:
                monto_parseado = parsed_info.get('monto') or 0
                monto_parseado_cents = int(round(monto_parseado * 100)) if monto_parseado else 0
                
                has_amount = False
                if monto_parseado_cents > 0:
                    if abs(monto_parseado_cents - monto_esperado_1) <= 100:
                        has_amount = True
                    elif monto_esperado_2 and abs(monto_parseado_cents - monto_esperado_2) <= 100:
                        has_amount = True

                if not has_amount:
                    # Formato ES (4.059,02), Formato US (4,059.02), Formato llano (4059,02 / 4059.02)
                    m_1_val = monto_esperado_1 / 100.0
                    m1_es = f"{m_1_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') # 4.000,14
                    m1_us = f"{m_1_val:,.2f}"                                                         # 4,000.14
                    m1_plain_es = f"{m_1_val:.2f}".replace('.', ',')                                 # 4000,14
                    m1_plain_us = f"{m_1_val:.2f}"                                                 # 4000.14
                    
                    has_amount = (m1_es in text_content or 
                                  m1_us in text_content or 
                                  m1_plain_es in text_content or 
                                  m1_plain_us in text_content)
                    
                    if monto_esperado_2:
                        m_2_val = monto_esperado_2 / 100.0
                        m2_es = f"{m_2_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') # 4.059,02
                        m2_us = f"{m_2_val:,.2f}"                                                         # 4,059.02
                        m2_plain_es = f"{m_2_val:.2f}".replace('.', ',')                                 # 4059,02
                        m2_plain_us = f"{m_2_val:.2f}"                                                 # 4059.02
                        
                        has_amount = has_amount or (m2_es in text_content or 
                                                     m2_us in text_content or 
                                                     m2_plain_es in text_content or 
                                                     m2_plain_us in text_content)

                    # Extractor terciario para transferencias bancarias con superíndices de centavos (Banco Galicia, Santander, etc.)
                    if not has_amount:
                        int_m1 = str(int(monto_esperado_1 // 100))
                        int_m1_formatted = f"{int(int_m1):,}".replace(',', '.') # 17.856
                        int_m2 = str(int(monto_esperado_2 // 100)) if monto_esperado_2 else None
                        int_m2_formatted = f"{int(int_m2):,}".replace(',', '.') if int_m2 else None # 17.632
                        
                        # Si matchea la parte entera del monto (17.856 o 17.632)
                        has_amount = (int_m1 in text_content or int_m1_formatted in text_content)
                        if int_m2:
                            has_amount = has_amount or (int_m2 in text_content or int_m2_formatted in text_content)

                if concepto == '931':
                    has_amount = True

                if not has_amount:
                    if os.path.exists(temp_path): os.remove(temp_path)
                    val_esp_1 = f"${monto_esperado_1 / 100:,.2f}"
                    val_esp_2 = f" o ${monto_esperado_2 / 100:,.2f}" if monto_esperado_2 else ""
                    return {"status": "error", "message": f"El comprobante no contiene el monto esperado de {val_esp_1}{val_esp_2}. Verifique que el archivo sea el pago correspondiente a este vencimiento."}

            # --- VALIDACIÓN 3: ESTRUCTURAL DEL PARSER ---
            c_parsed = parsed_info.get('concepto')
            if c_parsed and c_parsed not in ['DESCONOCIDO', 'SINDICAL_GENERICO', 'PAGOS_GENERICO']:
                if c_parsed != concepto:
                    if os.path.exists(temp_path): os.remove(temp_path)
                    return {"status": "error", "message": f"El comprobante corresponde a {c_parsed}, pero estás cargándolo en la boleta de {concepto}."}
            
            m_parsed = parsed_info.get('periodo_mes')
            a_parsed = parsed_info.get('periodo_anio')
            if m_parsed and a_parsed:
                if m_parsed != mes or a_parsed != anio:
                    if os.path.exists(temp_path): os.remove(temp_path)
                    return {"status": "error", "message": f"El período del comprobante ({m_parsed}/{a_parsed}) no coincide con el de la boleta ({mes}/{anio})."}

        # 3. Cumplimiento 100% del TATUAJE SAGRADO ELT: Mover a Inbox para Ingesta Raw a Staging
        inbox_dir = os.path.join(WORKSPACE, "modulo_pagos", "inbox_pagos")
        os.makedirs(inbox_dir, exist_ok=True)
        
        ext = os.path.splitext(file.filename)[1]
        filename = f"{anio}_{mes}_Comprobante_{concepto}{ext}"
        inbox_file_path = os.path.join(inbox_dir, filename)
        
        # Mover desde temp a inbox para ingesta ELT oficial
        if os.path.exists(inbox_file_path):
            os.remove(inbox_file_path)
        shutil.move(temp_path, inbox_file_path)
        
        # 4. Disparar Fase 1 (Ingesta Raw a core_staging_raw + Bóveda) y Fase 2 (Transformación)
        from modulo_pagos.logic_pagos import ingestar_inbox_a_raw, transformar_raw_a_produccion
        st_count = ingestar_inbox_a_raw(inbox_dir)
        tr_count = transformar_raw_a_produccion()
        
        return {"status": "success", "message": f"Comprobante ingestado en Staging Raw ({st_count} raw) y conciliado exitosamente ({tr_count} actualizados)."}
    except Exception as e:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        return {"status": "error", "message": str(e)}

@router.delete("/api/pagos/{pago_id}")
async def delete_pago(pago_id: int):
    """Eliminar un registro de pago y sus registros de staging asociados para permitir re-importar."""
    try:
        conn = pagos_storage.get_db_connection()
        pago = conn.execute("SELECT raw_ingesta_id FROM pagos_vencimientos WHERE id = ?", (pago_id,)).fetchone()
        
        conn.execute("DELETE FROM pagos_vencimientos WHERE id = ?", (pago_id,))
        
        if pago and pago['raw_ingesta_id']:
            conn.execute("DELETE FROM core_staging_raw WHERE id = ?", (pago['raw_ingesta_id'],))
            conn.execute("DELETE FROM core_staging_logs WHERE staging_id = ?", (pago['raw_ingesta_id'],))
            
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Pago y staging eliminados correctamente."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
