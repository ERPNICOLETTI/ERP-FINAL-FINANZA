import pandas as pd
import os
import sys

# Importaciones Modulares (Ownership)
from . import storage_bancos as storage
from core_sistema import db_ingesta, checksum_service
from modulo_compras import storage_compras

# Parser Banco Chubut Movimientos Históricos 🏦🏗️🧱🧠⚖️
def normalizar_importe_banco(val):
    if pd.isna(val) or val is None: return 0.0
    try:
        return float(val)
    except:
        return 0.0

def parse_chubut_excel(file_path):
    """
    EXTRACTOR INTELIGENTE PARA BANCO CHUBUT (Excel Histórico).
    Diseñado para ser resiliente a cambios en las filas superiores y detectar IVA.
    """
    print(f"🏦 Analizando extracto Banco Chubut: {os.path.basename(file_path)}")
    
    # 1. CONTROL DE DUPLICADOS (HUELLA DIGITAL)
    es_nuevo, hash_val = checksum_service.validar_y_registrar("BANCOS", "FILE", os.path.basename(file_path), file_path)
    if not es_nuevo:
        print(f"🚫 SALTADO: Este extracto ya fue procesado anteriormente.")
        return

    try:
        df = pd.read_excel(file_path, header=None)
        
        # 2. DETECCIÓN DINÁMICA DE CABECERA Y CUENTA
        header_idx = -1
        cuenta_detectada = "SIN_ASIGNAR"
        
        # Escaneamos las primeras 30 filas
        for i, row in df.iterrows():
            row_str = " ".join(str(v).lower() for v in row.values)
            
            # Detectar cuenta
            if "tipo y nº de cuenta" in row_str or "cuenta" in row_str:
                for val in row.values:
                    if any(char.isdigit() for char in str(val)):
                        cuenta_detectada = str(val).strip()
                        break
            
            # Detectar cabecera de movimientos
            if "fecha" in row_str and ("movimiento" in row_str or "concepto" in row_str):
                header_idx = i
                break
        
        if header_idx == -1:
            raise ValueError("No se pudo detectar la tabla de movimientos en el Excel del Chubut.")

        # Re-leer con la cabecera correcta
        column_names = [str(c).strip().upper() for c in df.iloc[header_idx]]
        df_movs = df.iloc[header_idx + 1:].copy()
        df_movs.columns = column_names
        
        print(f"   -> Cuenta: {cuenta_detectada} | Cabecera en fila {header_idx}")

        movimientos = []
        for _, row in df_movs.iterrows():
            # Limpieza y normalización de fecha
            raw_fecha = row.get('FECHA')
            if pd.isna(raw_fecha): continue
            
            try:
                # Intentamos parsear la fecha de forma robusta
                fecha_dt = pd.to_datetime(raw_fecha, dayfirst=True)
                fecha_iso = fecha_dt.strftime('%Y-%m-%d')
            except:
                continue # No es una fila de datos válida

            desc = str(row.get('DESCRIPCIÓN DE MOVIMIENTO', row.get('CONCEPTO', ''))).strip()
            codigo = str(row.get('CÓDIGO', '')).strip()
            importe = normalizar_importe_banco(row.get('IMPORTE', 0))
            
            if desc and (importe != 0):
                mov_data = {
                    "banco": "CHUBUT",
                    "cuenta": cuenta_detectada,
                    "fecha": fecha_iso,
                    "descripcion": desc,
                    "codigo_movimiento": f"CHB_{codigo}_{fecha_iso}",
                    "importe": importe,
                    "metadata": {"archivo": os.path.basename(file_path)}
                }
                movimientos.append(mov_data)

                # 3. DETECCIÓN DE IVA FISCAL (IVA 21% por intereses/mora)
                # Buscamos patrones de IVA en la descripción o filas contiguas
                desc_lower = desc.lower()
                if "iva" in desc_lower and "21" in desc_lower:
                    storage_compras.registrar_impuesto({
                        "modulo": "BANCOS",
                        "fuente": "CHUBUT",
                        "fecha": fecha_iso,
                        "neto_gravado": 0, # El banco a veces no lo detalla
                        "iva_105": 0,
                        "iva_21": abs(importe),
                        "descripcion": f"IVA Bancario: {desc}",
                        "extern_id": None # No tenemos ID de movimiento aún
                    })

        if movimientos:
            agregados = storage.save_movimiento_banco(movimientos)
            print(f"🧱 Éxito: {agregados} nuevos movimientos bancarios sincronizados.")
        else:
            print("⚠️ No se encontraron movimientos válidos en el archivo.")
            
        # 4. Notificar actualización de búsqueda
        db_ingesta.update_search_index()

    except Exception as e:
        print(f"❌ Error crítico en Banco Chubut: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        parse_chubut_excel(sys.argv[1])
    else:
        parse_chubut_excel(r'C:\Users\essao\Downloads\MovimientosHistoricos.xlsx')
