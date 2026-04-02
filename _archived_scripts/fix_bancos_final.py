import sqlite3
import os

def fix_bancos_final():
    db_path = "erp_nicoletti.db"
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Reparamos el desvío de Credicoop
    cur.execute("""
        UPDATE bancos_movimientos 
        SET banco = 'CREDICOOP' 
        WHERE (descripcion LIKE '%27329549971%' OR descripcion LIKE '%DOMINGUEZ JORGELINA%')
           OR (banco = 'HIPOTECARIO' AND descripcion LIKE '%Transf.Inmediata%')
    """)
    rows_credicoop = cur.rowcount

    conn.commit()
    
    # Resumen Final
    cur.execute("SELECT banco, COUNT(*) FROM bancos_movimientos GROUP BY banco")
    resumen = cur.fetchall()
    conn.close()
    
    print("-" * 30)
    print("📋 RESUMEN FINAL POR BANCO:")
    for r in resumen:
        print(f"🏛️ BANCO: {r[0]:<12} | MOVIMIENTOS: {r[1]}")
    print("-" * 30)

if __name__ == "__main__":
    fix_bancos_final()
