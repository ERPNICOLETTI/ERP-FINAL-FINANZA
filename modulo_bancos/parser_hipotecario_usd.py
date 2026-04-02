import pandas as pd
import sqlite3
import os
import sys

def ingesta_hipotecario_usd(file_path, db_path):
    print(f"💵 PROCESANDO CA DOLARES (ÁREA JOAQUÍN) - BANCO HIPOTECARIO...")
    
    try:
        # El archivo tiene la estructura idéntica a la de pesos
        df = pd.read_excel(file_path, skiprows=4)
        df.columns = ['fecha', 'descripcion', 'importe', 'saldo']
        
        # Conectar a la DB
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        count = 0
        for _, row in df.iterrows():
            try:
                fecha = str(row['fecha']).strip()
                desc = str(row['descripcion']).strip()
                
                # Manejar conversión de importes USD con comas (Formato AR)
                val_str = str(row['importe']).replace('.', '').replace(',', '.')
                importe = float(val_str)
                
                # Usar la tabla unificada bancos_movimientos
                cur.execute('''
                    INSERT OR IGNORE INTO bancos_movimientos (banco, cuenta, fecha, descripcion, codigo_movimiento, importe)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('HIPOTECARIO', 'CA_USD_2646', fecha, desc, '', importe))
                
                if cur.rowcount > 0:
                    count += 1
            except:
                continue
        
        conn.commit()
        conn.close()
        print(f"✨ Éxito: {count} movimientos en USD (JOA) ingresados en tabla unificada.")
        
    except Exception as e:
        print(f"❌ Error fatal: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python parser_hipotecario_usd.py <ruta_excel>")
    else:
        WORKSPACE = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(WORKSPACE, "erp_nicoletti.db")
        ingesta_hipotecario_usd(sys.argv[1], DB_PATH)
