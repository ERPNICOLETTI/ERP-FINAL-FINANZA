import sqlite3
import json

db = sqlite3.connect('erp_nicoletti.db')
db.row_factory = sqlite3.Row

print("=== 1. TABLAS Y CANTIDAD DE REGISTROS ===")
tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
for t in tables:
    count = db.execute(f"SELECT count(*) FROM [{t}]").fetchone()[0]
    print(f"  - {t}: {count} filas")

print("\n=== 2. CHEQUEO DE FOREIGN KEYS (PRAGMA foreign_key_check) ===")
fks = db.execute("PRAGMA foreign_key_check").fetchall()
print(f"Total violaciones FK: {len(fks)}")
fks_by_table = {}
for fk in fks:
    tname = fk[0]
    fks_by_table[tname] = fks_by_table.get(tname, 0) + 1
for tname, cnt in fks_by_table.items():
    print(f"  - {tname}: {cnt} violaciones")
    sample = db.execute(f"PRAGMA foreign_key_check([{tname}])").fetchmany(3)
    for s in sample:
        print(f"     detalle muestra: rowid={s[1]}, target_table={s[2]}, fkid={s[3]}")

print("\n=== 3. TRAZABILIDAD RAW -> PRODUCCIÓN (raw_ingesta_id) ===")
for t in tables:
    cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])").fetchall()]
    if 'raw_ingesta_id' in cols:
        total = db.execute(f"SELECT count(*) FROM [{t}]").fetchone()[0]
        con_raw = db.execute(f"SELECT count(*) FROM [{t}] WHERE raw_ingesta_id IS NOT NULL").fetchone()[0]
        sin_raw = db.execute(f"SELECT count(*) FROM [{t}] WHERE raw_ingesta_id IS NULL").fetchone()[0]
        huerfanos = db.execute(f"SELECT count(*) FROM [{t}] WHERE raw_ingesta_id IS NOT NULL AND raw_ingesta_id NOT IN (SELECT id FROM core_staging_raw)").fetchone()[0]
        print(f"  - {t}: total={total} | con_raw={con_raw} | sin_raw={sin_raw} | raw_huerfano={huerfanos}")

print("\n=== 4. REVISIÓN DE MOVIMIENTOS BANCARIOS HUÉRFANOS ===")
if 'bancos_movimientos' in tables:
    res = db.execute("""
        SELECT banco, fecha_movimiento, count(*), min(id), max(id), min(raw_ingesta_id), max(raw_ingesta_id)
        FROM bancos_movimientos
        WHERE raw_ingesta_id NOT IN (SELECT id FROM core_staging_raw)
        GROUP BY banco, substr(fecha_movimiento, 1, 7)
    """).fetchall()
    print("Movimientos bancarios con raw_ingesta_id inexistente en core_staging_raw:")
    for r in res:
        print(f"  Banco={r[0]}, Mes={r[1]}, Cant={r[2]}, IDs=[{r[3]}..{r[4]}], RAWs=[{r[5]}..{r[6]}]")

print("\n=== 5. TABLAS DE LIQUIDACIONES / TARJETAS HUÉRFANAS O REPETIDAS ===")
for t in tables:
    if 'tarjeta' in t or 'payway' in t or 'liq' in t:
        cnt = db.execute(f"SELECT count(*) FROM [{t}]").fetchone()[0]
        print(f"  - {t}: {cnt} filas")

db.close()
