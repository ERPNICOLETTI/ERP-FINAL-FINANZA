import pandas as pd
import sqlite3
import os
import sys
import json

# Configuración de salida UTF-8 para Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def parse_payway(file_path, db_path):
    print(f"🚀 Iniciando ingesta de Payway: {os.path.basename(file_path)}")
    
    try:
        # Detectar cabecera real (si la línea 1 no empieza con COMPRA, saltamos)
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline()
        
        skip = 1 if "COMPRA" not in first_line else 0
        df = pd.read_csv(file_path, encoding='utf-8', skiprows=skip)
        
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        count_added = 0
        count_ignored = 0
        
        for _, row in df.iterrows():
            # NORMALIZACIÓN DE FECHAS (DD/MM/YYYY -> YYYY-MM-DD)
            try:
                f_compra = pd.to_datetime(row['COMPRA'], dayfirst=True).strftime('%Y-%m-%d')
                f_presen = pd.to_datetime(row['PRESENTACION'], dayfirst=True).strftime('%Y-%m-%d')
                f_pago = pd.to_datetime(row['PAGO'], dayfirst=True).strftime('%Y-%m-%d')
            except:
                f_compra = f_presen = f_pago = "ERROR_FECHA"

            # NORMALIZACIÓN DE MONTOS
            monto = float(row['MONTO_BRUTO'])
            
            # NORMALIZACIÓN DE LOTE Y CUPON (Padding 8 para cupón)
            lote = str(row['LOTE']).strip()
            cupon = str(row['NUM.CUPON']).strip().zfill(8)
            marca = str(row['MARCA']).strip().upper()
            
            # METADATA (Capa de robustez para datos extra)
            meta = {
                "establecimiento": str(row['ESTABLECIMIENTO']),
                "tarjeta": str(row['NUM.TARJETA']),
                "cuotas": int(row['CANT.CUOTAS']),
                "modalidad": str(row['MODALIDAD']),
                "aut": str(row['NRO_AUT']),
                "detalle": str(row['DETALLE']).strip()
            }
            
            # INSERT CON UNIQUE INDEX (Evita duplicados por lote/cupon/fecha/monto)
            try:
                cur.execute('''
                    INSERT INTO payway_records (
                        fecha_compra, fecha_presentacion, fecha_pago,
                        lote, cupon, marca, monto_bruto, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (f_compra, f_presen, f_pago, lote, cupon, marca, monto, json.dumps(meta)))
                count_added += 1
            except sqlite3.IntegrityError:
                count_ignored += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ Ingesta finalizada.")
        print(f"   -> Agregados: {count_added}")
        print(f"   -> Ignorados (Duplicados): {count_ignored}")
        
    except Exception as e:
        print(f"❌ Error fatal en Payway Parser: {e}")

if __name__ == "__main__":
    import glob
    DOWNLOADS = r"C:\Users\essao\Downloads"
    WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(WORKSPACE, "erp_nicoletti.db")
    
    pattern = os.path.join(DOWNLOADS, "Movimientos Presentados en pesos Delimitado por comas*.csv")
    files = glob.glob(pattern)
    
    if not files:
        print(f"❌ No se encontraron archivos de ventas en {DOWNLOADS}")
    else:
        for f in files:
            parse_payway(f, DB_PATH)
