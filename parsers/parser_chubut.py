import pandas as pd
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import ingesta

# Parser Banco Chubut Movimientos Históricos 🏦🏗️🧱🧠⚖️
def normalizar_importe_banco(val):
    if pd.isna(val) or val is None: return 0.0
    try:
        return float(val)
    except:
        return 0.0

def parse_chubut_excel(file_path):
    print(f"🏦 PROCESANDO BANCO CHUBUT: {os.path.basename(file_path)}")
    try:
        df = pd.read_excel(file_path, header=None)
        
        # Buscar el nombre de la cuenta en las primeras 10 filas
        cuenta_detectada = "DESCONOCIDA"
        for i in range(min(10, len(df))):
            val_col0 = str(df.iloc[i, 0]).strip().lower()
            val_col1 = str(df.iloc[i, 1]).strip()
            if "tipo y nº de cuenta" in val_col0 or "cuenta" in val_col0:
                cuenta_detectada = val_col1
                break
        print(f"   -> Cuenta Detectada: {cuenta_detectada}")

        movimientos = []
        for _, row in df.iterrows():
            fecha = str(row.iloc[1]).strip()
            # Formato esperado: DD/MM/AAAA
            if len(fecha) == 10 and fecha[2] == '/' and fecha[5] == '/':
                dia, mes, anio = fecha.split('/')
                fecha_iso = f"{anio}-{mes}-{dia}"
                desc = str(row.iloc[2]).strip()
                codigo = str(row.iloc[3]).strip()
                importe = normalizar_importe_banco(row.iloc[4])
                
                if pd.notna(codigo) and codigo != 'nan' and importe != 0.0:
                    movimientos.append({
                        "banco": "CHUBUT",
                        "cuenta": cuenta_detectada,
                        "fecha": fecha_iso,
                        "descripcion": desc,
                        "codigo_movimiento": f"CHUBUT_{codigo}",
                        "importe": importe,
                        "metadata": {
                            "archivo": os.path.basename(file_path)
                        }
                    })
        
        if movimientos:
            agregados = ingesta.persistir_movimientos_banco_lista(movimientos)
            print(f"🧱 Éxito: {agregados} nuevos movimientos bancarios guardados en la DB ({len(movimientos)} procesados).")
        else:
            print("⚠️ No se detectaron movimientos válidos en el archivo.")
            
    except Exception as e:
        print(f"Error procesando Banco Chubut: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        parse_chubut_excel(sys.argv[1])
    else:
        parse_chubut_excel(r'C:\Users\essao\Downloads\MovimientosHistoricos.xlsx')
