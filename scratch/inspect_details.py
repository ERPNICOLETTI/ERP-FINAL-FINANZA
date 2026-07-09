import sqlite3
import sys
import io

# Asegurar codificación utf-8 en consola de Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def inspect_details():
    conn = sqlite3.connect('erp_nicoletti.db')
    cursor = conn.cursor()
    
    print("=== CUENTAS MAESTRAS ===")
    cursor.execute("SELECT * FROM cuentas_maestras")
    for row in cursor.fetchall():
        print(row)
        
    print("\n=== GASTOS CUENTAS ===")
    cursor.execute("SELECT * FROM gastos_cuentas")
    for row in cursor.fetchall():
        print(row)
        
    print("\n=== CATEGORIAS MAESTRAS (primeras 5) ===")
    cursor.execute("SELECT * FROM categorias_maestras LIMIT 5")
    for row in cursor.fetchall():
        print(row)
        
    print("\n=== GASTOS TIPOS (primeras 5) ===")
    cursor.execute("SELECT * FROM gastos_tipos LIMIT 5")
    for row in cursor.fetchall():
        print(row)
        
    conn.close()

if __name__ == "__main__":
    inspect_details()
