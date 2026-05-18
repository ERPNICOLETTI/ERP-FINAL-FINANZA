import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')

def auditar_tablas():
    if not os.path.exists(DB_PATH):
        print("❌ No se encontró erp_nicoletti.db")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tablas = cursor.fetchall()
    
    print("\nTABLAS ACTUALES EN ERP_NICOLETTI.DB:")
    print("-" * 40)
    for t in tablas:
        print(f"- {t[0]}")
    print("-" * 40)
    print(f"Total: {len(tablas)} tablas encontradas.\n")
    conn.close()

if __name__ == "__main__":
    auditar_tablas()
