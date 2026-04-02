import pandas as pd
import os
import sys

# Importación local de Storage (Ownership)
from . import storage_tarjetas as storage
from core_sistema import db_ingesta, checksum_service
from modulo_compras import storage_compras

def normalizar_importe(texto):
    if not texto: return 0.0
    texto = str(texto).replace(".", "").replace(",", ".")
    try: return float(texto)
    except: return 0.0

def parse_payway_liq(csv_path):
    """
    EXTRACTOR ROBUSTO DE PAYWAY (CSV) CON CONTROL DE DUPLICADOS E IVA.
    """
    print(f"📄 Analizando CSV Payway: {os.path.basename(csv_path)}")
    
    # 1. CONTROL DE DUPLICADOS (HUELLA DIGITAL)
    es_nuevo, hash_val = checksum_service.validar_y_registrar("TARJETAS", "FILE", os.path.basename(csv_path), csv_path)
    if not es_nuevo:
        print(f"🚫 SALTADO: El archivo ya fue procesado anteriormente (Hash: {hash_val[:10]}...)")
        return

    try:
        # 2. DETECCIÓN ROBUSTA DE CABECERA
        # Leemos las primeras 20 líneas para buscar la fila que contiene 'Pago' o 'Marca'
        temp_df = pd.read_csv(csv_path, sep=',', encoding='latin1', nrows=20, header=None)
        header_idx = -1
        for i, row in temp_df.iterrows():
            row_str = " ".join(str(v).lower() for v in row.values)
            if "pago" in row_str and "marca" in row_str:
                header_idx = i
                break
        
        if header_idx == -1:
            raise ValueError("No se pudo detectar la fila de cabecera en el CSV de Payway.")

        df = pd.read_csv(csv_path, sep=',', encoding='latin1', skiprows=header_idx)
        print(f"   -> Cabecera detectada en fila {header_idx}. Procesando {len(df)} registros...")

        for _, row in df.iterrows():
            # Mapeo dinámico y manejo de importes
            bruto = normalizar_importe(row.get('Importe Bruto', 0))
            neto = normalizar_importe(row.get('Importe Neto', 0))
            
            # EXTRAER IVA (Si las columnas existen en este formato)
            # Payway a veces tiene 'IVA 21%' o 'IVA' a secas.
            iva_21 = normalizar_importe(row.get('IVA 21%', 0)) or normalizar_importe(row.get('IVA', 0))
            iva_105 = normalizar_importe(row.get('IVA 10.5%', 0))
            arancel = normalizar_importe(row.get('Arancel/Serv. Financ.', 0))

            data = {
                "fuente": "PAYWAY",
                "tipo": "DIARIA",
                "fecha_liquidacion": pd.to_datetime(row['Pago'], dayfirst=True).strftime('%Y-%m-%d'),
                "marca": str(row.get('Marca', 'DESCONOCIDA')),
                "establecimiento": str(row.get('Establecimiento', 'S/N')),
                "total_bruto": bruto,
                "costo_arancel": arancel,
                "retenciones": normalizar_importe(row.get('Impuestos (Suj. a Retenc / Perc)', 0)),
                "total_neto": neto,
                "metadata": {"nro_liquidacion": str(row.get('Nro. Liquidación', ''))}
            }
            
            # Guardar en módulo Tarjetas
            liq_id = storage.save_liquidacion(data)
            
            # REPORTE FISCAL (Si hay IVA, se notifica al Módulo Compras/Fiscal)
            if liq_id and (iva_21 > 0 or iva_105 > 0):
                storage_compras.registrar_impuesto({
                    "modulo": "TARJETAS",
                    "fuente": "PAYWAY",
                    "fecha": data["fecha_liquidacion"],
                    "neto_gravado": arancel, # El IVA suele ser sobre el arancel
                    "iva_105": iva_105,
                    "iva_21": iva_21,
                    "descripcion": f"Comisión Liq {row.get('Nro. Liquidación')} - {data['marca']}",
                    "extern_id": liq_id
                })

            # Guardar detalle atómico
            if liq_id:
                detalle = [{
                    "fecha": data["fecha_liquidacion"],
                    "descripcion": f"Liq {row.get('Nro. Liquidación')} - {data['marca']}",
                    "monto_bruto": bruto,
                    "monto_neto": neto,
                    "metadata_raw": row.to_dict()
                }]
                storage.save_liquidacion_detalle(liq_id, detalle)
            
        print(f"🧱 Éxito: Liquidación Payway procesada y reportada al módulo fiscal.")
        
        # 3. Notificar al Core para actualizar el índice de búsqueda
        db_ingesta.update_search_index()

    except Exception as e:
        print(f"❌ Error procesando Payway Liq: {e}")

if __name__ == "__main__":
    CSV = r"C:\Users\essao\Downloads\Liquidaciones diarias en pesos delimitadas por comas.csv"
    if os.path.exists(CSV):
        parse_payway_liq(CSV)
