import pandas as pd
import os
import sys

# Importaciones Modulares (Ownership)
from . import storage_bancos as storage
from core_sistema import db_ingesta, checksum_service
from modulo_compras import storage_compras

def normalizar_importe_usd(val):
    if pd.isna(val) or val is None: return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace('.', '').replace(',', '.')
    try: return float(s)
    except: return 0.0

def parse_hipotecario_usd(file_path):
    """
    EXTRACTOR ROBUSTO PARA BANCO HIPOTECARIO USD (Área Joaquín).
    """
    print(f"💵 Analizando extracto Hipotecario USD: {os.path.basename(file_path)}")
    
    # 1. CONTROL DE DUPLICADOS
    es_nuevo, hash_val = checksum_service.validar_y_registrar("BANCOS", "FILE", os.path.basename(file_path), file_path)
    if not es_nuevo:
        print(f"🚫 SALTADO: Ya procesado.")
        return

    try:
        df = pd.read_excel(file_path, header=None)
        
        # 2. DETECCIÓN DINÁMICA DE CABECERA
        header_idx = -1
        for i, row in df.iterrows():
            row_str = " ".join(str(v).lower() for v in row.values)
            if "fecha" in row_str and "importe" in row_str:
                header_idx = i
                break
        
        if header_idx == -1:
            raise ValueError("No se pudo detectar la cabecera en el Excel del Hipotecario.")

        # Mapeo de nombres de columnas a mayúsculas para evitar líos
        column_names = [str(c).strip().upper() for c in df.iloc[header_idx]]
        df_movs = df.iloc[header_idx + 1:].copy()
        df_movs.columns = column_names
        
        movimientos = []
        for _, row in df_movs.iterrows():
            raw_fecha = row.get('FECHA')
            if pd.isna(raw_fecha): continue
            
            try:
                # Normalización de fecha robusta
                fecha_dt = pd.to_datetime(raw_fecha, dayfirst=True)
                fecha_iso = fecha_dt.strftime('%Y-%m-%d')
            except:
                continue

            desc = str(row.get('DESCRIPCIÓN', row.get('CONCEPTO', 'MOVIMIENTO USD'))).strip()
            importe = normalizar_importe_usd(row.get('IMPORTE', 0))
            
            if importe != 0:
                movimientos.append({
                    "banco": "HIPOTECARIO",
                    "cuenta": "CA_USD_2646",
                    "fecha": fecha_iso,
                    "descripcion": desc,
                    "codigo_movimiento": f"HIP_USD_{fecha_iso}_{abs(importe)}",
                    "importe": importe,
                    "metadata": {"archivo": os.path.basename(file_path)}
                })
                
                # Reporte de IVA Bancario (Si aplica a USD, lo detectamos)
                if "iva" in desc.lower() and "21" in desc.lower():
                    storage_compras.registrar_impuesto({
                        "modulo": "BANCOS",
                        "fuente": "HIPOTECARIO_USD",
                        "fecha": fecha_iso,
                        "neto_gravado": 0,
                        "iva_105": 0,
                        "iva_21": abs(importe),
                        "descripcion": f"IVA Bancario USD: {desc}",
                        "extern_id": None
                    })

        if movimientos:
            agregados = storage.save_movimiento_banco(movimientos)
            print(f"✨ Éxito: {agregados} movimientos en USD ingresados correctamente.")
        else:
            print("⚠️ No se encontraron movimientos válidos.")
            
        db_ingesta.update_search_index()

    except Exception as e:
        print(f"❌ Error en Hipotecario USD: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python parser_hipotecario_usd.py <ruta_excel>")
    else:
        WORKSPACE = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(WORKSPACE, "erp_nicoletti.db")
        ingesta_hipotecario_usd(sys.argv[1], DB_PATH)
