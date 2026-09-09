import sqlite3
import json

db = sqlite3.connect('erp_nicoletti.db')
db.row_factory = sqlite3.Row

print("=== MUESTRA DE MOVIMIENTOS BANCARIOS CON RAW_INGESTA_ID = 66 ===")
sample = db.execute("""
    SELECT id, banco, cuenta, fecha, descripcion, tipo_movimiento, importe, saldo, path_archivo, hash_archivo, raw_ingesta_id
    FROM bancos_movimientos
    WHERE raw_ingesta_id = 66
    LIMIT 5
""").fetchall()
for s in sample:
    print(dict(s))

print("\n=== VERIFICAR SI EXISTE EL HASH EN core_staging_raw ===")
h = sample[0]['hash_archivo']
path = sample[0]['path_archivo']
print(f"Buscando por hash {h} o path {path}:")
raw_match = db.execute("SELECT * FROM core_staging_raw WHERE sha256 = ? OR path_archivo LIKE ?", (h, f"%{path}%")).fetchall()
print(f"Coincidencias en core_staging_raw: {len(raw_match)}")
for rm in raw_match:
    print(dict(rm))

print("\n=== COMPRAS FACTURAS SIN RAW ===")
sample_fac = db.execute("""
    SELECT id, emisor, numero_factura, fecha_emision, importe_total, origen, raw_ingesta_id
    FROM compras_facturas
    WHERE raw_ingesta_id IS NULL
    LIMIT 5
""").fetchall()
for sf in sample_fac:
    print(dict(sf))

origs = db.execute("SELECT origen, count(*) FROM compras_facturas GROUP BY origen").fetchall()
print("Distribución total compras_facturas por origen:")
for o in origs:
    print(f"  - {o[0]}: {o[1]} filas")

print("\n=== ANÁLISIS DE TABLAS OBSOLETAS O PARALELAS ===")
# Ver tarjetas_liquidaciones vs tarjetas_payway_movimientos / tarjetas_patagonia_liquidaciones
t_liq = db.execute("SELECT count(*) FROM tarjetas_liquidaciones").fetchone()[0]
t_liq_det = db.execute("SELECT count(*) FROM tarjetas_liquidaciones_detalles").fetchone()[0]
t_payway_old = db.execute("SELECT count(*) FROM tarjetas_payway").fetchone()[0]
t_payway_mov = db.execute("SELECT count(*) FROM tarjetas_payway_movimientos").fetchone()[0]
t_payway_res = db.execute("SELECT count(*) FROM tarjetas_payway_resumenes").fetchone()[0]

print(f"tarjetas_liquidaciones: {t_liq}")
print(f"tarjetas_liquidaciones_detalles: {t_liq_det}")
print(f"tarjetas_payway (legacy): {t_payway_old}")
print(f"tarjetas_payway_movimientos (nuevo ELT): {t_payway_mov}")
print(f"tarjetas_payway_resumenes (nuevo ELT): {t_payway_res}")

db.close()
