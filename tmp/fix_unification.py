import sqlite3

conn = sqlite3.connect('erp_nicoletti.db')

# 1. Migrar a tabla nueva con UNIQUE en numero_completo solo
conn.execute('DROP TABLE IF EXISTS facturas_new')
conn.execute('''CREATE TABLE facturas_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_completo TEXT UNIQUE,
    tipo_comprobante TEXT,
    proveedor TEXT,
    fecha_emision TEXT,
    neto_gravado REAL,
    monto_iva REAL,
    monto_total REAL,
    esta_en_afip INTEGER DEFAULT 0,
    esta_en_calim INTEGER DEFAULT 0,
    estado_proceso TEXT DEFAULT 'PENDIENTE',
    ruta_archivo TEXT
)''')

# 2. Unificar los registros del backup
# Primero insertamos los de CALIM (tienen el CUIT en el proveedor, son más completos)
conn.execute('''INSERT OR IGNORE INTO facturas_new 
    (numero_completo, tipo_comprobante, proveedor, fecha_emision, neto_gravado, monto_iva, monto_total, esta_en_afip, esta_en_calim, estado_proceso, ruta_archivo)
    SELECT numero_completo, tipo_comprobante, proveedor, fecha_emision, neto_gravado, monto_iva, monto_total, esta_en_afip, esta_en_calim, estado_proceso, ruta_archivo
    FROM facturas_bak WHERE esta_en_calim = 1
''')

# 3. Luego hacemos UPDATE para los de ARCA: si el número ya existe (de CALIM), solo actualizamos la bandera esta_en_afip
conn.execute('''INSERT INTO facturas_new 
    (numero_completo, tipo_comprobante, proveedor, fecha_emision, neto_gravado, monto_iva, monto_total, esta_en_afip, esta_en_calim, estado_proceso, ruta_archivo)
    SELECT numero_completo, tipo_comprobante, proveedor, fecha_emision, neto_gravado, monto_iva, monto_total, esta_en_afip, esta_en_calim, estado_proceso, ruta_archivo
    FROM facturas_bak WHERE esta_en_afip = 1
    ON CONFLICT(numero_completo) DO UPDATE SET
        esta_en_afip = 1
''')

# 4. Reemplazar tablas
conn.execute('DROP TABLE facturas')
conn.execute('ALTER TABLE facturas_new RENAME TO facturas')
conn.commit()

# 5. Verificar resultado
total = conn.execute('SELECT count(*) FROM facturas').fetchone()[0]
ambos = conn.execute('SELECT count(*) FROM facturas WHERE esta_en_afip=1 AND esta_en_calim=1').fetchone()[0]
solo_arca = conn.execute('SELECT count(*) FROM facturas WHERE esta_en_afip=1 AND esta_en_calim=0').fetchone()[0]
solo_calim = conn.execute('SELECT count(*) FROM facturas WHERE esta_en_afip=0 AND esta_en_calim=1').fetchone()[0]

print(f"Total: {total}")
print(f"En AMBOS (ARCA + CALIM): {ambos}")
print(f"Solo ARCA: {solo_arca}")
print(f"Solo CALIM: {solo_calim}")

conn.close()
