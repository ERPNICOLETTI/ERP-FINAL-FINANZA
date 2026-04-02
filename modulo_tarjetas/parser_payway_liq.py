import pandas as pd
import os
import sys

# Importación local de Storage (Ownership)
from . import storage_tarjetas as storage
from core_sistema import db_ingesta

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
            
            # PASAR AL DUEÑO DEL DOMINIO (STORAGE LOCAL)
            liq_id = storage.save_liquidacion(data)
            
            # DIGITALIZACIÓN BIT A BIT: Guardamos el detalle atómico de la fila
            if liq_id:
                detalle = [{
                    "fecha": data["fecha_liquidacion"],
                    "descripcion": f"Liq {row['Nro. Liquidación']} - {row['Marca']} {row['Establecimiento']}",
                    "monto_bruto": data["total_bruto"],
                    "monto_neto": data["total_neto"],
                    "metadata_raw": row.to_dict()
                }]
                storage.save_liquidacion_detalle(liq_id, detalle)
            
        print(f"🧱 Se procesaron {len(df)} días de liquidación Payway con bit-by-bit.")
        
        # 3. Notificar al Core para actualizar el índice de búsqueda global
        db_ingesta.update_search_index()

    except Exception as e:
        print(f"Error procesando Payway Liq: {e}")

if __name__ == "__main__":
    CSV = r"C:\Users\essao\Downloads\Liquidaciones diarias en pesos delimitadas por comas.csv"
    if os.path.exists(CSV):
        parse_payway_liq(CSV)
