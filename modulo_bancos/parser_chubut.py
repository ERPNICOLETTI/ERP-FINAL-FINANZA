import pandas as pd
import os
import logging
import hashlib
import json
from . import storage_bancos as storage
from modulo_compras import storage_compras

# Parser Banco Chubut Movimientos Históricos 🏦🏗️🧱🧠⚖️
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

def normalizar_importe_banco(val):
    """Limpia valores numéricos de Excel."""
    if pd.isna(val) or val is None: return 0.0
    try: return float(val)
    except: return 0.0

def procesar_archivo(file_path):
    """Función principal (Phase 3): Ingesta el extracto de Chubut y retorna (success, info)."""
    if not os.path.exists(file_path):
        logger.error(f"⚠️ El archivo no existe: {file_path}")
        return False, None

    logger.info(f"🏦 Analizando extracto Banco Chubut: {os.path.basename(file_path)}")
    file_hash = calculate_sha256(file_path)
    
    try:
        df = pd.read_excel(file_path, header=None)
        
        # 2. Detección Dinámica de Cabecera
        header_idx = -1
        cuenta_detectada = "SIN_ASIGNAR"
        for i, row in df.iterrows():
            row_str = " ".join(str(v).lower() for v in row.values)
            if "cuenta" in row_str:
                for val in row.values:
                    if any(char.isdigit() for char in str(val)):
                        cuenta_detectada = str(val).strip()
                        break
            if "fecha" in row_str and ("movimiento" in row_str or "concepto" in row_str):
                header_idx = i
                break
        
        if header_idx == -1:
            logger.error("❌ No se pudo detectar la tabla de movimientos en el Excel.")
            return False, None

        column_names = [str(c).strip().upper() for c in df.iloc[header_idx]]
        df_movs = df.iloc[header_idx + 1:].copy()
        df_movs.columns = column_names
        
        movimientos = []
        last_id = None
        first_date = "2026-01-01"

        for _, row in df_movs.iterrows():
            raw_fecha = row.get('FECHA')
            if pd.isna(raw_fecha): continue
            
            try:
                fecha_dt = pd.to_datetime(raw_fecha, dayfirst=True)
                fecha_iso = fecha_dt.strftime('%Y-%m-%d')
                if not movimientos: first_date = fecha_iso
            except: continue

            desc = str(row.get('DESCRIPCIÓN DE MOVIMIENTO', row.get('CONCEPTO', ''))).strip()
            importe = normalizar_importe_banco(row.get('IMPORTE', 0))
            
            if desc and (importe != 0):
                mov_data = {
                    "banco": "CHUBUT",
                    "cuenta": cuenta_detectada,
                    "fecha": fecha_iso,
                    "descripcion": desc,
                    "tipo_movimiento": str(row.get('CÓDIGO', '')).strip(),
                    "importe": importe,
                    "hash_archivo": file_hash,
                    "row_dump": row.to_dict()
                }
                movimientos.append(mov_data)

                # Detección de IVA
                if "iva" in desc.lower() and "21" in desc.lower():
                    storage_compras.registrar_impuesto({
                        "modulo": "BANCOS", "fuente": "CHUBUT", "fecha": fecha_iso,
                        "neto_gravado": 0, "iva_21": abs(importe), "iva_105": 0,
                        "descripcion": f"IVA Bancario: {desc}", "hash_archivo": file_hash
                    })

        if movimientos:
            agregados, last_id = storage.save_movimiento_banco(movimientos, file_hash)
            if last_id:
                info = {
                    "modulo": "BANCOS",
                    "anio": first_date[:4],
                    "mes": first_date[5:7],
                    "entidad": "BANCO_CHUBUT",
                    "db_table": "bancos_movimientos",
                    "id_insertado": last_id
                }
                return True, info
        
        logger.warning(f"🚫 Archivo Chubut omitido (sin nuevos datos): {os.path.basename(file_path)}")
        return False, None

    except Exception as e:
        logger.error(f"❌ Error crítico en Banco Chubut: {e}")
        return False, None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        procesar_archivo(sys.argv[1])
    else:
        logger.warning("Uso: python parser_chubut.py <absolute_path>")
