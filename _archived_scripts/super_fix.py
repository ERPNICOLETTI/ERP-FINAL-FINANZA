import sqlite3
import os

def super_fix_db():
    print(f"🛠️ [SÚPER FIX] REETIQUETANDO MOVIMIENTOS...")
    
    db_path = "erp_nicoletti.db"
    if not os.path.exists(db_path):
        print("❌ No se encontró la base de datos.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Identificamos movimientos de Credicoop por la descripción del CUIT
    cur.execute("""
        UPDATE bancos_movimientos 
        SET banco = 'CREDICOOP', cuenta = 'CA_JOAQUIN_CRED'
        WHERE descripcion LIKE '%27329549971%' OR descripcion LIKE '%DOMINGUEZ%'
    """)
    rows_credicoop = cur.rowcount
    
    # 2. El resto de Hipotecario (que no sea Credicoop) lo dejamos prolijo
    cur.execute("""
        UPDATE bancos_movimientos 
        SET cuenta = 'CA_JOAQUIN_HIPO'
        WHERE banco = 'HIPOTECARIO' AND banco != 'CREDICOOP'
    """)
    rows_hipo = cur.rowcount

    conn.commit()
    
    # 3. Resumen final para mostrarte
    cur.execute("SELECT banco, COUNT(*) FROM bancos_movimientos GROUP BY banco")
    resumen = cur.fetchall()
    
    conn.close()
    
    print(f"✅ Se corrigieron {rows_credicoop} registros a CREDICOOP.")
    print(f"✅ Se unificaron {rows_hipo} registros de HIPOTECARIO.")
    print("-" * 30)
    for r in resumen:
        print(f"BANCO: {r[0]} | MOVIMIENTOS: {r[1]}")

if __name__ == "__main__":
    super_fix_db()
