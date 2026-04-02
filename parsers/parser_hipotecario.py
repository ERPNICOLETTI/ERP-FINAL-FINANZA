import pandas as pd
import sqlite3
import os
import sys

def ingesta_hipotecario(file_path, db_path):
    print(f"💎 PROCESANDO BANCO HIPOTECARIO (ÁREA JOAQUÍN)...")
    
    try:
        # El archivo tiene basura en las primeras filas, saltamos hasta donde aparecen los datos reales
        df = pd.read_excel(file_path, skiprows=4)
        
        # Renombramos columnas basándonos en la inspección
        df.columns = ['fecha', 'descripcion', 'importe', 'saldo']
        
        # Limpiar filas vacías o que no son datos
        df = df.dropna(subset=['fecha', 'descripcion', 'importe'])
        
        # Conectar a la DB
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        count = 0
        for _, row in df.iterrows():
            try:
                fecha = str(row['fecha']).strip()
                desc = str(row['descripcion']).strip()
                
                # Manejar conversión de importe con comas y puntos (Formato AR)
                val_str = str(row['importe']).replace('.', '').replace(',', '.')
                importe = float(val_str)
                
                # Conectar a la DB e insertar
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute('''
                    INSERT OR IGNORE INTO bancos_movimientos (banco, cuenta, fecha, descripcion, codigo_movimiento, importe)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('HIPOTECARIO', 'CA_JOAQUIN', fecha, desc, '', importe))
                if cur.rowcount > 0:
                    count += 1
                conn.commit()
                conn.close()
            except Exception as e:
                # Si una fila falla (ej: encabezados), se ignora
                continue
        
        print(f"🧱 Éxito: {count} movimientos nuevos del Hipotecario (JOA) ingresados.")
        
    except Exception as e:
        print(f"❌ Error fatal: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python parser_hipotecario.py <ruta_excel>")
    else:
        WORKSPACE = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(WORKSPACE, "..", "erp_nicoletti.db")
        ingesta_hipotecario(sys.argv[1], DB_PATH)
