import os
import shutil
import hashlib
import sqlite3
import csv
from datetime import datetime

def procesar_archivo(filepath: str) -> tuple[bool, dict]:
    """
    Procesador ELT para Reportes de Mercado Pago (CSV) de doble capa e idempotencia.
    """
    try:
        # 1. Calcular Hash SHA256 Legal
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            sha256.update(f.read())
        hash_hex = sha256.hexdigest()
        
        # 2. Leer y Parsear CSV (Fase 1)
        movimientos_parsed = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            
            idx_fecha = headers.index('SETTLEMENT_DATE')
            idx_tipo = headers.index('TRANSACTION_TYPE')
            idx_bruto = headers.index('TRANSACTION_AMOUNT')
            idx_comision = headers.index('FEE_AMOUNT')
            idx_neto = headers.index('SETTLEMENT_NET_AMOUNT')
            idx_detalle = headers.index('SALE_DETAIL')
            idx_pagador = headers.index('PAYER_NAME')
            idx_id = headers.index('SOURCE_ID')
            idx_cuotas = headers.index('INSTALLMENTS')
            idx_retenciones = headers.index('TAXES_AMOUNT')
            idx_canal = headers.index('PAYMENT_METHOD_TYPE')
            
            raw_md_lines = []
            raw_md_lines.append("# REPORTE CONCILIACION MERCADO PAGO")
            raw_md_lines.append(f"**SHA256:** {hash_hex}\n")
            raw_md_lines.append("| Fecha Aprobacion | Tipo | Importe Bruto | Comision | Importe Neto | Detalle | Pagador | ID Operacion |")
            raw_md_lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
            
            for row in reader:
                if not row:
                    continue
                    
                fecha_val = row[idx_fecha].split('T')[0]
                tipo_val = row[idx_tipo]
                bruto_val = row[idx_bruto]
                comision_val = row[idx_comision]
                neto_val = row[idx_neto]
                detalle_val = row[idx_detalle]
                pagador_val = row[idx_pagador]
                id_val = row[idx_id]
                cuotas_val = row[idx_cuotas]
                ret_val = row[idx_retenciones]
                canal_val = row[idx_canal]
                
                raw_md_lines.append(f"| {fecha_val} | {tipo_val} | {bruto_val} | {comision_val} | {neto_val} | {detalle_val} | {pagador_val} | {id_val} |")
                
                def to_float(val):
                    try:
                        return float(str(val))
                    except:
                        return 0.0
                        
                movimientos_parsed.append({
                    'fecha': fecha_val,
                    'tipo': tipo_val,
                    'bruto': to_float(bruto_val),
                    'comision': to_float(comision_val),
                    'neto': to_float(neto_val),
                    'detalle': detalle_val,
                    'pagador': pagador_val,
                    'source_id': id_val,
                    'cuotas': int(to_float(cuotas_val)) if cuotas_val else 1,
                    'retenciones': to_float(ret_val),
                    'canal': canal_val
                })
                
        raw_md_text = "\n".join(raw_md_lines)
        
        # 3. Guardar en core_staging_raw (Fase 1)
        conn = sqlite3.connect('c:/Users/essao/Desktop/ERP FINAL/erp_nicoletti.db')
        conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM core_staging_raw WHERE hash_sha256 = ?", (hash_hex,))
        cursor.execute("""
            INSERT INTO core_staging_raw (
                nombre_archivo, hash_sha256, modulo, tipo_fuente, formato_raw, parser_version, contenido_raw, filas_leidas, estado, fecha_ingesta, fecha_procesado
            ) VALUES (
                ?, ?, 'bancos', 'CSV', 'MARKDOWN', 'v6.2.0', ?, ?, 'PROCESADO', datetime('now', 'localtime'), datetime('now', 'localtime')
            )
        """, (os.path.basename(filepath), hash_hex, raw_md_text, len(movimientos_parsed)))
        
        staging_id = cursor.lastrowid
        conn.commit()
        
        # 4. Fase 2: Crear e Insertar en movimientos_mp (Detalles)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS movimientos_mp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                tipo TEXT,
                bruto REAL,
                comision REAL,
                neto REAL,
                detalle TEXT,
                pagador TEXT,
                source_id TEXT UNIQUE,
                cuotas INTEGER,
                retenciones REAL,
                canal TEXT,
                raw_ingesta_id INTEGER
            )
        """)
        
        conn.execute("DELETE FROM movimientos_mp WHERE raw_ingesta_id IN (SELECT id FROM core_staging_raw WHERE hash_sha256 = ?)", (hash_hex,))
        
        # 5. Inyectar de manera acoplada en bancos_movimientos
        conn.execute("DELETE FROM bancos_movimientos WHERE raw_ingesta_id IN (SELECT id FROM core_staging_raw WHERE hash_sha256 = ?)", (hash_hex,))
        
        for m in movimientos_parsed:
            # Validar si ya existe este source_id para no volver a inyectarlo de forma duplicada
            existe_mp = conn.execute("SELECT id FROM movimientos_mp WHERE source_id = ?", (m['source_id'],)).fetchone()
            
            # Guardar el detalle
            conn.execute("""
                INSERT OR REPLACE INTO movimientos_mp (
                    fecha, tipo, bruto, comision, neto, detalle, pagador, source_id, cuotas, retenciones, canal, raw_ingesta_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (m['fecha'], m['tipo'], m['bruto'], m['comision'], m['neto'], m['detalle'], m['pagador'], m['source_id'], m['cuotas'], m['retenciones'], m['canal'], staging_id))
            
            if not existe_mp:
                desc = f"MP: {m['tipo']} - {m['detalle']}"
                if m['pagador']:
                    desc += f" (Pagador: {m['pagador']})"
                if m['source_id']:
                    desc += f" [ID: {m['source_id']}]"
                    
                cat = 'SIN_CATEGORIZAR'
                d_upper = desc.upper()
                if 'RENTAS' in d_upper or 'IMP' in d_upper or 'INACAP' in d_upper or 'FAECYS' in d_upper:
                    cat = 'Impuestos'
                    
                conn.execute("""
                    INSERT INTO bancos_movimientos (
                        fecha, cuenta, banco, descripcion, importe, saldo, categoria, raw_ingesta_id, entidad
                    ) VALUES (?, 'MERCADOPAGO', 'MERCADOPAGO', ?, ?, 0.0, ?, ?, 'LDK')
                """, (m['fecha'], desc, m['neto'], cat, staging_id))
                
        conn.commit()
        conn.close()
        
        info = {
            "modulo": "bancos",
            "anio": datetime.now().strftime("%Y"),
            "mes": datetime.now().strftime("%m"),
            "entidad": "LDK",
            "db_table": "bancos_movimientos",
            "id_insertado": staging_id
        }
        return True, info
    except Exception as e:
        print(f"❌ Error en lector_mercadopago: {e}")
        return False, {}
