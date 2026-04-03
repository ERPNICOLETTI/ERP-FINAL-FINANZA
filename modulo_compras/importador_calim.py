import os
import sys
import pandas as pd
from datetime import datetime

# Importaciones Modulares (Ownership)
from . import storage_compras as storage
from core_sistema import db_ingesta, checksum_service

# Setup utf-8 output for windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Diccionario Inverso para mapear nombres de CALIM al Código de AFIP
CALIM_TO_AFIP_CODIGO = {
    'Factura A': 1, 'Nota de Débito A': 2, 'Nota de Crédito A': 3,
    'Factura B': 6, 'Nota de Débito B': 7, 'Nota de Crédito B': 8,
    'Factura C': 11, 'Nota de Débito C': 12, 'Nota de Crédito C': 13,
    'Factura M': 51, 'Nota de Débito M': 52, 'Nota de Crédito M': 53
}

def parse_calim_excel(file_path):
    """
    IMPORTADOR ROBUSTO DE CALIM (Excel).
    """
    print(f"🧾 Analizando Excel de CALIM: {os.path.basename(file_path)}")
    
    # 1. CONTROL DE DUPLICADOS
    es_nuevo, hash_val = checksum_service.validar_y_registrar("COMPRAS", "FILE", os.path.basename(file_path), file_path)
    if not es_nuevo:
        print(f"🚫 SALTADO: Ya procesado.")
        return

    try:
        # Usamos calamine para bypassear los Excel rotos de CALIM
        df = pd.read_excel(file_path, engine='calamine')
        df = df.dropna(subset=['Numero', 'Total'])
        
        registros_procesados = 0
        
        for idx, row in df.iterrows():
            try:
                # 1. Interpretar Fecha
                fecha_raw = str(row['Fecha']).strip()
                fecha_emision = datetime.strptime(fecha_raw, "%d/%m/%Y").strftime("%Y-%m-%d") if '/' in fecha_raw else fecha_raw
                
                # 2. Interpretar Montos
                def parse_money(val):
                    if pd.isna(val): return 0.0
                    val = str(val).replace('$', '').replace('.', '').replace(',', '.').strip()
                    try: return float(val)
                    except: return 0.0
                        
                neto_gravado = parse_money(row.get('Neto'))
                monto_iva = parse_money(row.get('Iva'))
                monto_total = parse_money(row['Total'])
                tipo_nombre = str(row['Tipo']).strip()
                
                # Ajuste de signos
                if 'Crédito' in tipo_nombre:
                    neto_gravado, monto_iva, monto_total = -abs(neto_gravado), -abs(monto_iva), -abs(monto_total)
                else:
                    neto_gravado, monto_iva, monto_total = abs(neto_gravado), abs(monto_iva), abs(monto_total)
                    
                # 3. Formatear la llave única
                tipo_codigo = CALIM_TO_AFIP_CODIGO.get(tipo_nombre, 0)
                codigo_str = str(tipo_codigo).zfill(3)
                num_raw = str(row['Numero']).split('-')
                pv = num_raw[0].strip().zfill(5) if len(num_raw) == 2 else "00000"
                n = num_raw[1].strip().zfill(8) if len(num_raw) == 2 else str(row['Numero']).strip().zfill(8)
                numero_completo = f"{codigo_str}-{pv}-{n}"
                
                # 4. Inserción mediante Storage Modular
                factura_data = {
                    "numero_completo": numero_completo,
                    "tipo_operacion": 'COMPRA' if 'Compra' in os.path.basename(file_path) else 'VENTA',
                    "tipo_comprobante": tipo_nombre,
                    "proveedor": str(row['Proveedor']).strip(),
                    "fecha_emision": fecha_emision,
                    "neto_gravado": neto_gravado,
                    "monto_iva": monto_iva,
                    "monto_total": monto_total,
                    "status": "CONCILIADO_CALIM"
                }
                storage.save_factura(factura_data)
                registros_procesados += 1
                    
            except Exception as e:
                print(f"⚠️ Error en fila {idx}: {e}")

        print(f"✨ Éxito: {registros_procesados} comprobantes de CALIM sincronizados.")
        db_ingesta.update_search_index()
        
    except Exception as e:
        print(f"❌ Error fatal procesando CALIM: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for f in sys.argv[1:]:
            parse_calim_excel(f)
    else:
        print("💡 Uso: python importador_calim.py <ruta_archivo>")
