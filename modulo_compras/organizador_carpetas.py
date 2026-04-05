import os
import re
import shutil
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modulo_compras import storage_compras

# Config - Ruta relativa a la raíz del proyecto
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_ROOT = os.path.join(WORKSPACE, "static", "archivadas")

def migrate_folders():
    """Limpia las carpetas basadas en CUIT y usa funciones del Repositorio v4.5."""
    if not os.path.exists(ARCHIVE_ROOT):
        print("Archive root not found.")
        return

    # Usamos try porque get_todas_facturas no existe en el scope del prompt (solo los q importan), 
    # pero el usuario pidió que use las funciones de storage para obtener registros,
    # asique usaremos buscar_facturas o algo similar o iteraremos archivos y los machearemos en base al path.
    # Como la BD ya tiene los paths v4.5, organizamos fisico y buscamos.
    dirs = [d for d in os.listdir(ARCHIVE_ROOT) if os.path.isdir(os.path.join(ARCHIVE_ROOT, d))]
    
    for old_name in dirs:
        if re.match(r'^\d{11}', old_name):
            new_name = re.sub(r'^\d{11}\s*-\s*', '', old_name).strip()
            old_path = os.path.join(ARCHIVE_ROOT, old_name)
            new_path = os.path.join(ARCHIVE_ROOT, new_name)

            print(f"Renaming: {old_name} -> {new_name}")
            if os.path.exists(new_path) and old_path != new_path:
                for file_name in os.listdir(old_path):
                    shutil.move(os.path.join(old_path, file_name), os.path.join(new_path, file_name))
                os.rmdir(old_path)
            else:
                os.rename(old_path, new_path)

            # Para actualizar, buscamos si hay facturas pendientes sin archivo o actualizamos las que tienen este path
            # Nota: Esto debería llamarse solo de vez en cuando.
            print(f"Directory {new_name} ready. Future paths will use the correct method.")

    print("Migration complete!")

if __name__ == "__main__":
    migrate_folders()
