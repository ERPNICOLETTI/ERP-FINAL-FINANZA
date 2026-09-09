import sqlite3

db = sqlite3.connect('erp_nicoletti.db')
db.row_factory = sqlite3.Row

print("IDs existentes en core_staging_raw:")
ids = [r['id'] for r in db.execute("SELECT id, nombre_archivo, modulo, tipo_fuente, fecha_ingesta FROM core_staging_raw ORDER BY id").fetchall()]
print(f"Total RAWs: {len(ids)}, Mínimo: {min(ids)}, Máximo: {max(ids)}")
print("Muestra RAWs:", ids[:15], "...", ids[-10:])

# Verificar si hay archivos de Galicia en crudos / storage / staging
print("\nBuscando archivos Galicia en core_staging_raw:")
gal = db.execute("SELECT id, nombre_archivo, modulo, tipo_fuente, fecha_ingesta FROM core_staging_raw WHERE nombre_archivo LIKE '%galicia%' OR contenido_raw LIKE '%GALICIA%'").fetchall()
for g in gal:
    print(dict(g))

print("\nVerificar qué código usa las tablas de liquidaciones viejas:")
db.close()
