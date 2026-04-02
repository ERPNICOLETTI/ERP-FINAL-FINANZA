import sqlite3
import os

def fix_db_entities():
    print(f"🛠️ [CORRECCIÓN] REETIQUETANDO MOVIMIENTOS EN DB...")
    
    db_path = "erp_nicoletti.db"
    if not os.path.exists(db_path):
        print("❌ No se encontró la base de datos.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Movimientos que son claramente de Credicoop (por la descripción del Excel de hoy)
    # Ejemplo: 'Transf.Inmediata e/Ctas.Dist Tit.O/Bco 27329549971-VAR-DOMINGUEZ JORGELINA BE'
    cur.execute("""
        UPDATE bancos_movimientos 
        SET banco = 'CREDICOOP', cuenta = 'CA_JOAQUIN_9087'
        WHERE descripcion LIKE '%27329549971-VAR-DOMINGUEZ JORGELINA BE%'
           OR descripcion LIKE '%Transf.Inmediata%'
    """)
    rows_credicoop = cur.rowcount
    
    # 2. Aseguramos que lo que ya estaba como HIPOTECARIO y es de Joaquín quede bien etiquetado
    cur.execute("""
        UPDATE bancos_movimientos 
        SET cuenta = 'CA_JOAQUIN_9087'
        WHERE banco = 'HIPOTECARIO' AND (descripcion LIKE '%JOAQUIN%' OR descripcion LIKE '%DOMINGUEZ%')
    """)
    rows_hipo = cur.rowcount

    conn.commit()
    conn.close()
    print(f"✅ Se corrigieron {rows_credicoop} registros a CREDICOOP.")
    print(f"✅ Se unificaron {rows_hipo} registros de HIPOTECARIO bajo cuenta JOAQUIN.")

if __name__ == "__main__":
    fix_db_entities()
