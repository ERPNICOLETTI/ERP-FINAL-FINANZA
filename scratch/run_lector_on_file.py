import os
import sys

# Asegurar que la raíz del proyecto esté en el PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core_sistema.lector_excel import LectorExcelUniversal

db_path = "excel_staging.db"
target_file = r"C:\Users\essao\Desktop\Escritorio\gestion_quimica\uploads\N.P._PATAGONIA_25-11-2025_CON_OFERTAS_DE_DICIEMBRE.xlsx"

if not os.path.exists(target_file):
    print(f"❌ El archivo no existe en la ruta: {target_file}")
    sys.exit(1)

# Asegurar que si la base de datos ya tenía el registro para este test, lo borramos
if os.path.exists(db_path):
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("DROP TABLE IF EXISTS core_historial_archivos")
        conn.execute("DROP TABLE IF EXISTS core_staging_raw")
        conn.commit()
        conn.close()
    except Exception:
        pass

print(f"🔄 Procesando archivo: {target_file}")
lector = LectorExcelUniversal(db_path)
resultado = lector.procesar_e_ingestar_archivo(target_file)
print("Resultado:", resultado)
