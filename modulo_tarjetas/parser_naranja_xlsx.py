import pandas as pd
import os
import logging
import hashlib
import json
from . import storage_tarjetas as storage

# Parser Naranja XLSX (Digitalización Bit a Bit) 🏗️🧱🧠⚖️🚀
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

def normalizar_importe(val):
    """Limpia valores numéricos/moneda de Excel."""
    if pd.isna(val) or val is None: return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace("$", "").replace(" ", "").strip()
    s = "".join(c for c in s if c in "0123456789.,-")
    if not s: return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."): s = s.replace(".", "").replace(",", ".")
        else: s = s.replace(",", "")
    elif "," in s: s = s.replace(",", ".")
    try: return float(s)
    except: return 0.0

def procesar_archivo(file_path):
    """Función principal (Phase 3): Ingesta el XLSX de Naranja y retorna (success, info)."""
    if not os.path.exists(file_path):
        logger.error(f"⚠️ El archivo no existe: {file_path}")
        return False, None

    logger.info(f"💎 PROCESANDO NARANJA XLSX: {os.path.basename(file_path)}")
    file_hash = calculate_sha256(file_path)
    
    try:
        df = pd.read_excel(file_path)
        last_id = None
        
        # Mapeo de meses en español (Naranja usa formato 27/ENE/26)
        meses_map = {
            'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04', 'MAY': '05', 'JUN': '06',
            'JUL': '07', 'AGO': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
        }

        for idx, row in df.iterrows():
            # 1. Normalizar Fecha
            fecha_raw = str(row.get('Fecha', ''))
            fecha_iso = "2026-01-01" # Fallback
            import re
            m = re.search(r'(\d+)/([A-Z]+)/(\d+)', fecha_raw)
            if m:
                dia = m.group(1).zfill(2)
                mes_esp = m.group(2)
                anio = "20" + m.group(3)
                mes_num = meses_map.get(mes_esp, "01")
                fecha_iso = f"{anio}-{mes_num}-{dia}"
            
            # 2. Empaquetado Híbrido (Diseño Fase 2)
            # Extraemos lo duro y el resto va al volcado JSON
            data_row = {
                "fuente": "NARANJA",
                "tipo": "DIARIA",
                "marca": "NARANJA",
                "fecha_liquidacion": fecha_iso,
                "periodo": fecha_iso[:7],
                "total_bruto": normalizar_importe(row.get('Monto bruto')),
                "total_neto": normalizar_importe(row.get('Monto neto')),
                "costo_arancel": normalizar_importe(row.get('Arancel')),
                "costo_financiero": normalizar_importe(row.get('Interes por plan', 0)) + normalizar_importe(row.get('Interes por pago anticipado', 0)),
                "iva_21": normalizar_importe(row.get('IVA', 0)) + normalizar_importe(row.get('Percepción IVA', 0)),
                "retenciones": normalizar_importe(row.get('Retención de ingresos brutos', 0)) + normalizar_importe(row.get('SIRTAC', 0)),
                "establecimiento": str(row.get('N° de comercio', '')),
                "hash_archivo": file_hash,
                "row_index": idx,
                "row_dump": row.to_dict() # Se guardará en metadata_cruda
            }

            # 3. Persistencia via Storage (Modular)
            liq_id = storage.save_liquidacion(data_row)
            if liq_id:
                last_id = liq_id
        
        if last_id:
            info = {
                "modulo": "TARJETAS",
                "anio": fecha_iso[:4] if 'fecha_iso' in locals() else "2026",
                "mes": fecha_iso[5:7] if 'fecha_iso' in locals() else "01",
                "entidad": "NARANJA",
                "db_table": "liquidaciones_tarjetas",
                "id_insertado": last_id
            }
            return True, info
        else:
            logger.warning(f"🚫 Archivo omitido (sin registros nuevos): {os.path.basename(file_path)}")
            return False, None

    except Exception as e:
        logger.error(f"❌ Error crítico procesando Naranja XLSX: {e}")
        return False, None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        procesar_archivo(sys.argv[1])
    else:
        logger.warning("Uso: python parser_naranja_xlsx.py <absolute_path>")
