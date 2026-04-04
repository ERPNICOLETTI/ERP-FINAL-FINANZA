import pandas as pd
import os
import logging
import hashlib
import json
from . import storage_bancos as storage

# Parser Banco Credicoop (Joaquín) - Phase 3 🏦🏗️🧱🧠⚖️
# Esta versión implementa el Diseño Híbrido y el archivado legal.

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def calculate_sha256(file_path):
    """Calcula el hash SHA-256 del archivo para el control de idempotencia."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def procesar_archivo(file_path):
    """Función principal (Phase 3): Ingesta el extracto de Credicoop y retorna (success, info)."""
    if not os.path.exists(file_path):
        logger.error(f"⚠️ El archivo no existe: {file_path}")
        return False, None

    logger.info(f"🏦 Analizando extracto Credicoop (Joaquín): {os.path.basename(file_path)}")
    file_hash = calculate_sha256(file_path)
    
    try:
        df = pd.read_excel(file_path)
        last_id = None
        first_date = "2026-01-01"
        movimientos = []

        for idx, row in df.iterrows():
            try:
                fecha = str(row['Fecha']).strip()
                if "nan" in fecha.lower(): continue
                if idx == 0: first_date = fecha
                
                # Diseño Híbrido: Empaquetado de fila
                mov_data = {
                    "banco": "CREDICOOP",
                    "cuenta": "CA_JOAQUIN_9087",
                    "fecha": fecha,
                    "descripcion": str(row['Concepto']).strip(),
                    "tipo_movimiento": str(row.get('Cod.', '')).strip(),
                    "importe": float(row['Monto']),
                    "hash_archivo": file_hash,
                    "row_dump": row.to_dict()
                }
                movimientos.append(mov_data)

            except Exception as e:
                logger.warning(f"⚠️ Error en fila {idx}: {e}")
                continue

        if movimientos:
            agregados, last_id = storage.save_movimiento_banco(movimientos, file_hash)
            if last_id:
                info = {
                    "modulo": "BANCOS",
                    "anio": first_date[:4] if first_date else "2026",
                    "mes": first_date[5:7] if first_date else "01",
                    "entidad": "BANCO_CREDICOOP",
                    "db_table": "bancos_movimientos",
                    "id_insertado": last_id
                }
                return True, info
        
        logger.warning(f"🚫 Archivo Credicoop omitido: {os.path.basename(file_path)}")
        return False, None

    except Exception as e:
        logger.error(f"❌ Error en parser Credicoop: {e}")
        return False, None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        procesar_archivo(sys.argv[1])
    else:
        logger.warning("Uso: python parser_credicoop_joaquin.py <absolute_path>")
