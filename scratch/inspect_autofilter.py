import openpyxl

target_file = r"C:\Users\essao\Desktop\Escritorio\gestion_quimica\uploads\N.P._PATAGONIA_25-11-2025_CON_OFERTAS_DE_DICIEMBRE.xlsx"
wb = openpyxl.load_workbook(target_file, data_only=True)
ws = wb['LISTA Y OFERTAS NOV 2025']

print("AutoFilter Reference:", ws.auto_filter.ref)

# Verificar si B10 está dentro del rango de AutoFilter
if ws.auto_filter.ref:
    from openpyxl.utils import range_boundaries
    min_col, min_row, max_col, max_row = range_boundaries(ws.auto_filter.ref)
    print(f"Rango de filtro: Col {min_col} a {max_col}, Fila {min_row} a {max_row}")
    # B10 es Columna 2, Fila 10.
    if min_row <= 10 <= max_row and min_col <= 2 <= max_col:
        print("¡Sí! La celda B10 tiene un filtro activo configurado en su columna.")
else:
    print("No hay filtros automáticos definidos en la hoja.")

wb.close()
