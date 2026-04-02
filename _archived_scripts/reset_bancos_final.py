import sqlite3
import os

def reset_bancos_global():
    print(f"🧹 [RESET GLOBAL] LIMPIANDO TODO EL MÓDULO DE BANCOS...")
    
    db_path = "erp_nicoletti.db"
    if not os.path.exists(db_path):
        print("❌ No se encontró la base de datos.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Vaciar la tabla principal de movimientos bancarios
    cur.execute("DELETE FROM bancos_movimientos")
    rows1 = cur.rowcount
    
    # 2. Vaciar la tabla transactions (solo de lo que sea bancos/cuentas)
    # Buscamos patrones comunes de cuentas: CA_, CC_, HIPOTECARIO, CREDICOOP, CHUBUT...
    cur.execute("""
        DELETE FROM transactions 
        WHERE account LIKE 'CA_%' 
           OR account LIKE 'CC_%'
           OR account LIKE '%HIPOTECARIO%'
           OR account LIKE '%CREDICOOP%'
           OR account LIKE '%CHUBUT%'
           OR account LIKE '%JOAQUIN%'
    """)
    rows2 = cur.rowcount

    conn.commit()
    conn.close()
    
    print(f"✅ Se eliminaron {rows1} registros de bancos_movimientos.")
    print(f"✅ Se eliminaron {rows2} registros bancarios de la tabla transactions.")
    print("🚀 EL RESET HA SIDO COMPLETADO. Módulo de bancos vacío.")

if __name__ == "__main__":
    reset_bancos_global()
