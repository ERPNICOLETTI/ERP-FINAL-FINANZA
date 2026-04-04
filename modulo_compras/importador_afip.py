import pandas as pd
import os
import logging
import hashlib
import json
from . import storage_compras as storage

# IMPORTADOR AFIP (CSV) - Phase 3 🏗️🧱🧠⚖️🚀
# Esta versión implementa el Diseño Híbrido y el archivado legal.

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mapeo de Códigos de AFIP
AFIP_TIPO_COMPROBANTE = {
    1: 'Factura A', 2: 'Nota de Débito A', 3: 'Nota de Crédito A',
    6: 'Factura B', 7: 'Nota de Débito B', 8: 'Nota de Crédito B',
    11: 'Factura C', 12: 'Nota de Débito C', 13: 'Nota de Crédito C',
    51: 'Factura M', 52: 'Nota de Débito M', 53: 'Nota de Crédito M'
}

def calculate_sha256(file_path):
    """Calcula el hash SHA-256 del archivo para el control de idempotencia."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def clean_amount(val):
    """Convierte montos con coma a float puro."""
    if pd.isna(val) or val is None: return 0.0
    val_str = str(val).replace('.', '').replace(',', '.')
    try: return float(val_str)
    except: return 0.0

def procesar_archivo(file_path):
    """Función principal (Phase 3): Ingesta el CSV de AFIP y retorna (success, info)."""
    if not os.path.exists(file_path):
        logger.error(f"⚠️ El archivo no existe: {file_path}")
        return False, None

    logger.info(f"🧾 Analizando CSV de AFIP: {os.path.basename(file_path)}")
    file_hash = calculate_sha256(file_path)
    
    try:
        # AFIP usa punto y coma, y codificación en español utf-8
        df = pd.read_csv(file_path, sep=';', skiprows=0, dtype=str, encoding='utf-8')
        df = df.dropna(subset=['Fecha de Emisión'])
        
        last_id = None
        first_row_date = "2026-01-01"

        for idx, row in df.iterrows():
            try:
                fecha_emision_raw = str(row['Fecha de Emisión']).strip()
                # AFIP usa DD/MM/AAAA o YYYY-MM-DD
                import re
                fecha_iso = "2026-01-01"
                m_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', fecha_emision_raw)
                m_slash = re.search(r'(\d{2})/(\d{2})/(\d{4})', fecha_emision_raw)
                
                if m_iso:
                    fecha_iso = f"{m_iso.group(1)}-{m_iso.group(2)}-{m_iso.group(3)}"
                elif m_slash:
                    fecha_iso = f"{m_slash.group(3)}-{m_slash.group(2)}-{m_slash.group(1)}"
                
                if idx == 0: first_row_date = fecha_iso

                tipo_codigo = int(float(str(row['Tipo de Comprobante'])))
                tipo_nombre = AFIP_TIPO_COMPROBANTE.get(tipo_codigo, f'Tipo {tipo_codigo}')
                
                pv = str(row['Punto de Venta']).strip().zfill(5)
                num = str(row['Número Desde']).strip().zfill(8)
                codigo_str = str(tipo_codigo).zfill(3)
                numero_completo = f"{codigo_str}-{pv}-{num}"
                
                # Unificación de Columnas CUIT/Entidad (Soporte Multi-Formato)
                if 'Denominación Receptor' in row.index or 'Receptor' in row.index:
                    tipo_operacion = 'VENTA'
                    doc_entity = str(row.get('Nro. Doc. Receptor', row.get('CUIT Receptor', ''))).strip()
                    denom_entity = str(row.get('Denominación Receptor', 'Consumidor Final')).strip()
                else:
                    tipo_operacion = 'COMPRA'
                    # Probar varios nombres de columna para CUIT y Denominacion (Emisor)
                    doc_entity = str(row.get('Nro. Doc. Emisor', row.get('CUIT Emisor', ''))).strip()
                    denom_entity = str(row.get('Denominación Emisor', row.get('Nombre Emisor', 'Proveedor'))).strip()

                neto_gravado = clean_amount(row.get('Imp. Neto Gravado Total', row.get('Imp. Neto Gravado', '0')))
                monto_iva = clean_amount(row.get('Total IVA', row.get('Importe IVA', '0')))
                monto_total = clean_amount(row.get('Imp. Total', '0'))

                # Diseño Híbrido: Todo el resto de la fila al JSON
                factura_data = {
                    "numero_completo": numero_completo,
                    "tipo_operacion": tipo_operacion,
                    "tipo_comprobante": tipo_nombre,
                    "proveedor": denom_entity,
                    "cuit_proveedor": doc_entity,
                    "fecha": fecha_iso,
                    "neto_gravado": neto_gravado,
                    "monto_iva": monto_iva,
                    "monto_total": monto_total,
                    "hash_archivo": file_hash,
                    "origen": "AFIP_CSV",
                    "status": "DIGITALIZADO",
                    "row_dump": row.to_dict()
                }

                f_id = storage.save_factura(factura_data)
                if f_id: last_id = f_id

            except Exception as e:
                logger.warning(f"⚠️ Error en fila {idx}: {e}")
                continue

        if last_id:
            info = {
                "modulo": "COMPRAS",
                "anio": first_row_date[:4],
                "mes": first_row_date[5:7],
                "entidad": "ARCA_AFIP",
                "db_table": "facturas",
                "id_insertado": last_id
            }
            return True, info
        else:
            logger.warning(f"🚫 Archivo AFIP omitido (sin facturas nuevas): {os.path.basename(file_path)}")
            return False, None

    except Exception as e:
        logger.error(f"❌ Error fatal procesando AFIP: {e}")
        return False, None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        procesar_archivo(sys.argv[1])
    else:
        logger.warning("Uso: python importador_afip.py <absolute_path>")
