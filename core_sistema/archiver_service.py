import os
import shutil
import re
import hashlib
from datetime import datetime
import logging

# SERVICIO DE ARCHIVADO LEGAL (COMPLIANCE) 📜📁⚖️
# Encargado del resguardo físico de documentos probatorios.

logger = logging.getLogger(__name__)

def sanitize_filename(filename):
    """Limpia caracteres no permitidos en el sistema de archivos."""
    name, ext = os.path.splitext(filename)
    clean_name = re.sub(r'[^\w\s-]', '_', name).strip().upper()
    return f"{clean_name}{ext.lower()}"

def archivar_documento(filepath_origen, modulo, anio, mes, entidad):
    """
    Mueve un archivo procesado de 'inbox/' a la estructura jerárquica legal.
    Estructura: static/archivadas/{MODULO}/{AÑO}/{MES}/{ENTIDAD}/
    """
    if not os.path.exists(filepath_origen):
        raise FileNotFoundError(f"No se encontró el archivo de origen: {filepath_origen}")

    # 1. Definir Directorio Destino
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dir = os.path.join(
        BASE_DIR, 'static', 'archivadas',
        modulo.upper(),
        str(anio),
        str(mes).zfill(2),
        entidad.upper()
    )

    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        logger.info(f"📁 Creada nueva carpeta jerárquica: {target_dir}")

    # 2. Generar Nombre Destino Sanitizado
    original_name = os.path.basename(filepath_origen)
    target_filename = sanitize_filename(original_name)
    target_path = os.path.join(target_dir, target_filename)

    # 3. Prevención de Sobrescritura (Timestamp + Hash Short)
    if os.path.exists(target_path):
        name, ext = os.path.splitext(target_filename)
        # Calculamos un hash corto del contenido para distinguirlo
        with open(filepath_origen, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:6]
        timestamp = datetime.now().strftime("%H%M%S")
        target_filename = f"{name}_{timestamp}_{file_hash}{ext}"
        target_path = os.path.join(target_dir, target_filename)
        logger.warning(f"⚠️ Conflicto de nombre detectado. Renombrando a: {target_filename}")

    # 4. Mover Archivo
    try:
        shutil.move(filepath_origen, target_path)
        logger.info(f"✅ Archivo archivado legalmente: {target_path}")
        return os.path.abspath(target_path)
    except Exception as e:
        logger.error(f"❌ Error al mover el archivo al archivo legal: {e}")
        return None
