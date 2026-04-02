import sqlite3
import os

def audit_full_db():
    print(f"🕵️‍♂️ [AUDITORÍA FORENSE] ESCANEANDO CONTENIDO REAL DE erp_nicoletti.db...")
    
    db_path = "erp_nicoletti.db"
    if not os.path.exists(db_path):
        print("❌ No se encontró la base de datos.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Obtenemos todas las tablas
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cur.fetchall()]
    
    print("-" * 50)
    print(f"{'TABLA':<25} | {'REGISTROS':<10}")
    print("-" * 50)
    
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"{table:<25} | {count:<10}")
        except Exception as e:
            print(f"{table:<25} | ERROR: {e}")

    print("-" * 50)
    
    # 2. Detalles específicos de AFIP/CALIM
    try:
        cur.execute("SELECT tipo, COUNT(*) FROM comprobantes_afip GROUP BY tipo")
        tipos = cur.fetchall()
        print("\n📂 DETALLE DE FACTURAS (AFIP/CALIM):")
        for t in tipos:
            print(f"   -> {t[0]}: {t[1]} registros")
    except:
        print("\n❌ No se pudo leer el detalle de comprobantes_afip.")

    # 3. Detalles de Payway
    try:
        cur.execute("SELECT COUNT(*) FROM liquidaciones_tarjetas")
        count = cur.fetchone()[0]
        print(f"\n📂 DETALLE DE RECAUDACIÓN (PAYWAY): {count} registros")
    except:
        pass

    conn.close()

if __name__ == "__main__":
    audit_full_db()
