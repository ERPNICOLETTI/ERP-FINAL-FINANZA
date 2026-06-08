import sqlite3

DB_PATH = 'erp_nicoletti.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE gastos_registros SET fuente = 'Efectivo' WHERE fuente = 'Manual' OR fuente IS NULL OR fuente = ''")
    conn.commit()
    print(f"Migrados {cur.rowcount} registros de 'Manual' a 'Efectivo'.")
    conn.close()

if __name__ == '__main__':
    main()
