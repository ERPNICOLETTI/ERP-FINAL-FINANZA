import sqlite3
import os

def reset_credicoop():
    print(f"🧹 [REINICIO] LIMPIANDO BANCO CREDICOOP DE LA DB...")
    
    db_path = "erp_nicoletti.db"
    if not os.path.exists(db_path):
        print("❌ No se encontró la base de datos.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Borramos absolutamente TODO lo de CREDICOOP (cualquier etiqueta anterior)
    cur.execute("DELETE FROM bancos_movimientos WHERE banco = 'CREDICOOP'")
    rows_deleted = cur.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"✅ Se borraron {rows_deleted} registros de CREDICOOP.")
    print("🚀 La base de datos está LIMPIA para una nueva ingesta de Credicoop.")

if __name__ == "__main__":
    reset_credicoop()
