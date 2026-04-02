import sqlite3
import pandas as pd

def check_discrepancias():
    conn = sqlite3.connect('erp_nicoletti.db')
    print("\n" + "="*60)
    print(" REPORTE DE DISCREPANCIAS: AFIP VS CALIM")
    print("="*60)
    
    # Buscar facturas que están en el sistema (importadas de AFIP o manual) pero no en CALIM
    query = """
    SELECT numero_completo, proveedor, fecha_emision, monto_total 
    FROM facturas 
    WHERE tipo_operacion = 'COMPRA' 
      AND (esta_en_calim = 0 OR esta_en_calim IS NULL)
    ORDER BY fecha_emision DESC
    """
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        print("¡Excelente! No hay facturas pendientes de subir a CALIM.")
    else:
        print(f"Detectadas {len(df)} facturas pendientes de subir al contador:")
        print("-" * 60)
        for _, row in df.iterrows():
            print(f"[-] {row['fecha_emision']} | {row['numero_completo']} | {row['proveedor'][:20]:<20} | ${row['monto_total']:>10,.2f}")
    
    conn.close()

if __name__ == "__main__":
    check_discrepancias()
