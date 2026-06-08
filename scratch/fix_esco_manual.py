import sqlite3

conn = sqlite3.connect('erp_nicoletti.db')
cursor = conn.cursor()

print("=== RESTORING ESCO JORGE CATEGORY AND RECORD ===")

# 1. Re-create the category 'ESCO Jorge' under 'JOR' (id 133)
cursor.execute("""
    INSERT INTO gastos_tipos (id, cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave)
    VALUES (133, 'JOR', 'ESCO Jorge', 'EGRESO', '💸', 'rgba(244, 114, 182, 0.2); color: #f472b6', 'ESCO')
""")
print(f"Re-created 'ESCO Jorge' under JOR. Rows affected: {cursor.rowcount}")

# 2. Find the cheapest ESCO record (monto = 102450.0) and set its gasto_tipo_id to 133
cursor.execute("""
    UPDATE gastos_registros
    SET gasto_tipo_id = 133
    WHERE descripcion LIKE '%ESCO%' AND monto = 102450.0
""")
print(f"Updated cheapest ESCO record to JOR (ESCO Jorge). Rows affected: {cursor.rowcount}")

# 3. Ensure the other two ESCO records are under COMUN / ESCO (id 132)
cursor.execute("""
    UPDATE gastos_registros
    SET gasto_tipo_id = 132
    WHERE descripcion LIKE '%ESCO%' AND monto IN (111515.0, 206165.0)
""")
print(f"Ensured other ESCO records are under COMUN / ESCO. Rows affected: {cursor.rowcount}")

conn.commit()
conn.close()
print("Restoration complete.")
