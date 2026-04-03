import os
import re
import sqlite3
import shutil

# Config - Ruta relativa a la raíz del proyecto
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_ROOT = os.path.join(WORKSPACE, "static", "archivadas")
DB_PATH = os.path.join(WORKSPACE, "erp_nicoletti.db")

def migrate_folders():
    if not os.path.exists(ARCHIVE_ROOT):
        print("Archive root not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    dirs = [d for d in os.listdir(ARCHIVE_ROOT) if os.path.isdir(os.path.join(ARCHIVE_ROOT, d))]
    
    for old_name in dirs:
        # Detect CUIT (11 digits at start)
        if re.match(r'^\d{11}', old_name):
            new_name = re.sub(r'^\d{11}\s*-\s*', '', old_name).strip()
            
            old_path = os.path.join(ARCHIVE_ROOT, old_name)
            new_path = os.path.join(ARCHIVE_ROOT, new_name)

            print(f"Renaming: {old_name} -> {new_name}")
            
            # Handle if new folder already exists (merge)
            if os.path.exists(new_path) and old_path != new_path:
                for file_name in os.listdir(old_path):
                    shutil.move(os.path.join(old_path, file_name), os.path.join(new_path, file_name))
                os.rmdir(old_path)
            else:
                os.rename(old_path, new_path)

            # Update DB paths
            # In DB, paths are absolute. We need to replace the old folder name with the new one.
            # Using REPLACE in SQL for the ruta_archivo column
            cur.execute("UPDATE facturas SET ruta_archivo = REPLACE(ruta_archivo, ?, ?) WHERE ruta_archivo LIKE ?", (old_name, new_name, f"%{old_name}%"))
            print(f"Updated DB records for: {new_name}")

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate_folders()
