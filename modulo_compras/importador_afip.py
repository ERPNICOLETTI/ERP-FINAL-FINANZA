import pandas as pd
import os
import sys

# Importaciones Modulares (Ownership)
from . import storage_compras as storage
from core_sistema import db_ingesta, checksum_service

# Mapeo de Códigos de AFIP a Nombres Humanos
AFIP_TIPO_COMPROBANTE = {
    1: 'Factura A',
    2: 'Nota de Débito A',
    3: 'Nota de Crédito A',
    6: 'Factura B',
    7: 'Nota de Débito B',
    8: 'Nota de Crédito B',
    11: 'Factura C',
    12: 'Nota de Débito C',
    13: 'Nota de Crédito C',
    51: 'Factura M',
    52: 'Nota de Débito M',
    53: 'Nota de Crédito M'
}

def clean_amount(val):
    """Convierte montos con coma (ej. 1500,50) a float puro (1500.50)"""
    if pd.isna(val):
        return 0.0
    val_str = str(val).replace('.', '').replace(',', '.')
    try:
        return float(val_str)
    except:
        return 0.0

def parse_afip_csv(file_path):
    """
    IMPORTADOR ROBUSTO DE AFIP (CSV).
    """
    print(f"🧾 Analizando CSV de AFIP: {os.path.basename(file_path)}")
    
    # 1. CONTROL DE DUPLICADOS
    es_nuevo, hash_val = checksum_service.validar_y_registrar("COMPRAS", "FILE", os.path.basename(file_path), file_path)
    if not es_nuevo:
        print(f"🚫 SALTADO: Ya procesado.")
        return

    try:
        # AFIP usa punto y coma, y codificación en español utf-8
        df = pd.read_csv(file_path, sep=';', skiprows=0, dtype=str, encoding='utf-8')
        
        # Detección de filas vacías de AFIP
        df = df.dropna(subset=['Fecha de Emisión'])
        
        registros_procesados = 0

        for idx, row in df.iterrows():
            try:
                fecha_emision = str(row['Fecha de Emisión']).strip()
                tipo_codigo = int(float(str(row['Tipo de Comprobante'])))
                tipo_nombre = AFIP_TIPO_COMPROBANTE.get(tipo_codigo, f'Tipo {tipo_codigo}')
                
                # Formatear el número completo (Ej: 001-00005-00007365) para evitar conflictos UNIQUE
                pv = str(row['Punto de Venta']).strip().zfill(5)
                num = str(row['Número Desde']).strip().zfill(8)
                codigo_str = str(tipo_codigo).zfill(3)
                numero_completo = f"{codigo_str}-{pv}-{num}"
                
                # Receptor o Emisor (Cliente o Proveedor dependiendo si es Emitido o Recibido)
                if 'Denominación Receptor' in row.index:
                    tipo_operacion = 'VENTA'
                    doc_entity = str(row['Nro. Doc. Receptor']).strip() if 'Nro. Doc. Receptor' in row.index and not pd.isna(row['Nro. Doc. Receptor']) else ""
                    denom_entity = str(row['Denominación Receptor']).strip() if not pd.isna(row['Denominación Receptor']) else "Consumidor Final"
                elif 'Denominación Emisor' in row.index:
                    tipo_operacion = 'COMPRA'
                    doc_entity = str(row['Nro. Doc. Emisor']).strip() if 'Nro. Doc. Emisor' in row.index and not pd.isna(row['Nro. Doc. Emisor']) else ""
                    denom_entity = str(row['Denominación Emisor']).strip() if not pd.isna(row['Denominación Emisor']) else "Desconocido"
                else:
                    tipo_operacion = 'DESCONOCIDO'
                    doc_entity, denom_entity = "", "Consumidor Final"

                proveedor_cliente = f"{doc_entity} - {denom_entity}".strip(" - ")
                
                # Montos
                neto_gravado = clean_amount(row.get('Imp. Neto Gravado Total', '0'))
                monto_iva = clean_amount(row.get('Total IVA', '0'))
                monto_total = clean_amount(row.get('Imp. Total', '0'))
                # El archivo original de AFIP los trae en positivo siempre.
                # Nuestro Parser "lector" los negativiza si es Nota de Crédito para balancear la BD.
                if 'Crédito' in tipo_nombre:
                    neto_gravado = -abs(neto_gravado)
                    monto_iva = -abs(monto_iva)
                    monto_total = -abs(monto_total)

                # 5. Inserción mediante Storage Modular
                factura_data = {
                    "numero_completo": numero_completo,
                    "tipo_operacion": tipo_operacion,
                    "tipo_comprobante": tipo_nombre,
                    "proveedor": proveedor_cliente,
                    "fecha_emision": fecha_emision,
                    "neto_gravado": neto_gravado,
                    "monto_iva": monto_iva,
                    "monto_total": monto_total,
                    "status": "DIGITALIZADO"
                }
                storage.save_factura(factura_data)
                registros_procesados += 1

            except Exception as e:
                print(f"⚠️ Error en fila {idx}: {e}")
                continue

        print(f"✨ Éxito: {registros_procesados} comprobantes de AFIP sincronizados.")
        db_ingesta.update_search_index()
    except Exception as e:
        print(f"❌ Error crítico procesando archivo: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parse_afip_csv(sys.argv[1])
    else:
        print("💡 Uso: python parser_facturas.py 'ruta_al_excel_afip.csv'")
