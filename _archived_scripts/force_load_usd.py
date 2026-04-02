import pandas as pd
import sqlite3
import os
import sys

def force_inject_usd(file_path, db_path):
    print(f"🕵️ [FORZANDO INGESTA USD] ESCANEANDO...")
    try:
        # Cargamos el excel saltando 3 filas (como vimos antes)
        df = pd.read_excel(file_path, skiprows=3)
        
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        count = 0
        for i, row in df.iterrows():
            try:
                # El log anterior dice: pos0=Fecha, pos1=Desc, pos2=Monto, pos3=Saldo
                fecha = str(row.iloc[0]).strip()
                # Salteamos cabeceras vacías o con texto "FECHA"
                if "FECHA" in fecha.upper() or "NAN" in fecha.upper():
                    continue

                desc = str(row.iloc[1]).strip()
                monto_val = str(row.iloc[2]).replace('.', '').replace(',', '.')
                monto = float(monto_val)
                
                cur.execute('''
                    INSERT INTO bancos_movimientos (banco, cuenta, fecha, descripcion, codigo_movimiento, importe)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('HIPOTECARIO', 'CA_USD_JOAQUIN', fecha, desc, 'FORCE_LOAD', monto))
                count += 1
            except:
                continue
                
        conn.commit()
        conn.close()
        print(f"🧱 Éxito: {count} registros USD inyectados a la fuerza.")

    except Exception as e:
        print(f"❌ Error fatal en force_inject: {e}")

if __name__ == "__main__":
    WORKSPACE = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(WORKSPACE, "erp_nicoletti.db")
    force_inject_usd(sys.argv[1], DB_PATH)
