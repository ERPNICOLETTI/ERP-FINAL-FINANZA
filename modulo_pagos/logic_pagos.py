import os
import re
import json
import shutil
import hashlib
import traceback
import logging
from datetime import datetime
from core_sistema import conversores
from core_sistema.archiver_service import archivar_documento
from modulo_pagos.storage_pagos import get_db_connection, save_pago, find_pago_record
from modulo_pagos.lectores.lector_pagos import procesar_pago

# LOGIC PAGOS - v6.0.0 (ELT Pipeline Unificado) 🚀🧠⚖️

logger = logging.getLogger(__name__)

TAXONOMIA = {
    'SINDICALES': ['SEC', 'FAECYS', 'INACAP', 'POLICIA', 'SINDICAL'],
    'IMPUESTOS':  ['IIBB', 'IVA', 'GANANCIAS', 'AFIP', 'ARBA', 'AUTONOMO', '931'],
    'SERVICIOS':  ['SERVICOOP', 'REDUNO', 'LUZ', 'GAS', 'AGUA', 'TELEFON', 'ALQUILER', 'TIENDANUBE'],
}

def calcular_hash_archivo(filepath):
    """Calcula el hash SHA-256 de un archivo para control de duplicados."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()

def ingestar_inbox_a_raw(inbox_path):
    """
    Fase 1: Ingesta Centralizada a Staging.
    Verifica firma, tamaño, duplicados, convierte a Markdown e inserta en core_staging_raw.
    Mueve el archivo original a la Bóveda de Crudos.
    """
    if not os.path.exists(inbox_path):
        os.makedirs(inbox_path, exist_ok=True)
        return 0

    no_reconocidos_dir = os.path.join(inbox_path, 'no_reconocidos')
    os.makedirs(no_reconocidos_dir, exist_ok=True)

    archivos_procesados = 0
    # Escaneo recursivo del inbox
    for root, dirs, files in os.walk(inbox_path):
        # Evitar procesar recursivamente dentro de no_reconocidos
        if 'no_reconocidos' in root:
            continue
            
        for f in files:
            filepath_origen = os.path.join(root, f)
            if not os.path.isfile(filepath_origen):
                continue

            f_upper = f.upper()
            print(f"\n📥 [PAGOS-ELT] Ingestando archivo físico: {f}")

            # 1. Validación de tamaño (0 bytes)
            try:
                size = os.path.getsize(filepath_origen)
                if size == 0:
                    print(f"⚠️ [PAGOS-ELT] Archivo vacío (0 bytes): {f}. Desviando a no_reconocidos.")
                    shutil.move(filepath_origen, os.path.join(no_reconocidos_dir, f))
                    continue
            except Exception as e:
                logger.error(f"Error al verificar tamaño del archivo {f}: {e}")
                continue

            # 2. Validación de tipo (PDF y ZIP para pagos)
            if not f_upper.endswith('.PDF') and not f_upper.endswith('.ZIP'):
                print(f"⚠️ [PAGOS-ELT] Formato no soportado: {f}. Desviando a no_reconocidos.")
                import shutil
                shutil.move(filepath_origen, os.path.join(no_reconocidos_dir, f))
                continue

            # 3. Control de Duplicados Temprano por Hash
            file_hash = calcular_hash_archivo(filepath_origen)
            conn = get_db_connection()
            dup = conn.execute("SELECT id FROM core_staging_raw WHERE hash_sha256 = ?", (file_hash,)).fetchone()
            if dup:
                print(f"🚫 [PAGOS-ELT] Archivo duplicado detectado (Hash {file_hash[:10]}...). Eliminando del inbox.")
                conn.close()
                os.remove(filepath_origen)
                continue

            # 4. Conversión Temprana a Markdown / Extracción de ZIP
            markdown_text = ""
            try:
                if f_upper.endswith('.ZIP'):
                    import zipfile, io, pypdf
                    with zipfile.ZipFile(filepath_origen, 'r') as z:
                        for name in z.namelist():
                            if name.upper().startswith('__MACOSX') or name.startswith('.'):
                                continue
                            data = z.read(name)
                            pdf_file = io.BytesIO(data)
                            reader = pypdf.PdfReader(pdf_file)
                            pdf_text = '\n'.join([page.extract_text() or '' for page in reader.pages])
                            markdown_text += f"\n## ARCHIVO: {name}\n" + pdf_text + "\n"
                else:
                    markdown_text = conversores.convertir_pdf_a_markdown(filepath_origen)
            except Exception as e:
                print(f"❌ [PAGOS-ELT] Error al extraer contenido de {f}: {e}. Desviando.")
                conn.close()
                import shutil
                shutil.move(filepath_origen, os.path.join(no_reconocidos_dir, f))
                continue

            # 5. Validación Temprana de Firma (Uso de procesar_pago para alineación de carpetas)
            text_upper = markdown_text.upper()
            concepto_detectado = 'PAGOS_GENERICO'
            categoria_detectada = 'OTROS'
            
            ok_parse, parsed_info = procesar_pago(text_content=markdown_text)
            if ok_parse and parsed_info and parsed_info.get('concepto') not in ['DESCONOCIDO', 'SINDICAL_GENERICO']:
                concepto_detectado = parsed_info['concepto']
                categoria_detectada = parsed_info['categoria']
            else:
                # Fallback taxonomía si el parser no da coincidencia exacta
                for cat, conceptos in TAXONOMIA.items():
                    for conc in conceptos:
                        if len(conc) <= 4:
                            pattern = r'\b' + re.escape(conc) + r'\b'
                            if re.search(pattern, text_upper) or re.search(pattern, f_upper):
                                concepto_detectado = conc
                                categoria_detectada = cat
                                break
                        else:
                            if conc in text_upper or conc in f_upper:
                                concepto_detectado = conc
                                categoria_detectada = cat
                                break
                    if concepto_detectado != 'PAGOS_GENERICO':
                        break

            if concepto_detectado == 'PAGOS_GENERICO':
                print(f"⚠️ [PAGOS-ELT] Firma no reconocida en el contenido para: {f}. Desviando a no_reconocidos.")
                conn.close()
                import shutil
                shutil.move(filepath_origen, os.path.join(no_reconocidos_dir, f))
                continue

            # 6. Extraer periodo tentativo para la Bóveda de Crudos
            anio_tentativo = parsed_info.get('periodo_anio') if (ok_parse and parsed_info and parsed_info.get('periodo_anio')) else datetime.now().strftime("%Y")
            mes_tentativo = parsed_info.get('periodo_mes') if (ok_parse and parsed_info and parsed_info.get('periodo_mes')) else datetime.now().strftime("%m")
            
            if not parsed_info.get('periodo_mes') or not parsed_info.get('periodo_anio'):
                # Fallback por nombre de archivo si el parser no encontró periodo
                patron_fecha = re.search(r'(\d{2})-(\d{4})|(\d{4})-(\d{2})', f)
                if patron_fecha:
                    if patron_fecha.group(1):
                        mes_tentativo, anio_tentativo = patron_fecha.group(1), patron_fecha.group(2)
                    else:
                        anio_tentativo, mes_tentativo = patron_fecha.group(3), patron_fecha.group(4)
                else:
                    m = re.search(r'PER[IÍI]ODO[:\s]+(\d{2})/(\d{4})', text_upper)
                    if m:
                        mes_tentativo, anio_tentativo = m.group(1), m.group(2)

            # 7. Insertar en Staging (Estado PENDIENTE)
            cursor = conn.execute('''
                INSERT INTO core_staging_raw (
                    nombre_archivo, hash_sha256, modulo, tipo_fuente, formato_raw, parser_version, contenido_raw, estado
                ) VALUES (?, ?, 'pagos', ?, 'MD', '6.0.0', ?, 'PENDIENTE')
            ''', (f, file_hash, concepto_detectado, markdown_text))
            staging_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # 8. Nombre Canónico e Inyección en Bóveda de Crudos
            prefijo = "Comprobante" if any(kw in f_upper for kw in ['PAGO', 'COMPROBANTE', 'TICKET', 'RECIBO', 'TRANSFERENCIA']) else "Boleta"
            ext = ".zip" if f_upper.endswith('.ZIP') else ".pdf"
            nombre_canonico = f"{prefijo}_{concepto_detectado}_{mes_tentativo}_{anio_tentativo}{ext}"

            try:
                path_final = archivar_documento(
                    filepath_origen=filepath_origen,
                    modulo='pagos',
                    anio=anio_tentativo,
                    mes=mes_tentativo,
                    entidad=concepto_detectado,
                    subcategoria=categoria_detectada,
                    forced_filename=nombre_canonico
                )
                if path_final:
                    print(f"✅ [PAGOS-ELT] Archivado en Bóveda: {os.path.basename(path_final)}")
                    # Eliminar el archivo del inbox
                    if os.path.exists(filepath_origen):
                        os.remove(filepath_origen)
                    archivos_procesados += 1
            except Exception as e:
                logger.error(f"Error al archivar archivo en Bóveda: {e}")

    return archivos_procesados

def transformar_raw_a_produccion():
    """
    Fase 2: Transformación Atómica.
    Lee de core_staging_raw, parsea el texto, mapea importes a centavos y actualiza las tablas definitivas.
    """
    conn = get_db_connection()
    registros_pendientes = conn.execute('''
        SELECT id, nombre_archivo, tipo_fuente, contenido_raw 
        FROM core_staging_raw 
        WHERE modulo = 'pagos' AND estado = 'PENDIENTE'
    ''').fetchall()
    
    if not registros_pendientes:
        conn.close()
        return 0

    print(f"\n🔄 [PAGOS-ELT] Iniciando Fase 2 de Transformación para {len(registros_pendientes)} registros...")
    procesados = 0

    for reg in registros_pendientes:
        staging_id = reg['id']
        nombre_orig = reg['nombre_archivo']
        concepto_detectado = reg['tipo_fuente']
        contenido = reg['contenido_raw']

        # Transacción atómica por archivo
        db_transaction = get_db_connection()
        try:
            # 1. Ejecutar el parser sobre el texto Markdown/Raw de la DB
            ok, info = procesar_pago(text_content=contenido)
            if not ok or not info:
                raise ValueError("El parser de pagos no pudo extraer información válida del contenido raw.")

            # Detectar si es comprobante por nombre original de archivo
            es_comprobante = False
            for kw in ['PAGO', 'COMPROBANTE', 'TICKET', 'RECIBO', 'TRANSFERENCIA']:
                if kw in nombre_orig.upper():
                    es_comprobante = True
                    break
            info['es_comprobante'] = es_comprobante

            # Validar periodo
            mes = info.get('periodo_mes')
            anio = info.get('periodo_anio')
            barras = info.get('codigo_barras')

            # Si no hay periodo pero hay barras, intentar recobrar periodo
            if (not anio or not mes) and barras:
                reco = db_transaction.execute('''
                    SELECT periodo_mes, periodo_anio FROM pagos_vencimientos 
                    WHERE codigo_barras = ? LIMIT 1
                ''', (barras,)).fetchone()
                if reco:
                    mes = reco['periodo_mes']
                    anio = reco['periodo_anio']

            # Fallback de periodo por nombre del archivo
            if not anio or not mes:
                mf = re.search(r'_(\d{2})-(\d{4})_', nombre_orig.upper())
                if mf:
                    mes, anio = mf.group(1), mf.group(2)

            if not anio or not mes:
                raise ValueError(f"No se pudo determinar el período MM/YYYY para el archivo {nombre_orig}")

            # Construir la ruta canónica relativa a la Bóveda para guardar en DB
            prefijo = "Comprobante" if es_comprobante else "Boleta"
            ext = ".zip" if nombre_orig.upper().endswith('.ZIP') else ".pdf"
            nombre_canonico = f"{prefijo}_{info['concepto']}_{mes}_{anio}{ext}"
            path_relativo = f"modulo_pagos/archivos_pagos/{info['categoria']}/{info['concepto']}/{anio}/{mes}/{nombre_canonico}"

            # Estructurar datos para persistencia
            data_sql = {
                'concepto':           info['concepto'],
                'categoria':          info['categoria'],
                'entidad':            info.get('entidad', 'LDK'),
                'periodo_mes':        mes,
                'periodo_anio':       anio,
                'monto':              info.get('monto') or 0,
                'fecha_vencimiento':  info.get('fecha_vencimiento') or f"{anio}-{mes}-10",
                'monto_2':            info.get('monto_2') or 0,
                'fecha_vencimiento_2':info.get('fecha_vencimiento_2'),
                'meta_json':          info.get('meta_json', {}),
                'codigo_barras':      barras,
                'raw_ingesta_id':     staging_id,
                'numero_linea':       1
            }

            if es_comprobante:
                monto_pagado = info.get('monto') or 0
                
                # Intentar buscar la boleta existente para conciliación
                boleta = None
                if barras:
                    boleta = db_transaction.execute("SELECT id, monto, monto_2 FROM pagos_vencimientos WHERE codigo_barras = ?", (barras,)).fetchone()
                if not boleta:
                    boleta = db_transaction.execute("SELECT id, monto, monto_2 FROM pagos_vencimientos WHERE concepto = ? AND periodo_mes = ? AND periodo_anio = ?", (info['concepto'], mes, anio)).fetchone()
                
                if boleta:
                    # NOTA: Los montos de la boleta ya están guardados en centavos (enteros) en la base de datos
                    # Por lo tanto, multiplicamos el monto_pagado del comprobante por 100 para comparar manzanas con manzanas.
                    monto_pagado_cents = int(round(monto_pagado * 100))
                    m1 = boleta['monto']
                    m2 = boleta['monto_2']
                    
                    if abs(monto_pagado_cents - m1) < 100 or (m2 and abs(monto_pagado_cents - m2) < 100):
                        data_sql['path_comprobante'] = path_relativo
                    else:
                        raise ValueError(f"Discrepancia de monto en conciliación de pago. Boleta espera {m1/100.0}/{m2/100.0}, Comprobante dice {monto_pagado}")
                else:
                    # Pago huérfano
                    data_sql['path_comprobante'] = path_relativo
            else:
                data_sql['path_boleta'] = path_relativo

            # Persistir en la tabla pagos_vencimientos (las columnas monto/monto_2 se guardan como centavos enteros)
            # Pasamos la conexión activa para asegurar atomicidad
            pago_id = save_pago_con_conexion(db_transaction, data_sql)
            
            if not pago_id:
                raise RuntimeError("No se pudo insertar/actualizar el registro definitivo de pagos_vencimientos.")

            # Actualizar Staging a PROCESADO
            db_transaction.execute('''
                UPDATE core_staging_raw 
                SET estado = 'PROCESADO', fecha_procesado = CURRENT_TIMESTAMP, mensaje_error = NULL, filas_leidas = 1
                WHERE id = ?
            ''', (staging_id,))

            # Escribir log de éxito
            db_transaction.execute('''
                INSERT INTO core_staging_logs (staging_id, resultado, detalles)
                VALUES (?, 'SUCCESS', ?)
            ''', (staging_id, f"Procesado exitosamente. Registro pagos_vencimientos ID: {pago_id}"))

            db_transaction.commit()
            print(f"✅ [PAGOS-ELT] Transformado: {info['concepto']} ({mes}/{anio})")
            procesados += 1

        except Exception as e:
            db_transaction.rollback()
            err_msg = str(e)
            trace = traceback.format_exc()
            logger.warning(f"❌ [PAGOS-ELT] Error en transformación del staging ID {staging_id}: {err_msg}")
            
            # Escribir log de error en Staging (afuera de la transacción del registro pero actualizando el staging)
            db_err = get_db_connection()
            db_err.execute('''
                UPDATE core_staging_raw 
                SET estado = 'ERROR', mensaje_error = ?
                WHERE id = ?
            ''', (err_msg, staging_id))
            db_err.execute('''
                INSERT INTO core_staging_logs (staging_id, resultado, detalles)
                VALUES (?, 'ERROR', ?)
            ''', (staging_id, f"Error: {err_msg}\n{trace}"))
            db_err.commit()
            db_err.close()
        finally:
            db_transaction.close()

    conn.close()
    return procesados

def save_pago_con_conexion(conn, data: dict):
    """Auxiliar para guardar pagos usando una conexión transaccional activa."""
    p_boleta = data.get('path_boleta')
    p_comprobante = data.get('path_comprobante')
    concepto = data.get('concepto')
    periodo_mes = data.get('periodo_mes')
    periodo_anio = data.get('periodo_anio')
    codigo_barras = data.get('codigo_barras')
    
    # Escalar montos a centavos enteros
    monto_cents = int(round(float(data.get('monto') or 0) * 100))
    monto_2_cents = int(round(float(data.get('monto_2') or 0) * 100))
    
    res = None
    if codigo_barras:
        res = conn.execute('SELECT id, estado, path_boleta, path_comprobante, monto, monto_2, fecha_vencimiento, fecha_vencimiento_2 FROM pagos_vencimientos WHERE codigo_barras = ?', (codigo_barras,)).fetchone()
    if not res:
        res = conn.execute('SELECT id, estado, path_boleta, path_comprobante, monto, monto_2, fecha_vencimiento, fecha_vencimiento_2 FROM pagos_vencimientos WHERE concepto = ? AND periodo_mes = ? AND periodo_anio = ?', (concepto, periodo_mes, periodo_anio)).fetchone()
        
    if res:
        pago_id = res['id']
        estado_actual = res['estado']
        if estado_actual == 'PAGADO':
            return pago_id
            
        final_boleta = p_boleta if p_boleta else res['path_boleta']
        final_compro = p_comprobante if p_comprobante else res['path_comprobante']
        final_estado = 'PAGADO' if final_compro else 'PENDIENTE'
        
        # Si es un comprobante, no sobreescribir montos ni vencimientos
        if p_comprobante:
            final_monto = res['monto'] if res['monto'] else monto_cents
            final_monto_2 = res['monto_2'] if res['monto_2'] else monto_2_cents
            final_vto = res['fecha_vencimiento'] if res['fecha_vencimiento'] else data.get('fecha_vencimiento')
            final_vto_2 = res['fecha_vencimiento_2'] if res['fecha_vencimiento_2'] else data.get('fecha_vencimiento_2')
        else:
            final_monto = monto_cents
            final_monto_2 = monto_2_cents
            final_vto = data.get('fecha_vencimiento')
            final_vto_2 = data.get('fecha_vencimiento_2')
        
        conn.execute('''
            UPDATE pagos_vencimientos SET 
                categoria = COALESCE(?, categoria),
                entidad = COALESCE(?, entidad),
                monto = COALESCE(?, monto),
                fecha_vencimiento = COALESCE(?, fecha_vencimiento),
                monto_2 = COALESCE(?, monto_2),
                fecha_vencimiento_2 = COALESCE(?, fecha_vencimiento_2),
                path_boleta = ?,
                path_comprobante = ?,
                hash_boleta = COALESCE(?, hash_boleta),
                estado = ?,
                codigo_barras = COALESCE(?, codigo_barras),
                meta_json = ?,
                raw_ingesta_id = COALESCE(?, raw_ingesta_id),
                numero_linea = COALESCE(?, numero_linea)
            WHERE id = ?
        ''', (
            data.get('categoria'), data.get('entidad', 'LDK'), final_monto, final_vto,
            final_monto_2, final_vto_2,
            final_boleta, final_compro, data.get('hash_boleta'), final_estado,
            codigo_barras, json.dumps(data.get('meta_json', {})),
            data.get('raw_ingesta_id'), data.get('numero_linea'), pago_id
        ))
        return pago_id
    else:
        estado_inicial = 'PAGADO' if p_comprobante else 'PENDIENTE'
        cursor = conn.execute('''
            INSERT INTO pagos_vencimientos (
                categoria, entidad, concepto, periodo_mes, periodo_anio, monto, fecha_vencimiento,
                monto_2, fecha_vencimiento_2,
                estado, path_boleta, path_comprobante, hash_boleta, codigo_barras, meta_json,
                raw_ingesta_id, numero_linea
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('categoria', 'OTROS'), data.get('entidad', 'LDK'), concepto, periodo_mes, periodo_anio,
            monto_cents, data.get('fecha_vencimiento'),
            monto_2_cents, data.get('fecha_vencimiento_2'),
            estado_inicial, p_boleta, p_comprobante, data.get('hash_boleta'),
            codigo_barras, json.dumps(data.get('meta_json', {})),
            data.get('raw_ingesta_id'), data.get('numero_linea')
        ))
        return cursor.lastrowid

def procesar_inbox_pagos(inbox_path):
    """Interface de compatibilidad con erp_master.py. Ejecuta Ingesta + Transformación."""
    print("🚀 [PAGOS-ELT] Ejecutando Fase 1: Ingesta Raw a Staging...")
    ingestados = ingestar_inbox_a_raw(inbox_path)
    print(f"✅ [PAGOS-ELT] Ingesta finalizada. {ingestados} archivos procesados.")
    
    print("\n🚀 [PAGOS-ELT] Ejecutando Fase 2: Transformación Modular...")
    transformados = transformar_raw_a_produccion()
    print(f"✅ [PAGOS-ELT] Transformación finalizada. {transformados} registros actualizados.")
