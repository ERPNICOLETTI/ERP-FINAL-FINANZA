import os
import hashlib
import sqlite3
import openpyxl

# SISTEMA INTEGRADO DE AUDITORÍA Y VERIFICACIÓN CRUZADA v1.0.0 🛡️🧮

class VerificadorIntegridadERP:
    def __init__(self, db_path: str = 'c:/Users/essao/Desktop/ERP FINAL/erp_nicoletti.db'):
        self.db_path = db_path

    def verificar_ingesta_banco_excel(self, filepath: str, staging_id: int) -> dict:
        """
        Realiza una reconciliación matemática 1:1 entre un Excel físico
        y lo transformado en la base de datos de producción.
        """
        if not os.path.exists(filepath):
            return {"status": "ERROR", "mensaje": f"Archivo físico no encontrado: {filepath}"}

        # 1. Leer Excel Físico
        try:
            wb = openpyxl.load_workbook(filepath, data_only=True)
            ws = wb['Cuentas']
            excel_filas = 0
            excel_debitos = 0.0
            excel_creditos = 0.0

            for r in range(7, ws.max_row + 1):
                f_val = ws.cell(r, 1).value
                m_val = ws.cell(r, 2).value
                deb_val = ws.cell(r, 3).value
                cred_val = ws.cell(r, 4).value
                
                if f_val and m_val:
                    excel_filas += 1
                    
                    def to_float(val):
                        if not val: return 0.0
                        try:
                            return float(str(val).replace('.', '').replace(',', '.'))
                        except:
                            return 0.0
                            
                    excel_debitos += abs(to_float(deb_val))
                    excel_creditos += abs(to_float(cred_val))
        except Exception as e:
            return {"status": "ERROR", "mensaje": f"Error al leer Excel original: {e}"}

        # 2. Leer Base de Datos
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            # Verificar Staging
            st = conn.execute("SELECT id, filas_leidas, hash_sha256 FROM core_staging_raw WHERE id = ?", (staging_id,)).fetchone()
            if not st:
                conn.close()
                return {"status": "ERROR", "mensaje": f"No se encontró el registro Staging ID {staging_id}"}
                
            # Verificar Producción
            bm = conn.execute("""
                SELECT count(*) as count, 
                       sum(case when importe < 0 then abs(importe) else 0 end) as debitos, 
                       sum(case when importe > 0 then importe else 0 end) as creditos 
                FROM bancos_movimientos 
                WHERE raw_ingesta_id = ?
            """, (staging_id,)).fetchone()
            
            conn.close()
        except Exception as e:
            return {"status": "ERROR", "mensaje": f"Error de base de datos: {e}"}

        # 3. Control de Conciliación
        db_filas = bm['count'] or 0
        db_debitos = bm['debitos'] or 0.0
        db_creditos = bm['creditos'] or 0.0

        dif_filas = excel_filas - db_filas
        dif_debitos = abs(excel_debitos - db_debitos)
        dif_creditos = abs(excel_creditos - db_creditos)

        conciliado = (dif_filas == 0 and dif_debitos < 0.01 and dif_creditos < 0.01)

        return {
            "status": "OK" if conciliado else "DISCREPANCIA",
            "hash_sha256": st['hash_sha256'],
            "origen": {
                "filas": excel_filas,
                "debitos": round(excel_debitos, 2),
                "creditos": round(excel_creditos, 2)
            },
            "destino": {
                "filas": db_filas,
                "debitos": round(db_debitos, 2),
                "creditos": round(db_creditos, 2)
            },
            "diferencias": {
                "filas": dif_filas,
                "debitos": round(dif_debitos, 2),
                "creditos": round(dif_creditos, 2)
            }
        }
