import sqlite3
import sys
import io
from modulo_pagos.lectores.lector_pagos import procesar_pago

# Asegurar codificación utf-8 en consola
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('erp_nicoletti.db')
cursor = conn.cursor()

cursor.execute("SELECT id, nombre_archivo, contenido_raw FROM core_staging_raw")
for row in cursor.fetchall():
    rid, name, content = row
    ok, info = procesar_pago(text_content=content)
    print(f"ID: {rid} | Archivo: {name}")
    print(f"   Parser OK: {ok}")
    if ok:
        print(f"   Concepto: {info['concepto']}")
        print(f"   Periodo: {info['periodo_mes']}/{info['periodo_anio']}")
        print(f"   Monto 1: {info['monto']} | Monto 2: {info['monto_2']}")
        print(f"   Barras: {info['codigo_barras']}")
    else:
        print(f"   Error parsing.")
    print("-" * 50)
conn.close()
