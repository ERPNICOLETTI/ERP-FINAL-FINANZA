import sqlite3
import pandas as pd

conn = sqlite3.connect('erp_nicoletti.db')
periodo = '2026-02'

print(f"=== AUDITORÍA FINAL AL CENTAVO: {periodo} ===")

# 1. TARJETAS (TEÓRICO)
liq = pd.read_sql_query(f"""
    SELECT fuente, SUM(total_neto) as neto
    FROM liquidaciones_tarjetas 
    WHERE fecha_liquidacion LIKE '{periodo}-%'
    GROUP BY fuente
""", conn)
total_liq = liq['neto'].sum()

# 2. BANCO (REAL) - Créditos y Débitos relacionados a tarjetas
banco = pd.read_sql_query(f"""
    SELECT SUM(importe) as neto
    FROM bancos_movimientos 
    WHERE fecha LIKE '{periodo}-%' AND (descripcion LIKE '%LIQUID%' OR descripcion LIKE '%NARANJA%')
""", conn).iloc[0]['neto'] or 0.0

# 3. IMPUESTO LEY 25413 (Masa fiscal)
impuestos = pd.read_sql_query(f"""
    SELECT SUM(importe) as total
    FROM bancos_movimientos 
    WHERE fecha LIKE '{periodo}-%' AND descripcion LIKE '%IMP LEY%'
""", conn).iloc[0]['total'] or 0.0

print(f"\n1. Venta Neta Esperada (Tarjetas): $ {total_liq:,.2f}")
for _, row in liq.iterrows():
    print(f"   - {row['fuente']}: $ {row['neto']:,.2f}")

print(f"\n2. Dinero Efectivo en Banco:       $ {banco:,.2f}")
print(f"3. Impuestos Bancarios (Ley):      $ {impuestos:,.2f}")

# El desfasaje al centavo
diferencia = total_liq - (banco + abs(impuestos)) # abs porque el impuesto es negativo, lo sumamos al gasto
print(f"\n--- DESFASAJE TOTAL: $ {diferencia:,.2f} ---")

conn.close()
