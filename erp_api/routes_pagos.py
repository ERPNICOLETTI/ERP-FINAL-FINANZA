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
        
        if ok_parse and parsed_info:
            text_content = parsed_info.get('meta_json', {}).get('full_text', '').upper()
            
            # --- VALIDACIÓN 0: COINCIDENCIA POR CÓDIGO DE BARRAS / CÓDIGO DE PAGO ---
            # Si el comprobante contiene el código de barras (o una subcadena significativa de al menos 15 dígitos)
            # que coincida con el de la boleta, la validación se aprueba de inmediato.
            import re
            barcode_matched = False
            codigo_barras_db = pago_dict.get('codigo_barras')
            if codigo_barras_db and text_content:
                db_digits = "".join(re.findall(r'\d+', str(codigo_barras_db)))
                file_digits = "".join(re.findall(r'\d+', text_content))
                
                min_len = 15
                if len(db_digits) >= min_len and len(file_digits) >= min_len:
                    if db_digits in file_digits or file_digits in db_digits:
                        barcode_matched = True
                    else:
                        for i in range(len(db_digits) - min_len + 1):
                            if db_digits[i:i+min_len] in file_digits:
                                barcode_matched = True
                                break
            
            if barcode_matched:
                print(f"🔒 [PAGOS-VALIDACION] Match atómico por código de barras/pago detectado para ID {pago_id}. Aprobando comprobante.")
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
                    
                    # Si el archivo tiene texto legible pero NO tiene la palabra clave de este concepto,
                    # y SÍ tiene la palabra clave de otro concepto diferente, entonces lo bloqueamos.
                    if not has_current_kw:
                        for other_concept, other_kws in concept_keywords.items():
                            if other_concept != concepto:
                                if any(kw in text_content for kw in other_kws):
                                    if os.path.exists(temp_path): os.remove(temp_path)
                                    return {"status": "error", "message": f"El comprobante parece corresponder a {other_concept} (se detectó su palabra clave), pero estás cargándolo en la boleta de {concepto}."}

                # --- VALIDACIÓN 2: PRESENCIA DEL MONTO ESPERADO EN EL TEXTO ---
                if text_content:
                    # Construir representaciones en texto de los montos esperados
                    monto_str_1a = f"{monto_esperado_1 / 100:.2f}".replace('.', ',') # Ej: 25.830,80 -> 25830,80
                    monto_str_1b = f"{monto_esperado_1 / 100:.2f}"                  # Ej: 25830.80
                    # Quitar puntos de miles si existieran en el texto
                    clean_text = text_content.replace('.', '').replace(' ', '')
                    monto_clean_1 = f"{monto_esperado_1 / 100:.2f}".replace('.', '').replace(',','') # Ej: 2583080
                    
                    # Fallback de parte entera para tolerar errores de OCR en centavos (ej: ",35" leído como "%")
                    int_1 = str(int(monto_esperado_1 / 100)) # Ej: 16094
                    int_1_dots = f"{int(monto_esperado_1 / 100):,}".replace(',', '.') # Ej: 16.094
                    
                    has_amount = (monto_str_1a in text_content or 
                                  monto_str_1b in text_content or 
                                  monto_clean_1 in clean_text or
                                  int_1 in clean_text or
                                  int_1_dots in text_content)
                    
                    if monto_esperado_2:
                        monto_str_2a = f"{monto_esperado_2 / 100:.2f}".replace('.', ',')
                        monto_str_2b = f"{monto_esperado_2 / 100:.2f}"
                        monto_clean_2 = f"{monto_esperado_2 / 100:.2f}".replace('.', '').replace(',','')
                        
                        int_2 = str(int(monto_esperado_2 / 100)) # Ej: 16241
                        int_2_dots = f"{int(monto_esperado_2 / 100):,}".replace(',', '.') # Ej: 16.241
                        
                        has_amount = has_amount or (monto_str_2a in text_content or 
                                                     monto_str_2b in text_content or 
                                                     monto_clean_2 in clean_text or
                                                     int_2 in clean_text or
                                                     int_2_dots in text_content)
                    
                    if concepto == '931':
                        has_amount = True

                    if not has_amount:
                        if os.path.exists(temp_path): os.remove(temp_path)
                        val_esp_1 = f"${monto_esperado_1 / 100:,.2f}"
                        val_esp_2 = f" o ${monto_esperado_2 / 100:,.2f}" if monto_esperado_2 else ""
                        return {"status": "error", "message": f"El comprobante no contiene el monto esperado de {val_esp_1}{val_esp_2}. Verifique que el archivo sea correcto."}

                # --- VALIDACIÓN 3: VALIDACIÓN ESTRUCTURAL DEL PARSER (FALLBACK) ---
                # Validar concepto (Ej: SEC, FAECYS) si el parser lo identificó específicamente
                c_parsed = parsed_info.get('concepto')
                if c_parsed and c_parsed not in ['DESCONOCIDO', 'SINDICAL_GENERICO', 'PAGOS_GENERICO']:
                    if c_parsed != concepto:
                        if os.path.exists(temp_path): os.remove(temp_path)
                        return {"status": "error", "message": f"El comprobante corresponde a {c_parsed}, pero estás cargándolo en la boleta de {concepto}."}
                
                # Validar período (Mes / Año)
                m_parsed = parsed_info.get('periodo_mes')
                a_parsed = parsed_info.get('periodo_anio')
                if m_parsed and a_parsed:
                    if m_parsed != mes or a_parsed != anio:
                        if os.path.exists(temp_path): os.remove(temp_path)
                        return {"status": "error", "message": f"El período del comprobante ({m_parsed}/{a_parsed}) no coincide con el de la boleta ({mes}/{anio})."}
                
                # Validar monto sugerido si el parser leyó uno específico
                monto_parsed = parsed_info.get('monto')
                if monto_parsed:
                    monto_cents = int(round(float(monto_parsed) * 100))
                    diff_1 = abs(monto_cents - monto_esperado_1)
                    diff_2 = abs(monto_cents - monto_esperado_2) if monto_esperado_2 else 999999
                    
                    if concepto == '931':
                        # Toleramos diferencias por intereses resarcitorios/punitorios en F.931
                        pass
                    elif diff_1 > 500 and diff_2 > 500:
                        if os.path.exists(temp_path): os.remove(temp_path)
                        return {"status": "error", "message": f"El monto del comprobante (${monto_parsed:,.2f}) no coincide con los montos esperados de la boleta."}

        # 3. Si pasó la validación, guardar en la bóveda física definitiva
        dest_dir = os.path.join(WORKSPACE, "modulo_pagos", "archivos_pagos", categoria, concepto, anio, mes)
        os.makedirs(dest_dir, exist_ok=True)
        
        ext = os.path.splitext(file.filename)[1]
        filename = f"Comprobante_{concepto}_{mes}_{anio}{ext}"
        dest_path = os.path.join(dest_dir, filename)
        
        # Mover desde temp a destino final
        shutil.move(temp_path, dest_path)
        
        # 4. Actualizar en BD
        db_path_compro = f"modulo_pagos/archivos_pagos/{categoria}/{concepto}/{anio}/{mes}/{filename}"
        
        update_data = {
            "id": pago_id,
            "concepto": concepto,
            "periodo_mes": mes,
            "periodo_anio": anio,
            "path_comprobante": db_path_compro,
            "estado": "PAGADO"
        }
        
        pagos_storage.save_pago(update_data)
        return {"status": "success", "message": "Comprobante vinculado y estado cambiado a PAGADO."}
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
