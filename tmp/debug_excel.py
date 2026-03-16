
import openpyxl
f = r"C:\Users\essao\Downloads\Facturas de Compra (7).xlsx"
wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
sheet = wb.active
print(f"Hoja: {sheet.title}")
for i, row in enumerate(sheet.iter_rows(values_only=True)):
    print(row)
    if i > 10: break
