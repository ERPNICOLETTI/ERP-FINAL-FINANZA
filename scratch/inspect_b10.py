import openpyxl

target_file = r"C:\Users\essao\Desktop\Escritorio\gestion_quimica\uploads\N.P._PATAGONIA_25-11-2025_CON_OFERTAS_DE_DICIEMBRE.xlsx"
wb = openpyxl.load_workbook(target_file, data_only=True)
ws = wb['LISTA Y OFERTAS NOV 2025']

cell = ws['B10']
print("Valor:", cell.value)
if cell.font:
    print("Nombre Fuente:", cell.font.name)
    print("Tamaño:", cell.font.size)
    print("Negrita (Bold):", cell.font.bold)
    print("Cursiva (Italic):", cell.font.italic)
    print("Subrayado (Underline):", cell.font.underline)
    if cell.font.color:
        print("Color Fuente RGB:", getattr(cell.font.color, 'rgb', None))

if cell.fill:
    print("Fill type:", getattr(cell.fill, 'fill_type', None))
    start_color = getattr(cell.fill, 'start_color', None)
    if start_color:
        print("Color Fondo RGB:", getattr(start_color, 'rgb', None))

wb.close()
