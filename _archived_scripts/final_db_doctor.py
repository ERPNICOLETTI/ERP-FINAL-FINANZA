import sqlite3
import os

def final_db_doctor():
    print(f"🧙‍♂️ [DB DOCTOR] INICIANDO SANEAMIENTO PROFUNDO...")
    
    db_path = "erp_nicoletti.db"
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Borrar ruido de Texto Bancario y "NaN"
    cur.execute("""
        DELETE FROM bancos_movimientos 
        WHERE descripcion IS NULL 
           OR descripcion LIKE '%El presente documento%' 
           OR descripcion LIKE '%El resumen correspondiente%'
           OR descripcion LIKE '%nan%'
    """)
    rows_ruido = cur.rowcount
    
    # 2. Corregir registros sin Banco o Cuenta
    cur.execute("UPDATE bancos_movimientos SET banco = 'HIPOTECARIO' WHERE banco IS NULL")
    cur.execute("UPDATE bancos_movimientos SET cuenta = 'CA_JOAQUIN' WHERE banco = 'HIPOTECARIO' AND (cuenta IS NULL OR cuenta = 'None')")
    
    # 3. Eliminar movimientos con Monto Cero (No nos interesan para auditoría financiera)
    cur.execute("DELETE FROM bancos_movimientos WHERE importe = 0")
    rows_cero = cur.rowcount

    conn.commit()
    
    # --- RESUMEN FINAL DE ESTADO DE SALUD ---
    print(f"✅ Se eliminaron {rows_ruido} filas de RUIDO/LEGALES.")
    print(f"✅ Se eliminaron {rows_cero} filas con IMPORTE CERO.")
    
    cur.execute("SELECT banco, cuenta, COUNT(*) FROM bancos_movimientos GROUP BY banco, cuenta")
    resumen = cur.fetchall()
    
    print("-" * 40)
    print("📊 BASE DE DATOS SANEADA Y LISTA:")
    for r in resumen:
        print(f"🏦 BANCO: {str(r[0]):<12} | CUENTA: {str(r[1]):<16} | TOTAL: {r[2]} MOV.")
    print("-" * 40)
    
    conn.close()

if __name__ == "__main__":
    final_db_doctor()
