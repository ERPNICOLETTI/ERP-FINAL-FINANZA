import sqlite3

DB_PATH = 'erp_nicoletti.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. Update JOA's category ID 87 from 'Tarjeta' to 'Gasto Tarjeta'
    cur.execute("""
        UPDATE gastos_tipos 
        SET nombre = 'Gasto Tarjeta', 
            palabras_clave = 'IMPUESTO DE SELLOS, MANTENIMIENTO, COMISION, IVA COMISIONES, SELLADOS'
        WHERE id = 87
    """)
    if cur.rowcount > 0:
        print("Actualizado concepto JOA Tarjeta -> Gasto Tarjeta (ID 87)")
    else:
        # Fallback if ID is different
        cur.execute("""
            UPDATE gastos_tipos 
            SET nombre = 'Gasto Tarjeta', 
                palabras_clave = 'IMPUESTO DE SELLOS, MANTENIMIENTO, COMISION, IVA COMISIONES, SELLADOS'
            WHERE cuenta_codigo = 'JOA' AND nombre = 'Tarjeta'
        """)
        print("Actualizado concepto JOA Tarjeta -> Gasto Tarjeta por nombre")
        
    # 2. Insert JOA 'Intereses Tarjeta' if not exists
    cur.execute("""
        INSERT OR IGNORE INTO gastos_tipos (cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave)
        VALUES ('JOA', 'Intereses Tarjeta', 'EGRESO', '📉', 'rgba(56, 189, 248, 0.2); color: #38bdf8', 
                'INTERESES FINANCIACION, INTERES POR MORA, DB IVA, IVA RG, DB.RG, INTERESES PUNITORIOS')
    """)
    print("Insertado (OR IGNORE) JOA Intereses Tarjeta")

    # 3. Insert JOR 'Gasto Tarjeta' if not exists
    cur.execute("""
        INSERT OR IGNORE INTO gastos_tipos (cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave)
        VALUES ('JOR', 'Gasto Tarjeta', 'EGRESO', '💳', 'rgba(244, 114, 182, 0.2); color: #f472b6', 
                'COMISION SERVICIO MENSUAL, IVA COMISIONES, SELLADOS, COMISION POR MANTENIMIENTO, IMPUESTO DE SELLOS, COMISION POR AVISOS, CARGO POR GESTION, IVA Operaciones, *COMISION, *CARGO')
    """)
    print("Insertado (OR IGNORE) JOR Gasto Tarjeta")

    # 4. Insert JOR 'Intereses Tarjeta' if not exists
    cur.execute("""
        INSERT OR IGNORE INTO gastos_tipos (cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave)
        VALUES ('JOR', 'Intereses Tarjeta', 'EGRESO', '📉', 'rgba(244, 114, 182, 0.2); color: #f472b6', 
                'INTERESES FINANCIACION, INTERESES PUNITORIOS, INTERES POR MORA')
    """)
    print("Insertado (OR IGNORE) JOR Intereses Tarjeta")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    main()
