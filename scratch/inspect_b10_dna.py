import sqlite3
import json

conn = sqlite3.connect('excel_staging.db')
row = conn.execute("SELECT valor_raw, metadatos_json FROM core_staging_raw WHERE coordenada = 'B10' AND pestana = 'LISTA Y OFERTAS NOV 2025'").fetchone()
conn.close()

if row:
    print(f"VALOR: {row[0]}")
    # Formatear el JSON para mostrarlo hermoso
    parsed_meta = json.loads(row[1])
    print("ADN METADATA JSON:")
    print(json.dumps(parsed_meta, indent=2))
else:
    print("Celda no encontrada")
