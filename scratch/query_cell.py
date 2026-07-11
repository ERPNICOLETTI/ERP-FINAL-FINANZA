import sqlite3
conn = sqlite3.connect('excel_staging.db')
row = conn.execute("SELECT valor_raw, color_hex, color_fuente_hex FROM core_staging_raw WHERE coordenada = 'C894' AND pestana = 'LISTA Y OFERTAS NOV 2025'").fetchone()
conn.close()
if row:
    print(f"VALOR: {row[0]}")
    print(f"COLOR FONDO: {row[1]}")
    print(f"COLOR FUENTE: {row[2]}")
else:
    print("Celda no encontrada")
