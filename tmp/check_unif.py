import sqlite3
conn = sqlite3.connect('erp_nicoletti.db')

print("=== Registros en AMBOS (ARCA + CALIM) ===")
rows = conn.execute('SELECT numero_completo, proveedor, esta_en_afip, esta_en_calim FROM facturas WHERE esta_en_afip=1 AND esta_en_calim=1 LIMIT 5').fetchall()
print(rows if rows else "NINGUNO encontrado")

print("\n=== Muestra solo ARCA (primeros 5) ===")
rows = conn.execute('SELECT numero_completo, proveedor FROM facturas WHERE esta_en_afip=1 LIMIT 5').fetchall()
for r in rows: print(r)

print("\n=== Muestra solo CALIM (primeros 5) ===")
rows = conn.execute('SELECT numero_completo, proveedor FROM facturas WHERE esta_en_calim=1 LIMIT 5').fetchall()
for r in rows: print(r)

# Buscar si mismos proveedores tienen numeros parecidos en ambas fuentes
print("\n=== Buscando posibles duplicados sin unificar ===")
rows = conn.execute('''
    SELECT a.numero_completo as num_arca, c.numero_completo as num_calim, a.proveedor
    FROM facturas a
    JOIN facturas c ON a.proveedor = c.proveedor AND a.id != c.id
    WHERE a.esta_en_afip=1 AND c.esta_en_calim=1
    LIMIT 10
''').fetchall()
for r in rows: print(r)

conn.close()
