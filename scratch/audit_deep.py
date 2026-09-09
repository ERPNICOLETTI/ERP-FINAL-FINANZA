import sqlite3
import json

db = sqlite3.connect('erp_nicoletti.db')
db.row_factory = sqlite3.Row

print("=== 4. ESTRUCTURA Y MOVIMIENTOS BANCARIOS HUÉRFANOS ===")
cols = [c[1] for c in db.execute("PRAGMA table_info(bancos_movimientos)").fetchall()]
print("Columnas bancos_movimientos:", cols)

res = db.execute("""
    SELECT banco, fecha, count(*), min(id), max(id), min(raw_ingesta_id), max(raw_ingesta_id)
    FROM bancos_movimientos
    WHERE raw_ingesta_id NOT IN (SELECT id FROM core_staging_raw)
    GROUP BY banco, substr(fecha, 1, 7)
""").fetchall()
print("\nMovimientos bancarios con raw_ingesta_id inexistente en core_staging_raw:")
for r in res:
    print(f"  Banco={r[0]}, Mes={r[1]}, Cant={r[2]}, IDs=[{r[3]}..{r[4]}], RAW_IDs=[{r[5]}..{r[6]}]")

# Ver de qué archivo provienen esos 498 registros si tienen path o metadata
sample = db.execute("""
    SELECT id, banco, cuenta, fecha, concepto, debito, credito, saldo, raw_ingesta_id
    FROM bancos_movimientos
    WHERE raw_ingesta_id NOT IN (SELECT id FROM core_staging_raw)
    LIMIT 5
""").fetchall()
print("\nMuestra de movimientos huérfanos:")
for s in sample:
    print(dict(s))

print("\n=== 5. ANÁLISIS DE TARJETAS / LIQUIDACIONES LEGACY vs NUEVAS ===")
print("Tablas de liquidaciones:")
for t in ['tarjetas_liquidaciones', 'tarjetas_liquidaciones_detalles', 'tarjetas_payway', 'tarjetas_payway_movimientos', 'tarjetas_payway_resumenes', 'tarjetas_patagonia_liquidaciones']:
    cnt = db.execute(f"SELECT count(*) FROM [{t}]").fetchone()[0]
    print(f"  {t}: {cnt} filas")

# Ver quién referencia tarjetas_liquidaciones o tarjetas_liquidaciones_detalles en el código
print("\n=== 6. COMPRAS FACTURAS SIN RAW ===")
cnt_sin_raw = db.execute("SELECT count(*) FROM compras_facturas WHERE raw_ingesta_id IS NULL").fetchone()[0]
origenes = db.execute("SELECT origen, count(*) FROM compras_facturas WHERE raw_ingesta_id IS NULL GROUP BY origen").fetchall()
print(f"compras_facturas sin raw_ingesta_id: {cnt_sin_raw}")
for o in origenes:
    print(f"  Origen={o[0]}: {o[1]} filas")

print("\n=== 7. LOGS HUÉRFANOS EN core_staging_logs ===")
log_fk = db.execute("SELECT * FROM core_staging_logs WHERE raw_ingesta_id NOT IN (SELECT id FROM core_staging_raw)").fetchall()
for l in log_fk:
    print(dict(l))

db.close()
