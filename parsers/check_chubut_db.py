import sqlite3
conn = sqlite3.connect('erp_nicoletti.db')
cursor = conn.cursor()
cursor.execute("SELECT id, amount, desc FROM transactions WHERE account = 'Caja de Ahorro Chubut' AND category = 'Importación Automática'")
rows = cursor.fetchall()
print(f"Total: {len(rows)}")
for r in rows[:10]:
    print(r)
conn.close()
