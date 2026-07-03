import os
import shutil
import sys

# Configure UTF-8 encoding for console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

TARGET_DIR = os.path.join("modulo_bancos", "crudos_bancos")

def main():
    if not os.path.exists(TARGET_DIR):
        print(f"Error: La carpeta {TARGET_DIR} no existe.")
        return

    print(f"Iniciando la limpieza de: {TARGET_DIR}")
    deleted_files = 0
    deleted_dirs = 0

    for item in os.listdir(TARGET_DIR):
        item_path = os.path.join(TARGET_DIR, item)
        try:
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                deleted_dirs += 1
                print(f"  Directorio eliminado: {item_path}")
            else:
                os.remove(item_path)
                deleted_files += 1
                print(f"  Archivo eliminado: {item_path}")
        except Exception as e:
            print(f"  Error al eliminar {item_path}: {e}")

    print(f"\nLimpieza completada:")
    print(f"  - Directorios eliminados: {deleted_dirs}")
    print(f"  - Archivos eliminados: {deleted_files}")

if __name__ == "__main__":
    main()
