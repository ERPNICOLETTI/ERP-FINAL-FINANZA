import sqlite3
import os

db_path = r'c:\Users\Usuario\OneDrive\Documentos\ERP_NICOLETTI\erp_nicoletti.db'

def migrate():
    if not os.path.exists(db_path):
        print("DB not found at", db_path)
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Update entity names
    cursor.execute("UPDATE transactions SET entity = 'Lo de Karlota' WHERE entity = 'karlota'")
    
    print(f"Filas actualizadas: {cursor.rowcount}")
    
    conn.commit()
    conn.close()
    print("Migración de 'karlota' a 'Lo de Karlota' completada con éxito.")

if __name__ == "__main__":
    migrate()
