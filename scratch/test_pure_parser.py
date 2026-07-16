import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core_sistema.lector_excel import LectorExcelUniversal

target_file = r"C:\Users\essao\Desktop\Escritorio\gestion_quimica\uploads\N.P._PATAGONIA_25-11-2025_CON_OFERTAS_DE_DICIEMBRE.xlsx"

if os.path.exists(target_file):
    print("🔄 Corriendo parser puro en memoria...")
    lector = LectorExcelUniversal()
    datos = lector.extraer_raw(target_file)
    print("Nombre archivo:", datos["nombre_archivo"])
    print("Pestañas:", datos["pestanas"])
    print("Cantidad de celdas procesadas:", len(datos["filas"]))
    
    # Mostrar una celda de ejemplo
    c894 = next((f for f in datos["filas"] if f["coordenada"] == "C894"), None)
    if c894:
        print("Celda C894:")
        print("  Valor:", c894["valor"])
        print("  Fondo:", c894["color"])
        print("  Fuente:", c894["color_fuente"])
        print("  Fórmula:", c894["metadatos"]["estructura"]["formula"])
else:
    print("El archivo no existe.")
