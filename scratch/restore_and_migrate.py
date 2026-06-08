import zipfile
import sqlite3
import os

zip_path = r"C:\Users\essao\Desktop\Backup\backup_2026-06-08_12-39-20.zip"
db_path = "erp_nicoletti.db"

# 1. Extract DB from zip to root
print(f"Extracting erp_nicoletti.db from {zip_path}...")
with zipfile.ZipFile(zip_path, 'r') as zf:
    zf.extract("erp_nicoletti.db", path=".")

# 2. Open DB and run migrations
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if fecha_compra exists in gastos_registros
cursor.execute("PRAGMA table_info(gastos_registros)")
columns = [col[1] for col in cursor.fetchall()]

if "fecha_compra" not in columns:
    print("Migrating schema: Adding 'fecha_compra' column to 'gastos_registros'...")
    cursor.execute("ALTER TABLE gastos_registros ADD COLUMN fecha_compra TEXT")
    cursor.execute("UPDATE gastos_registros SET fecha_compra = fecha")
    print("Schema migrated.")
else:
    print("'fecha_compra' column already exists.")

# Check if gastos_tipos has ESCO Jorge
cursor.execute("SELECT id FROM gastos_tipos WHERE id = 133")
has_133 = cursor.fetchone()
if not has_133:
    print("Re-creating 'ESCO Jorge' category under JOR (id 133)...")
    cursor.execute("""
        INSERT INTO gastos_tipos (id, cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave)
        VALUES (133, 'JOR', 'ESCO Jorge', 'EGRESO', '💸', 'rgba(244, 114, 182, 0.2); color: #f472b6', 'ESCO')
    """)

# Re-apply keyword updates for category cleanups
print("Applying keyword cleanups...")
cursor.execute("UPDATE gastos_tipos SET palabras_clave = 'MUN PT MADRYN, AFIP 931, IIBB, SIRCREB, ARBA, PAGO IVA' WHERE id = 55")
cursor.execute("UPDATE gastos_tipos SET palabras_clave = 'TRANSFERENCIA DE TERCEROS NICOLETTI JOAQUIN' WHERE id = 61")
cursor.execute("UPDATE gastos_tipos SET palabras_clave = 'COOP, EMSRL' WHERE id = 117")
cursor.execute("UPDATE gastos_tipos SET palabras_clave = 'RED UNO' WHERE id = 73")

# Set the cheapest ESCO record (monto = 102450.0) to JOR (ESCO Jorge, id 133)
print("Manually classifying the cheapest ESCO record to JOR...")
cursor.execute("""
    UPDATE gastos_registros
    SET gasto_tipo_id = 133
    WHERE descripcion LIKE '%ESCO%' AND monto = 102450.0
""")

# Ensure the other ESCO records are COMUN / ESCO (id 132)
# Check if id 132 category exists, if not create it
cursor.execute("SELECT id FROM gastos_tipos WHERE id = 132")
has_132 = cursor.fetchone()
if not has_132:
    print("Re-creating 'ESCO' category under COMUN (id 132)...")
    cursor.execute("""
        INSERT INTO gastos_tipos (id, cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave)
        VALUES (132, 'COMUN', 'ESCO', 'EGRESO', '💸', 'rgba(234, 179, 8, 0.2); color: #eab308', 'ESCO')
    """)

print("Manually classifying other ESCO records to COMUN...")
cursor.execute("""
    UPDATE gastos_registros
    SET gasto_tipo_id = 132
    WHERE descripcion LIKE '%ESCO%' AND monto IN (111515.0, 206165.0)
""")

conn.commit()
conn.close()
print("Database successfully restored and migrated.")
