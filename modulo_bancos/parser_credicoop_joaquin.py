import pandas as pd
import sqlite3
import os
import sys

def parse_credicoop_joaquin_final(file_path, db_path):
    print(f"🏦 [AUDITORÍA VISUAL] EXTRAIENDO CREDICOOP SEGÚN IMAGEN...")
    
    try:
        # Cargamos el Excel
        df = pd.read_excel(file_path)
        
        # Sincronizamos nombres de columnas con la imagen:
        # 'Fecha', 'Concepto', 'NÂ° de comprobante', 'Monto', 'Saldo', 'Cod.'
        
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        count = 0
        for i, row in df.iterrows():
            try:
                fecha = str(row['Fecha']).strip()
                if "nan" in fecha.lower(): continue
                
                concepto = str(row['Concepto']).strip()
                # El monto en la imagen es float, pero por las dudas limpiamos
                monto = float(row['Monto'])
                comprobante = str(row['NÂ° de comprobante']).strip()
                
                # Inyectar en tabla unificada con etiqueta JOA_CREDICOOP
                cur.execute('''
                    INSERT OR IGNORE INTO bancos_movimientos (banco, cuenta, fecha, descripcion, codigo_movimiento, importe)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('CREDICOOP', 'CA_JOAQUIN_9087', fecha, concepto, comprobante, monto))
                
                if cur.rowcount > 0:
                    count += 1
            except Exception as e:
                continue
                
        conn.commit()
        conn.close()
        print(f"🧱 Éxito: {count} registros de CREDICOOP validados e inyectados.")

    except Exception as e:
        print(f"❌ Error en auditoría visual: {e}")

if __name__ == "__main__":
    WORKSPACE = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(WORKSPACE, "erp_nicoletti.db")
    parse_credicoop_joaquin_final(sys.argv[1], DB_PATH)
