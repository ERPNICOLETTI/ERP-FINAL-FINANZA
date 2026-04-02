import sqlite3

def reporte_iva_marzo():
    db_path = "erp_nicoletti.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    print("🕵️‍♂️ REPORTE FISCAL DE TARJETAS - MARZO 2026 🕵️‍♂️")
    print("-" * 50)
    
    query = """
    SELECT 
        marca, 
        SUM(total_bruto) as bruto,
        SUM(iva_21) as iva21,
        SUM(iva_105) as iva105,
        SUM(retenciones) as ret
    FROM liquidaciones_tarjetas 
    WHERE periodo = '2026-03'
    GROUP BY marca
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    
    total_iva = 0
    total_ret = 0
    
    for row in rows:
        marca = row[0]
        bruto = row[1]
        iva21 = row[2]
        iva105 = row[3]
        ret = row[4]
        
        suma_iva = iva21 + iva105
        total_iva += suma_iva
        total_ret += ret
        
        print(f"💳 MARCA: {marca}")
        print(f"   Ventas Brutas: $ {bruto:,.2f}")
        print(f"   IVA (21% + 10.5%): $ {suma_iva:,.2f}")
        print(f"   Retenciones AFIP: $ {abs(ret):,.2f}")
        print("-" * 30)
        
    print(f"🔥 TOTAL CRÉDITO FISCAL IVA: $ {total_iva:,.2f}")
    print(f"🔥 TOTAL RETENCIONES A CUENTA: $ {abs(total_ret):,.2f}")
    print("-" * 50)
    
    conn.close()

if __name__ == "__main__":
    reporte_iva_marzo()
