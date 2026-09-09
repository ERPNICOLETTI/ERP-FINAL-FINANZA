import sqlite3

db = sqlite3.connect('erp_nicoletti.db')
db.row_factory = sqlite3.Row

print("Columnas core_staging_logs:", [c[1] for c in db.execute("PRAGMA table_info(core_staging_logs)").fetchall()])

# FK check en core_staging_logs
fks_logs = db.execute("PRAGMA foreign_key_check(core_staging_logs)").fetchall()
print("FK check core_staging_logs:", [dict(f) for f in fks_logs])
for fl in fks_logs:
    row = db.execute(f"SELECT * FROM core_staging_logs WHERE rowid = {fl['rowid']}").fetchone()
    print("Fila infractora en core_staging_logs:", dict(row))

# Ver duplicados en compras_facturas
dup_fac = db.execute("""
    SELECT emisor, numero_factura, tipo_comprobante, count(*), group_concat(id), group_concat(origen)
    FROM compras_facturas
    GROUP BY emisor, numero_factura, tipo_comprobante
    HAVING count(*) > 1
""").fetchall()
print(f"\nFacturas con mismo emisor/numero/tipo: {len(dup_fac)}")
for df in dup_fac[:10]:
    print(f"  Emisor={df[0]}, Num={df[1]}, Cant={df[3]}, IDs={df[4]}, Orígenes={df[5]}")

# Ver duplicados en bancos_movimientos
dup_bancos = db.execute("""
    SELECT banco, cuenta, fecha, importe_centavos, descripcion, count(*), group_concat(id)
    FROM bancos_movimientos
    GROUP BY banco, cuenta, fecha, importe_centavos, descripcion
    HAVING count(*) > 1
""").fetchall()
print(f"\nMovimientos bancarios con misma firma exacta: {len(dup_bancos)}")
for dbm in dup_bancos[:5]:
    ids_list = dbm[5].split(',')
    rows = db.execute(f"SELECT id, numero_linea, raw_ingesta_id, saldo FROM bancos_movimientos WHERE id IN ({','.join(ids_list)})").fetchall()
    print(f"   Detalle gemelos IDs {dbm[5]}: {[dict(r) for r in rows]}")

db.close()
