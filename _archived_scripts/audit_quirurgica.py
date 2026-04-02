import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('erp_nicoletti.db')

# 1. Definir Periodo de Precision (Enero 2026)
periodo = '2026-01'

print(f"=== AUDITORÍA QUIRÚRGICA: {periodo} ===")

# --- TARJETAS: Lo que dicen que nos deben pagar ---
liq = pd.read_sql_query(f"""
    SELECT fuente, fecha_liquidacion, total_bruto, costo_arancel, costo_financiero, iva_21, retenciones, total_neto 
    FROM liquidaciones_tarjetas 
    WHERE fecha_liquidacion LIKE '{periodo}-%'
""", conn)

# --- BANCO: Lo que efectivamente entró y salió por Tarjetas ---
banco = pd.read_sql_query(f"""
    SELECT fecha, descripcion, importe 
    FROM bancos_movimientos 
    WHERE (descripcion LIKE '%LIQUID%' OR descripcion LIKE '%NARANJA%')
      AND fecha LIKE '{periodo}-%'
""", conn)

# --- BANCO: Lo que el banco nos mordió por fuera (Impuesto Ley) ---
impuesto_ley = pd.read_sql_query(f"""
    SELECT SUM(importe) as total 
    FROM bancos_movimientos 
    WHERE descripcion LIKE '%IMP LEY%' AND fecha LIKE '{periodo}-%'
""", conn).iloc[0]['total'] or 0.0

total_esperado = liq['total_neto'].sum()
total_recibido = banco['importe'].sum()

print(f"\n1. FLUJO TARJETAS (TEÓRICO):  $ {total_esperado:,.2f}")
print(f"2. FLUJO BANCO (REAL):       $ {total_recibido:,.2f}")
print(f"   Diferencia Bruta (1 - 2): $ {total_esperado - total_recibido:,.2f}")

print(f"\n3. DESCUENTOS BANCARIOS (Fuera de Tarjetas):")
print(f"   Impuesto Ley 25413:       $ {impuesto_ley:,.2f}")

diferencia_final = total_esperado - total_recibido + impuesto_ley # Sumamos el impuesto porque es negativo
print(f"\n4. DESFASAJE FINAL AL CENTAVO: $ {diferencia_final:,.2f}")

if abs(diferencia_final) > 0:
    print("\n--- POSIBLES CAUSAS DEL DESFASAJE ---")
    # Buscar liquidaciones de fin de mes que entran el mes siguiente
    fin_de_mes = liq[liq['fecha_liquidacion'].str.endswith('31') | liq['fecha_liquidacion'].str.endswith('30')]
    print(f"Liquidaciones de fin de mes (que pueden no haber entrado): $ {fin_de_mes['total_neto'].sum():,.2f}")

conn.close()
