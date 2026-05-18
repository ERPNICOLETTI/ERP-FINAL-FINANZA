import os
import shutil
from datetime import datetime
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')
BACKUPS_DIR = os.path.join(BASE_DIR, 'backups')

def create_db_backup():
    """Copia la base de datos a la carpeta backups con fecha y hora en el nombre."""
    if not os.path.exists(DB_PATH):
        print(f"❌ [BACKUP] No se encontró la base de datos en: {DB_PATH}")
        return False
        
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    backup_name = f"erp_nicoletti_{timestamp}.db"
    backup_path = os.path.join(BACKUPS_DIR, backup_name)
    
    try:
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ [BACKUP] Éxito. Copia guardada como: backups/{backup_name}")
        return True
    except Exception as e:
        print(f"❌ [BACKUP] Error al crear el backup: {e}")
        return False

def git_sync():
    """Agrega, hace commit y push de todo el código (ignorando la DB gracias al .gitignore)."""
    print("\n🔄 [GIT] Iniciando sincronización del código fuente...")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    try:
        # 1. Add
        print("  -> Ejecutando 'git add .'")
        subprocess.run(["git", "add", "."], check=True, cwd=BASE_DIR)
        
        # 2. Commit
        commit_msg = f"Auto-backup & Sincronización AI: {timestamp}"
        print(f"  -> Ejecutando 'git commit -m \"{commit_msg}\"'")
        res = subprocess.run(["git", "commit", "-m", commit_msg], cwd=BASE_DIR, capture_output=True, text=True)
        
        if "nothing to commit" in res.stdout.lower() or "nada para hacer commit" in res.stdout.lower():
            print("  -> No hay cambios nuevos en el código para subir.")
        else:
            print(f"✅ [GIT] Commit registrado localmente: '{commit_msg}'")
            
        # 3. Push
        print("  -> Ejecutando 'git push'")
        push_res = subprocess.run(["git", "push"], cwd=BASE_DIR, capture_output=True, text=True)
        
        if push_res.returncode == 0:
            print("✅ [GIT] Push exitoso. Tu código está seguro en la nube.")
        else:
            print(f"⚠️ [GIT] El comando push arrojó un error o advertencia:\n{push_res.stderr}")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ [GIT] Falló un comando de Git: {e}")
    except FileNotFoundError:
        print("❌ [GIT] Error: No se detectó 'git' instalado o configurado en tu terminal.")

if __name__ == "__main__":
    print("🚀 Iniciando Rutina de Seguridad (Backup de DB + Git Sync)")
    print("=" * 60)
    
    create_db_backup()
    git_sync()
    
    print("=" * 60)
    print("🎉 Rutina finalizada.")
