import zipfile
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

zip_path = r"C:\Users\essao\Desktop\Backup\backup_2026-06-08_12-39-20.zip"
temp_db_path = "erp_nicoletti_backup_temp.db"

if not os.path.exists(zip_path):
    print(f"Zip not found: {zip_path}")
    sys.exit(1)

# Extract only the DB file
print(f"Extracting erp_nicoletti.db from {zip_path}...")
with zipfile.ZipFile(zip_path, 'r') as zf:
    zf.extract("erp_nicoletti.db", path=".")
    
# Rename to temp DB path
if os.path.exists("erp_nicoletti.db"):
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)
    os.rename("erp_nicoletti.db", temp_db_path)

# Query temp DB
conn = sqlite3.connect(temp_db_path)
conn.row_factory = sqlite3.Row

print("=== ESCO REGISTRATIONS IN BACKUP ===")
rows = conn.execute("""
    SELECT r.id, r.descripcion, r.monto, r.fecha, r.fuente, t.nombre as tipo_nombre, t.cuenta_codigo 
    FROM gastos_registros r
    JOIN gastos_tipos t ON r.gasto_tipo_id = t.id
    WHERE r.descripcion LIKE '%ESCO%' OR t.nombre LIKE '%ESCO%'
""").fetchall()

for r in sorted(rows, key=lambda x: x['monto']):
    print(dict(r))

conn.close()

# Cleanup temp DB
if os.path.exists(temp_db_path):
    os.remove(temp_db_path)
