import sqlite3

db = sqlite3.connect('erp_nicoletti.db')
db.row_factory = sqlite3.Row

cols_fac = [c[1] for c in db.execute("PRAGMA table_info(compras_facturas)").fetchall()]
print("Columnas compras_facturas:", cols_fac)

dup_fac = db.execute("""
    SELECT cuit_emisor, punto_venta, numero_comprobante, tipo_comprobante, count(*), group_concat(id), group_concat(origen), group_concat(estado)
    FROM compras_facturas
    GROUP BY cuit_emisor, punto_venta, numero_comprobante, tipo_comprobante
    HAVING count(*) > 1
""").fetchall()
print(f"\nFacturas con mismo comprobante y emisor: {len(dup_fac)}")
for df in dup_fac[:10]:
    print(f"  CUIT={df[0]}, PV-Num={df[1]}-{df[2]}, Tipo={df[3]}, Cant={df[4]}, IDs={df[5]}, Orígenes={df[6]}, Estados={df[7]}")

db.close()
