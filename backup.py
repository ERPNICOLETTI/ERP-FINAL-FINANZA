import os
import sys
import zipfile
import datetime
import subprocess

# Configurar salida UTF-8 en consola de Windows para evitar UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    # Versiones antiguas de Python que no soportan reconfigure
    pass

# Configuración de Rutas
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
BACKUP_DIR = os.path.join(DESKTOP_DIR, "Backup")

# Directorios a excluir en el ZIP
EXCLUDE_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".idea", ".vscode"}

def run_cmd(cmd, cwd=None):
    """Ejecuta un comando en la consola de comandos de forma segura."""
    print(f"Executing: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        if res.stdout:
            print(res.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] al ejecutar {cmd[0]}: {e.stderr.strip()}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] inesperado ejecutando {cmd[0]}: {e}", file=sys.stderr)
        return False

def run_git_backup():
    """Ejecuta los comandos de Git locales y remotos."""
    print("\n--- [GIT] [1/3] Iniciando respaldo en Git ---")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. git add .
    run_cmd(["git", "add", "."], cwd=PROJECT_DIR)
    
    # 2. git commit
    run_cmd(["git", "commit", "-m", f"Backup automatico - {now_str}"], cwd=PROJECT_DIR)
    
    # 3. git push
    print("Enviando cambios al repositorio remoto...")
    run_git = run_cmd(["git", "push"], cwd=PROJECT_DIR)
    if run_git:
        print("[OK] Git push completado con exito.")
    else:
        print("[WARNING] No se pudo realizar git push (puede no haber un repositorio remoto configurado). El backup local continua.")

def create_zip_backup():
    """Crea una copia de seguridad integral en formato ZIP en el Escritorio."""
    print("\n--- [ZIP] [2/3] Generando archivo ZIP integral ---")
    
    # Asegurar que el directorio de Backup en el Escritorio exista
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Nombre de archivo basado en la fecha y hora
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    zip_filename = f"backup_{timestamp}.zip"
    zip_filepath = os.path.join(BACKUP_DIR, zip_filename)
    
    print(f"Creando respaldo en: {zip_filepath}")
    
    try:
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(PROJECT_DIR):
                # Excluir directorios no deseados al vuelo
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    # Calcular la ruta relativa para el interior del zip
                    arcname = os.path.relpath(file_path, PROJECT_DIR)
                    zipf.write(file_path, arcname)
                    
        print(f"[OK] Backup ZIP creado exitosamente en el Escritorio: {zip_filename}")
        return zip_filepath
    except Exception as e:
        print(f"[ERROR] al crear el archivo ZIP: {e}", file=sys.stderr)
        return None

def main():
    print("==================================================")
    print("       INICIANDO SCRIPT DE BACKUP ERP             ")
    print("==================================================")
    
    # 1. Ejecutar Git
    run_git_backup()
    
    # 2. Crear ZIP
    zip_path = create_zip_backup()
    
    print("\n==================================================")
    if zip_path:
        print("    PROCESO DE RESPALDO COMPLETADO CON EXITO!     ")
    else:
        print("    Proceso de respaldo terminado con advertencias.")
    print("==================================================")

if __name__ == "__main__":
    main()
