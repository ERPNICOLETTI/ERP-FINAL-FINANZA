import os
import shutil
import re
import hashlib
from datetime import datetime
import logging

# SERVICIO DE ARCHIVADO LEGAL (COMPLIANCE) 📜📁⚖️
# Encargado del resguardo físico de documentos probatorios.

logger = logging.getLogger(__name__)

def calculate_hash(filepath):
    """Calcula el hash MD5 de un archivo para control de unicidad."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def sanitize_filename(filename):
    """Limpia el nombre del archivo de caracteres no permitidos."""
    return re.sub(r'[^\w\.-]', '_', filename)

def archivar_documento(filepath_origen, modulo, anio, mes, entidad, use_vault=True, overwrite=False, subcategoria=None):
    """
    Mueve un archivo crudo analizado a la estructura jerárquica modular.
    Estructura v4.7: 
    - Bóveda:  modulo_{M}/archivos_{M}/[subcategoria]/{ENTIDAD}/{AÑO}/{MES}/
    - Histórico: modulo_{M}/crudos_{M}/[subcategoria]/{ENTIDAD}/{AÑO}/{MES}/
    """
    if not os.path.exists(filepath_origen):
        raise FileNotFoundError(f"No se encontró el archivo de origen: {filepath_origen}")

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    entidad_clean = re.sub(r'[^\w\s-]', '_', entidad).strip().upper()
    
    # Seleccionar carpeta destino según propósito (Bóveda o Histórico)
    subfolder = f'archivos_{modulo.lower()}' if use_vault else f'crudos_{modulo.lower()}'
    
    if subcategoria:
        target_dir = os.path.join(
            BASE_DIR, 
            f'modulo_{modulo.lower()}', 
            subfolder,
            subcategoria,
            entidad_clean,
            str(anio),
            str(mes).zfill(2)
        ).replace('\\', '/')
    else:
        target_dir = os.path.join(
            BASE_DIR, 
            f'modulo_{modulo.lower()}', 
            subfolder,
            entidad_clean,
            str(anio),
            str(mes).zfill(2)
        ).replace('\\', '/')

    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    # 1. Calcular Hash del archivo a archivar
    current_hash = calculate_hash(filepath_origen)
    
    original_name = os.path.basename(filepath_origen)
    target_filename = sanitize_filename(original_name)
    target_path = os.path.join(target_dir, target_filename).replace('\\', '/')

    # 2. Política de Archivo Único por Hash
    if os.path.exists(target_path):
        existing_hash = calculate_hash(target_path)
        
        if current_hash == existing_hash:
            # Es un duplicado idéntico. No hacemos nada con el destino, simplemente retornamos la ruta existente.
            # El orquestador se encargará de borrar el origen (inbox).
            logger.info(f"📁 Archivo idéntico ya existe en {target_path}. Omitiendo duplicado.")
            return target_path.replace('\\', '/')
        
        # El contenido es distinto pero el nombre es igual.
        if not overwrite:
            # Mantener ambos con sufijo (Comportamiento por defecto en Bóveda)
            name, ext = os.path.splitext(target_filename)
            timestamp = datetime.now().strftime("%H%M%S")
            target_filename = f"{name}_{timestamp}_{current_hash[:6]}{ext}"
            target_path = os.path.join(target_dir, target_filename)
        else:
            # Sobreescribir (Comportamiento deseado en Histórico de Reportes)
            logger.info(f"🔄 Sobreescribiendo reporte anterior: {target_filename}")

    # 3. Mover Archivo
    try:
        shutil.move(filepath_origen, target_path)
        logger.info(f"✅ Archivo archivado legalmente en: {target_path}")
        return target_path.replace('\\', '/')
    except Exception as e:
        logger.error(f"❌ Error al mover el archivo: {e}")
        return None
