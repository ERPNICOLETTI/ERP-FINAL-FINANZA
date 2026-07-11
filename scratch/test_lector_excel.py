import os
import sqlite3
import sys

# Asegurar que la raíz del proyecto esté en el PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core_sistema.lector_excel import LectorExcelUniversal, calcular_hash_archivo

db_path = "excel_staging.db"

# Asegurar que empezamos con una DB limpia para el test
if os.path.exists(db_path):
    os.remove(db_path)

lector = LectorExcelUniversal(db_path)

print("🧪 Probando saneamiento contable...")

# 1. Regla de los centavos
monto_centavos = lector.transformar_celda("$ 1,234.56", es_importe=True)
print(f"💵 Entrada: '$ 1,234.56' -> Centavos: {monto_centavos} (Esperado: 123456)")
assert monto_centavos == 123456

monto_centavos_coma = lector.transformar_celda("$ 1.234,56", es_importe=True)
print(f"💵 Entrada: '$ 1.234,56' -> Centavos: {monto_centavos_coma} (Esperado: 123456)")
assert monto_centavos_coma == 123456

# 2. Sanidad de strings
sku_saneado = lector.transformar_celda("   sku-1234-ab    ", es_identificador=True)
print(f"🔍 SKU: '   sku-1234-ab    ' -> Saneado: '{sku_saneado}' (Esperado: 'SKU-1234-AB')")
assert sku_saneado == "SKU-1234-AB"

# 3. Fechas
fecha_saneada = lector.transformar_celda("10/07/2026", es_fecha=True)
print(f"📅 Fecha: '10/07/2026' -> Saneada: '{fecha_saneada}' (Esperado: '2026-07-10')")
assert fecha_saneada == "2026-07-10"

print("\n🚀 Verificando base de datos y esquema...")
conn = sqlite3.connect(db_path)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tablas encontradas en excel_staging.db:", tables)
assert "core_staging_raw" in tables
assert "core_auditoria_errores" in tables
assert "core_discrepancias" in tables
assert "core_historial_archivos" in tables
conn.close()

print("\n🎉 Todas las validaciones unitarias y de base de datos pasaron con éxito en la DB dedicada.")
