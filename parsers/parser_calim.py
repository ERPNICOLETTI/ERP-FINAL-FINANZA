import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime

# Setup utf-8 output for windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(WORKSPACE, 'erp_nicoletti.db')

# Diccionario Inverso para mapear nombres de CALIM al Código de AFIP y armar el mismo "numero_completo"
CALIM_TO_AFIP_CODIGO = {
    'Factura A': 1,
    'Nota de Débito A': 2,
    'Nota de Crédito A': 3,
    'Factura B': 6,
    'Nota de Débito B': 7,
    'Nota de Crédito B': 8,
    'Factura C': 11,
    'Nota de Débito C': 12,
    'Nota de Crédito C': 13,
    'Factura M': 51,
    'Nota de Débito M': 52,
    'Nota de Crédito M': 53
}

def parse_calim_excel(file_path):
    print(f"[{os.path.basename(file_path)}] Iniciando procesamiento de reporte CALIM...")
    
    # Usamos calamine para bypassear los Excel rotos de CALIM
    try:
        df = pd.read_excel(file_path, engine='calamine')
    except Exception as e:
        print(f"Error fatal abriendo Excel de CALIM: {e}")
        return
        
    # Limpieza básica
    df = df.dropna(subset=['Numero', 'Total'])
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    insertados = 0
    actualizados = 0
    match_afip_count = 0
    
    for idx, row in df.iterrows():
        try:
            # 1. Interpretar Fecha (DD/MM/YYYY a YYYY-MM-DD)
            fecha_raw = str(row['Fecha']).strip()
            fecha_emision = datetime.strptime(fecha_raw, "%d/%m/%Y").strftime("%Y-%m-%d") if '/' in fecha_raw else fecha_raw
            
            # 2. Interpretar Montos
            def parse_money(val):
                if pd.isna(val): return 0.0
                val = str(val).replace('$', '').replace('.', '').replace(',', '.').strip()
                try:
                    return float(val)
                except:
                    return 0.0
                    
            neto_gravado = parse_money(row.get('Neto'))
            monto_iva = parse_money(row.get('Iva'))
            monto_total = parse_money(row['Total'])
            
            tipo_nombre = str(row['Tipo']).strip()
            
            # Ajuste de signos idéntico a AFIP
            if 'Crédito' in tipo_nombre:
                neto_gravado = -abs(neto_gravado)
                monto_iva = -abs(monto_iva)
                monto_total = -abs(monto_total)
            else:
                neto_gravado = abs(neto_gravado)
                monto_iva = abs(monto_iva)
                monto_total = abs(monto_total)
                
            # 3. Formatear la llave única (Ej: 001-00073-00513907)
            tipo_codigo = CALIM_TO_AFIP_CODIGO.get(tipo_nombre, 0)
            codigo_str = str(tipo_codigo).zfill(3)
            
            # CALIM separa Punto y Num con un guión "0073 - 00513907"
            num_raw = str(row['Numero']).split('-')
            if len(num_raw) == 2:
                pv = num_raw[0].strip().zfill(5)
                n = num_raw[1].strip().zfill(8)
            else:
                # Fallback si no tiene guión
                pv = "00000"
                n = str(row['Numero']).strip().zfill(8)
                
            numero_completo = f"{codigo_str}-{pv}-{n}"
            
            # 4. Proveedor o Cliente
            proveedor = str(row['Proveedor']).strip()
            
            # CALIM son archivos de compra si dice "Facturas de Compra" en el nombre, si no asume venta (pero por ahora guardamos COMPRA de default o deducimos)
            es_compra = 'Compra' in os.path.basename(file_path)
            tipo_operacion = 'COMPRA' if es_compra else 'VENTA'

            # 5. Guardado en la tabla Segregada (facturas_calim)
            cur.execute('''
                INSERT INTO facturas_calim (
                    numero_completo, tipo_operacion, tipo_comprobante, proveedor, fecha_emision,
                    neto_gravado, monto_iva, monto_total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(numero_completo) DO UPDATE SET
                    tipo_operacion = excluded.tipo_operacion,
                    proveedor = excluded.proveedor,
                    monto_total = excluded.monto_total,
                    tipo_comprobante = excluded.tipo_comprobante
            ''', (numero_completo, tipo_operacion, tipo_nombre, proveedor, fecha_emision, neto_gravado, monto_iva, monto_total))
            
            insertados += 1
            
            # OJO A LA MAGIA: Actualizamos también la tabla oficial AFIP (facturas) poniéndole el gancho de esta_en_calim=1
            cur.execute("UPDATE facturas SET esta_en_calim = 1 WHERE numero_completo = ?", (numero_completo,))
            if cur.rowcount > 0:
                match_afip_count += 1
                
        except Exception as e:
            print(f"Error procesando fila {idx} ({row.get('Numero', 'Desconocido')}): {e}")

    conn.commit()
    conn.close()
    
    print("\n--- RESUMEN DE IMPORTACIÓN DE CALIM ---")
    print(f"-> Facturas Inyectadas a tabla CALIM: {insertados}")
    print(f"-> MATCHINGS EXITOSOS CON AFIP!: {match_afip_count} facturas unificadas")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("💡 Uso: python import/parser_calim.py <ruta_al_excel_calim>")
        sys.exit(1)
        
    for file in sys.argv[1:]:
        parse_calim_excel(file)
