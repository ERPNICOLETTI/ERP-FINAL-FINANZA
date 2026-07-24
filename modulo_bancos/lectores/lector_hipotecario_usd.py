import os
import shutil
import hashlib
import sqlite3
import openpyxl
from datetime import datetime

def procesar_archivo(filepath: str) -> tuple[bool, dict]:
    """
    Procesador ELT para Extracto de Banco Hipotecario Dólares.
    Entidad: JOA (Cuentas Joaquín).
    """
    try:
        # 1. Calcular Hash SHA256 Legal
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            sha256.update(f.read())
        hash_hex = sha256.hexdigest()
        
        # 2. Generar representación Markdown Raw Completa (Fase 1)
        wb = openpyxl.load_workbook(filepath, data_only=True)
        ws = wb.active # Toma la pestaña activa
        
        cuenta_alias = "CA U$D ...2646"
        
        raw_md_lines = []
        raw_md_lines.append("# EXTRACTO BANCARIO BANCO HIPOTECARIO - CAJA DE AHORRO DOLARES")
        raw_md_lines.append(f"**Cuenta:** {cuenta_alias}")
        raw_md_lines.append(f"**SHA256:** {hash_hex}\n")
        raw_md_lines.append("| Fecha | Movimiento / Descripción | Importe | Saldo Parcial |")
        raw_md_lines.append("| --- | --- | --- | --- |")
        
        movimientos_parsed = []
        
        # El archivo tiene filas de encabezado basura, los datos reales de movimientos empiezan más abajo (skiprows=4 en pandas)
        for r in range(6, ws.max_row + 1):
            fecha_val = ws.cell(r, 1).value
            desc_val = ws.cell(r, 2).value
            imp_val = ws.cell(r, 3).value
            saldo_val = ws.cell(r, 4).value
            
            if not fecha_val or not desc_val:
                continue
                
            clean_mov = " ".join(str(desc_val).split('\n')).strip()
            raw_md_lines.append(f"| {fecha_val} | {clean_mov} | {imp_val} | {saldo_val} |")
            
            def to_float(val):
                if not val: return 0.0
                try:
                    return float(str(val).replace('.', '').replace(',', '.'))
                except:
                    return 0.0
                    
            imp_f = to_float(imp_val)
            saldo_f = to_float(saldo_val)
            
            movimientos_parsed.append({
                'fecha': str(fecha_val),
                'descripcion': clean_mov,
                'importe': imp_f,
                'saldo': saldo_f,
                'cuenta': cuenta_alias,
                'banco': 'HIPOTECARIO'
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
                ?, ?, 'bancos', 'EXCEL', 'MARKDOWN', 'v6.2.0', ?, ?, 'PROCESADO', datetime('now', 'localtime'), datetime('now', 'localtime')
            )
        """, (os.path.basename(filepath), hash_hex, raw_md_text, len(movimientos_parsed)))
        
        staging_id = cursor.lastrowid
        conn.commit()
        
        # 4. Insertar en bancos_movimientos
        conn.execute("DELETE FROM bancos_movimientos WHERE cuenta = ? AND raw_ingesta_id IN (SELECT id FROM core_staging_raw WHERE hash_sha256 = ?)", (cuenta_alias, hash_hex))
        
        for m in movimientos_parsed:
            cat = 'SIN_CATEGORIZAR'
            desc = m['descripcion'].upper()
            if 'AFIP' in desc or 'VEP' in desc or 'LEY 25413' in desc:
                cat = 'Impuestos'
            elif 'SUELDO' in desc or 'HABERES' in desc:
                cat = 'Sueldo'
            elif 'INTERES' in desc:
                cat = 'Intereses'
            elif 'MERCADO LIBRE' in desc or 'MERCADOPAGO' in desc:
                cat = 'Compras'
                
            conn.execute("""
                INSERT OR REPLACE INTO bancos_movimientos (fecha, cuenta, banco, descripcion, importe, saldo, categoria, raw_ingesta_id, entidad)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'JOA')
            """, (m['fecha'], m['cuenta'], m['banco'], m['descripcion'], m['importe'], m['saldo'], cat, staging_id))
            
        conn.commit()
        conn.close()
        
        # 5. Correr el Verificador de Integridad Automático en Caliente
        try:
            from core_sistema.verificador_integridad import VerificadorIntegridadERP
            vi = VerificadorIntegridadERP()
            res_v = vi.verificar_y_reportar(filepath, staging_id)
            if res_v['status'] != 'OK':
                print(f"⚠️ [DISCREPANCIA DETECTADA EN INGESTA HIPOTECARIO USD] Staging ID: {staging_id} | Desvío: {res_v.get('diferencias')}")
        except Exception as ver_err:
            print(f"⚠️ Error al ejecutar verificador automático en caliente: {ver_err}")
            
        info = {
            "modulo": "bancos",
            "anio": datetime.now().strftime("%Y"),
            "mes": datetime.now().strftime("%m"),
            "entidad": "JOA",
            "db_table": "bancos_movimientos",
            "id_insertado": staging_id
        }
        return True, info
    except Exception as e:
        print(f"❌ Error en lector_hipotecario_usd: {e}")
        return False, {}
