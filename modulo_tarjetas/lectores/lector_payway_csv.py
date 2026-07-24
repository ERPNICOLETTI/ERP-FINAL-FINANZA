import os
import shutil
import hashlib
import sqlite3
import csv
from datetime import datetime

def procesar_archivo(filepath: str) -> tuple[bool, dict]:
    """
    Procesador ELT para CSV de Transacciones Presentadas de Payway.
    Sube cupones granulares a tarjetas_payway de forma idempotente.
    """
    try:
        # 1. Calcular Hash SHA256 Legal
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            sha256.update(f.read())
        hash_hex = sha256.hexdigest()
        
        # 2. Leer y Parsear CSV (Fase 1)
        cupones_parsed = []
        with open(filepath, 'r', encoding='latin1') as f:
            reader = csv.reader(f)
            
            # Fila 1 es metadata de encabezado
            header_desc = next(reader)[0]
            # Fila 2 son las columnas
            headers = next(reader)
            
            idx_compra = headers.index('COMPRA')
            idx_presentacion = headers.index('PRESENTACION')
            idx_tipo = headers.index('TIPO')
            idx_lote = headers.index('LOTE')
            idx_cupon = headers.index('NUM.CUPON')
            idx_marca = headers.index('MARCA')
            idx_est = headers.index('ESTABLECIMIENTO')
            idx_pago = headers.index('PAGO')
            idx_bruto = headers.index('MONTO_BRUTO')
            idx_tarjeta = headers.index('NUM.TARJETA')
            idx_cuotas = headers.index('CANT.CUOTAS')
            
            raw_md_lines = []
            raw_md_lines.append(f"# DETALLE CUATRIESTRUCTURA PAYWAY: {header_desc}")
            raw_md_lines.append(f"**SHA256:** {hash_hex}\n")
            raw_md_lines.append("| Fecha Compra | Fecha Pago | Lote | Cupon | Marca | Bruto | Tarjeta |")
            raw_md_lines.append("| --- | --- | --- | --- | --- | --- | --- |")
            
            for row in reader:
                if not row or len(row) < 10:
                    continue
                    
                # Convertir fechas de DD/MM/YYYY a YYYY-MM-DD
                def to_iso_date(d_str):
                    try:
                        return datetime.strptime(d_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
                    except:
                        return d_str
                        
                f_compra = to_iso_date(row[idx_compra])
                f_pago = to_iso_date(row[idx_pago])
                lote = row[idx_lote].strip()
                cupon = row[idx_cupon].strip()
                marca = row[idx_marca].strip()
                bruto = float(row[idx_bruto])
                tarjeta = row[idx_tarjeta].strip()
                cuotas = int(row[idx_cuotas]) if row[idx_cuotas] else 0
                
                raw_md_lines.append(f"| {f_compra} | {f_pago} | {lote} | {cupon} | {marca} | {bruto} | {tarjeta} |")
                
                cupones_parsed.append({
                    'fecha_compra': f_compra,
                    'fecha_pago': f_pago,
                    'lote': lote,
                    'cupon': cupon,
                    'marca': marca,
                    'monto_bruto': bruto,
                    'tarjeta': tarjeta,
                    'cuotas': cuotas,
                    'establecimiento': row[idx_est].strip()
                })
                
        raw_md_text = "\n".join(raw_md_lines)
        
        # 3. Guardar en core_staging_raw
        conn = sqlite3.connect('c:/Users/essao/Desktop/ERP FINAL/erp_nicoletti.db')
        conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM core_staging_raw WHERE hash_sha256 = ?", (hash_hex,))
        cursor.execute("""
            INSERT INTO core_staging_raw (
                nombre_archivo, hash_sha256, modulo, tipo_fuente, formato_raw, parser_version, contenido_raw, filas_leidas, estado, fecha_ingesta, fecha_procesado
            ) VALUES (
                ?, ?, 'tarjetas', 'CSV', 'MARKDOWN', 'v6.2.0', ?, ?, 'PROCESADO', datetime('now', 'localtime'), datetime('now', 'localtime')
            )
        """, (os.path.basename(filepath), hash_hex, raw_md_text, len(cupones_parsed)))
        
        staging_id = cursor.lastrowid
        conn.commit()
        
        # 4. Fase 2: Cargar en tarjetas_payway de forma idempotente (INSERT OR IGNORE para respetar UNIQUE)
        # Limpiar registros previos cargados de este mismo archivo para posibilitar re-procesamientos limpios
        conn.execute("DELETE FROM tarjetas_payway WHERE hash_archivo = ?", (hash_hex,))
        
        for c in cupones_parsed:
            metadata_json = json.dumps({
                'tarjeta_enmascarada': c['tarjeta'],
                'cantidad_cuotas': c['cuotas'],
                'establecimiento': c['establecimiento'],
                'raw_ingesta_id': staging_id
            })
            conn.execute("""
                INSERT OR IGNORE INTO tarjetas_payway (
                    fuente, fecha_compra, fecha_pago, lote, cupon, marca, monto_bruto, path_archivo, hash_archivo, metadata_cruda
                ) VALUES ('PAYWAY_CSV', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (c['fecha_compra'], c['fecha_pago'], c['lote'], c['cupon'], c['marca'], c['monto_bruto'], filepath, hash_hex, metadata_json))
            
        conn.commit()
        conn.close()
        
        info = {
            "modulo": "tarjetas",
            "anio": datetime.now().strftime("%Y"),
            "mes": datetime.now().strftime("%m"),
            "entidad": "PAYWAY_CSV",
            "db_table": "tarjetas_payway",
            "id_insertado": staging_id
        }
        return True, info
        
    except Exception as e:
        print(f"❌ Error en lector_payway_csv: {e}")
        return False, {}
import json
