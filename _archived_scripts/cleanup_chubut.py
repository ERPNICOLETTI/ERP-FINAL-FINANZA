import sqlite3
conn = sqlite3.connect('erp_nicoletti.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM transactions WHERE account = 'Caja de Ahorro Chubut' AND category = 'Importación Automática'")
deleted = cursor.rowcount
conn.commit()
print(f"Borrados {deleted} movimientos erróneos de Chubut.")
conn.close()
