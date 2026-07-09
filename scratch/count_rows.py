import sqlite3
import os

DB_PATH = 'erp_nicoletti.db'

def inspect_db():
    if not os.path.exists(DB_PATH):
        print("❌ No database file found.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [r[0] for r in cursor.fetchall()]
    
    print(f"{'TABLA':<32} | {'FILAS':<10} | {'COLUMNAS'}")
    print("-" * 80)
    for table in tables:
        if 'search_index_' in table or table == 'sqlite_sequence':
            continue
        
        # Count rows
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        row_count = cursor.fetchone()[0]
        
        # Get schema columns
        cursor.execute(f'PRAGMA table_info("{table}")')
        cols = [col[1] for col in cursor.fetchall()]
        cols_str = ", ".join(cols)
        
        print(f"{table:<32} | {row_count:<10} | {cols_str}")
        
    conn.close()

if __name__ == "__main__":
    inspect_db()
