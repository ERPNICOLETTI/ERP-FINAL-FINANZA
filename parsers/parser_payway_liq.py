import pandas as pd
import os
import sys

# Añadir path raíz para importar core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import ingesta

def normalizar_importe(texto):
    if not texto: return 0.0
    texto = str(texto).replace(".", "").replace(",", ".")
    try: return float(texto)
    except: return 0.0

def parse_payway_liq(csv_path):
    """
    EXTRACTOR DE DATOS DE PAYWAY (CSV).
    Se encarga de leer el archivo crudo y entregarlo al motor de ingesta.
    """
    print(f"📄 Procesando CSV Payway Liquidaciones: {os.path.basename(csv_path)}")
    
    try:
        # 1. Leer CSV omitiendo cabecera de reporte
        df = pd.read_csv(csv_path, sep=',', encoding='latin1', skiprows=1)
        
        for _, row in df.iterrows():
            # Mapeo de columnas a objeto normalizado
            data = {
                "fuente": "PAYWAY",
                "tipo": "DIARIA",
                "fecha_liquidacion": pd.to_datetime(row['Pago'], dayfirst=True).strftime('%Y-%m-%d'),
                "marca": str(row['Marca']),
                "establecimiento": str(row['Establecimiento']),
                "total_bruto": normalizar_importe(row['Importe Bruto']),
                "costo_arancel": normalizar_importe(row['Arancel/Serv. Financ.']),
                "retenciones": normalizar_importe(row['Impuestos (Suj. a Retenc / Perc)']),
                "total_neto": normalizar_importe(row['Importe Neto']),
                "metadata": {"nro_liquidacion": str(row['Nro. Liquidación'])}
            }
            
            # PASAR AL LADRILLERO (INGESTA)
            ingesta.persistir_liquidacion(data)
            
        print(f"🧱 Se procesaron {len(df)} días de liquidación Payway.")

    except Exception as e:
        print(f"Error procesando Payway Liq: {e}")

if __name__ == "__main__":
    CSV = r"C:\Users\essao\Downloads\Liquidaciones diarias en pesos delimitadas por comas.csv"
    if os.path.exists(CSV):
        parse_payway_liq(CSV)
