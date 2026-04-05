import os
import logging
import hashlib
import json
import pandas as pd
from datetime import datetime
from . import storage_compras as storage

# IMPORTADOR CALIM (EXCEL/CALAMINE) - Phase 3 🏗️🧱🧠⚖️🚀
# Esta versión implementa el Diseño Híbrido y el archivado legal.

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mapeo CALIM a AFIP
CALIM_TO_AFIP_CODIGO = {
    'Factura A': 1, 'Nota de Débito A': 2, 'Nota de Crédito A': 3,
    'Factura B': 6, 'Nota de Débito B': 7, 'Nota de Crédito B': 8,
    'Factura C': 11, 'Nota de Débito C': 12, 'Nota de Crédito C': 13,
    'Factura M': 51, 'Nota de Débito M': 52, 'Nota de Crédito M': 53
}

def calculate_sha256(file_path):
    """Calcula el hash SHA-256 del archivo para el control de idempotencia."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def parse_money(val):
    if pd.isna(val) or val is None: return 0.0
    val = str(val).replace('$', '').replace('.', '').replace(',', '.').strip()
    try: return float(val)
    except: return 0.0

def procesar_archivo(file_path):
    """Función principal (Phase 3): Ingesta el Excel de CALIM y retorna (success, info)."""
    if not os.path.exists(file_path):
        logger.error(f"⚠️ El archivo no existe: {file_path}")
        return False, None

    logger.info(f"🧾 Analizando Excel de CALIM: {os.path.basename(file_path)}")
    file_hash = calculate_sha256(file_path)
    
    try:
        # CALIM suele enviar Excels con errores de formato, calamine es más robusto
        df = pd.read_excel(file_path, engine='calamine')
        df = df.dropna(subset=['Numero', 'Total'])
        
        last_id = None
        first_row_date = "2026-01-01"

        for idx, row in df.iterrows():
            try:
                fecha_raw = str(row['Fecha']).strip()
                fecha_emision = datetime.strptime(fecha_raw, "%d/%m/%Y").strftime("%Y-%m-%d") if '/' in fecha_raw else fecha_raw
                if idx == 0: first_row_date = fecha_emision

                neto = parse_money(row.get('Neto'))
                iva21 = parse_money(row.get('Iva'))
                total = parse_money(row.get('Total'))
                tipo_nombre = str(row['Tipo']).strip()
                
                num_parts = str(row['Numero']).split('-')
                pv = num_parts[0].strip().zfill(5) if len(num_parts) == 2 else "00000"
                n = num_parts[1].strip().zfill(8) if len(num_parts) == 2 else str(row['Numero']).strip().zfill(8)
                
                # Diseño Híbrido: Empaquetar fila completa en meta_json via row_dump
                factura_data = {
                    "punto_venta": pv,
                    "numero_comprobante": n,
                    "tipo_operacion": 'COMPRA' if 'Compra' in os.path.basename(file_path) else 'VENTA',
                    "tipo_comprobante": tipo_nombre,
                    "proveedor": str(row['Proveedor']).strip(),
                    "fecha": fecha_emision,
                    "neto": neto,
                    "iva21": iva21,
                    "total": total,
                    "hash_archivo": file_hash,
                    "origen": "CALIM_EXCEL",
                    "status": "CONCILIADO_CALIM",
                    "row_dump": row.to_dict()
                }

                f_id = storage.save_factura(factura_data)
                if f_id: last_id = f_id
                    
            except Exception as e:
                logger.warning(f"⚠️ Error en fila {idx}: {e}")

        if last_id:
            info = {
                "modulo": "COMPRAS",
                "anio": first_row_date[:4],
                "mes": first_row_date[5:7],
                "entidad": "CALIM_ESTUDIO",
                "db_table": "facturas",
                "id_insertado": last_id
            }
            return True, info
        else:
            logger.warning(f"🚫 Archivo CALIM omitido (sin facturas nuevas): {os.path.basename(file_path)}")
            return False, None
        
    except Exception as e:
        logger.error(f"❌ Error fatal procesando CALIM: {e}")
        return False, None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for f in sys.argv[1:]:
            procesar_archivo(f)
    else:
        logger.warning("Uso: python importador_calim.py <absolute_path>")
