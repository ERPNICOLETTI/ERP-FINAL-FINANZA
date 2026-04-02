import sqlite3
import os
import pandas as pd

def listar_haberes(db_path):
    print(f"💎 ESCANEANDO HABERES (INGRESOS) - BANCO HIPOTECARIO (ÁREA JOAQUÍN)...")
    
    conn = sqlite3.connect(db_path)
    # Seleccionamos movimientos positivos (Importe > 0)
    query = """
        SELECT fecha, descripcion, importe 
        FROM bancos_movimientos 
        WHERE banco = 'HIPOTECARIO' AND importe > 0 
        ORDER BY fecha DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("❌ No se encontraron haberes registrados.")
    else:
        print(df.to_string(index=False))
        print(f"\n✅ Total de ingresos detectados: {len(df)}")
        print(f"💰 Suma total de haberes: $ {df['importe'].sum():,.2f}")

if __name__ == "__main__":
    WORKSPACE = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(WORKSPACE, "erp_nicoletti.db")
    listar_haberes(DB_PATH)
