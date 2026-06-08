import sqlite3

conn = sqlite3.connect('erp_nicoletti.db')
cursor = conn.cursor()

print("=== CLEANING OVERLY GENERIC KEYWORDS ===")

# Update Impuestos Comerciales (id 55): remove 'IVA', replace with 'AFIP IVA' or keep the rest
cursor.execute("""
    UPDATE gastos_tipos 
    SET palabras_clave = 'MUN PT MADRYN, AFIP 931, IIBB, SIRCREB, ARBA, PAGO IVA' 
    WHERE id = 55
""")
print(f"Updated Impuestos Comerciales (id 55). Rows affected: {cursor.rowcount}")

# Update Aportes de Capital (id 61): remove CUIT '20353824199'
cursor.execute("""
    UPDATE gastos_tipos 
    SET palabras_clave = 'TRANSFERENCIA DE TERCEROS NICOLETTI JOAQUIN' 
    WHERE id = 61
""")
print(f"Updated Aportes de Capital (id 61). Rows affected: {cursor.rowcount}")

# Update Depa Procrear (id 117): remove 'RED'
cursor.execute("""
    UPDATE gastos_tipos 
    SET palabras_clave = 'COOP, EMSRL' 
    WHERE id = 117
""")
print(f"Updated Depa Procrear (id 117). Rows affected: {cursor.rowcount}")

# Update COMUN / Red Uno (id 73): remove 'RED'
cursor.execute("""
    UPDATE gastos_tipos 
    SET palabras_clave = 'RED UNO' 
    WHERE id = 73
""")
print(f"Updated COMUN / Red Uno (id 73). Rows affected: {cursor.rowcount}")

conn.commit()
conn.close()
print("Database keywords cleaned successfully.")
