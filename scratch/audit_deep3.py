import sqlite3
import json

db = sqlite3.connect('erp_nicoletti.db')
db.row_factory = sqlite3.Row

print("Columnas core_staging_raw:", [c[1] for c in db.execute("PRAGMA table_info(core_staging_raw)").fetchall()])

print("\n=== RAW_INGESTA_ID 66 EN core_staging_raw ===")
r66 = db.execute("SELECT * FROM core_staging_raw WHERE id = 66").fetchone()
print("ID 66 en core_staging_raw:", dict(r66) if r66 else "NO EXISTE")

print("\n=== LISTA DE IDs EN core_staging_raw (MIN, MAX, COUNT) ===")
print("core_staging_raw id range:", db.execute("SELECT min(id), max(id), count(*) FROM core_staging_raw").fetchone())

print("\n=== ORIGEN DE COMPRAS_FACTURAS ===")
origs = db.execute("SELECT origen, raw_ingesta_id IS NOT NULL, count(*) FROM compras_facturas GROUP BY origen, raw_ingesta_id IS NOT NULL").fetchall()
for o in origs:
    print(f"  Origen={o[0]} | Tiene RAW={bool(o[1])} | Cant={o[2]}")

print("\n=== BANCOS_MOVIMIENTOS: CANTIDAD POR BANCO Y RAW_INGESTA_ID ===")
bancos_raw = db.execute("SELECT banco, raw_ingesta_id, count(*) FROM bancos_movimientos GROUP BY banco, raw_ingesta_id").fetchall()
for br in bancos_raw:
    print(f"  Banco={br[0]} | RAW_ID={br[1]} | Cant={br[2]}")

db.close()
