
import openpyxl
import os

def count_simple(file_path):
    try:
        # read_only=True suele evitar errores de estilos corruptos
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        nums = set()
        for sheet in wb.worksheets:
            header_idx = -1
            col_map = {}
            # Como es read_only, iteramos manualmente
            rows = []
            for r in sheet.iter_rows(values_only=True):
                rows.append(r)
                if len(rows) > 1000: break # Limite de seguridad
            
            for i, row in enumerate(rows[:50]):
                row_str = " ".join([str(c).lower() for c in row if c])
                if ("proveedor" in row_str or "denominaci" in row_str) and ("iva" in row_str or "total" in row_str):
                    header_idx = i
                    for idx, c in enumerate(row):
                        h = str(c or "").lower()
                        if "punto de venta" in h: col_map['pv'] = idx
                        if "número desde" in h: col_map['num'] = idx
                        if any(x in h for x in ["numero", "nro", "factura"]):
                            if 'calim' not in col_map: col_map['calim'] = idx
                    break
            if header_idx != -1:
                for row in rows[header_idx+1:]:
                    n = ""
                    if 'calim' in col_map and row[col_map['calim']]:
                        n = "".join(filter(str.isdigit, str(row[col_map['calim']])))
                    elif 'pv' in col_map and 'num' in col_map and row[col_map['pv']] and row[col_map['num']]:
                        pv = "".join(filter(str.isdigit, str(row[col_map['pv']]))).zfill(4)
                        num = "".join(filter(str.isdigit, str(row[col_map['num']]))).zfill(8)
                        n = pv + num
                    n = n.lstrip('0')
                    if len(n) >= 2: nums.add(n)
        return nums
    except: return set()

f1 = r"C:\Users\essao\Downloads\Facturas de Compra (7).xlsx"
f2 = r"C:\Users\essao\Downloads\Mis Comprobantes Recibidos - CUIT 27329549971 (5).xlsx"

n1 = count_simple(f1)
n2 = count_simple(f2)

combined = n1 | n2
intersection = n1 & n2

print(f"Archivo 1 (Facturas de Compra): {len(n1)} facturas únicas")
print(f"Archivo 2 (Mis Comprobantes): {len(n2)} facturas únicas")
print(f"Total REAL unificado: {len(combined)}")
print(f"Facturas repetidas en AMBOS archivos: {len(intersection)}")
