import sqlite3

db = sqlite3.connect('erp_nicoletti.db')
db.row_factory = sqlite3.Row

print("=== 1. TABLAS VACÍAS ===")
tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
empty_tables = []
for t in tables:
    cnt = db.execute(f"SELECT count(*) FROM [{t}]").fetchone()[0]
    if cnt == 0:
        empty_tables.append(t)
        print(f"  - {t}: 0 filas")

print("\n=== 2. TABLAS FTS / ÍNDICES DE BÚSQUEDA ===")
fts_tables = [t for t in tables if t.startswith('search_index')]
print(f"FTS tables: {fts_tables}")

print("\n=== 3. FK VIOLATIONS DETALLE ===")
# 75 violaciones en tarjetas_liquidaciones_detalles
huerfanos_liq = db.execute("""
    SELECT distinct liquidacion_id 
    FROM tarjetas_liquidaciones_detalles 
    WHERE liquidacion_id NOT IN (SELECT id FROM tarjetas_liquidaciones)
""").fetchall()
print("Liquidacion_ids en detalles que no existen en tarjetas_liquidaciones:")
for h in huerfanos_liq:
    print(f"  ID={h[0]}")

# 1 violación en core_staging_logs
huerfano_log = db.execute("""
    SELECT id, raw_ingesta_id, mensaje, nivel, created_at 
    FROM core_staging_logs 
    WHERE raw_ingesta_id NOT IN (SELECT id FROM core_staging_raw)
""").fetchall()
print("\nLogs huérfanos de core_staging_raw:")
for hl in huerfano_log:
    print(dict(hl))

print("\n=== 4. DUPLICADOS SEMÁNTICOS O EXACTOS ===")
# Duplicados en compras_facturas
dup_fac = db.execute("""
    SELECT emisor, numero_factura, tipo_comprobante, count(*), group_concat(id), group_concat(origen)
    FROM compras_facturas
    GROUP BY emisor, numero_factura, tipo_comprobante
    HAVING count(*) > 1
""").fetchall()
print(f"Facturas con mismo emisor/numero/tipo: {len(dup_fac)}")
for df in dup_fac[:10]:
    print(f"  Emisor={df[0]}, Num={df[1]}, Cant={df[3]}, IDs={df[4]}, Orígenes={df[5]}")

# Duplicados en bancos_movimientos (mismo banco, cuenta, fecha, importe_centavos, descripcion)
dup_bancos = db.execute("""
    SELECT banco, cuenta, fecha, importe_centavos, descripcion, count(*), group_concat(id)
    FROM bancos_movimientos
    GROUP BY banco, cuenta, fecha, importe_centavos, descripcion
    HAVING count(*) > 1
""").fetchall()
print(f"\nMovimientos bancarios con misma firma exacta (banco, fecha, importe, descripcion): {len(dup_bancos)}")
for dbm in dup_bancos[:10]:
    print(f"  Banco={dbm[0]}, Fecha={dbm[2]}, Importe={dbm[3]}, IDs={dbm[5]}, Desc={dbm[4][:40]}")

# Ver si son gemelos legítimos (ej. RED UNO)
for dbm in dup_bancos[:5]:
    ids_list = dbm[5].split(',')
    rows = db.execute(f"SELECT id, numero_linea, raw_ingesta_id, saldo FROM bancos_movimientos WHERE id IN ({','.join(ids_list)})").fetchall()
    print(f"   Detalle gemelos {dbm[5]}: {[dict(r) for r in rows]}")

db.close()
