import sqlite3
import os
import pandas as pd

def listar_sueldos(db_path):
    print(f"💎 ESCANEANDO SUELDOS (HABERES) - BANCO HIPOTECARIO (ÁREA JOAQUÍN)...")
    
    conn = sqlite3.connect(db_path)
    # Filtramos por "SUELDOS" o "PINO SUB SA" que detectamos antes
    query = """
        SELECT fecha, descripcion, importe 
        FROM bancos_movimientos 
        WHERE banco = 'HIPOTECARIO' 
        AND (descripcion LIKE '%SUELDOS%' OR descripcion LIKE '%PINO SUB SA%')
        ORDER BY substr(fecha, 7, 4) DESC, substr(fecha, 4, 2) DESC, substr(fecha, 1, 2) DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("❌ No se encontraron movimientos con 'SUELDOS' o 'PINO SUB SA'.")
    else:
        # Formatear para que se vea bien la tabla
        pd.options.display.max_rows = 100
        print(df.to_string(index=False))
        print(f"\n✅ Total de sueldos detectados: {len(df)}")
        print(f"💰 Suma total de sueldos: $ {df['importe'].sum():,.2f}")

if __name__ == "__main__":
    WORKSPACE = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(WORKSPACE, "erp_nicoletti.db")
    listar_sueldos(DB_PATH)
