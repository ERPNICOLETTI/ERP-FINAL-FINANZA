import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')

def sanear_tablas():
    if not os.path.exists(DB_PATH):
        print("❌ No se encontró erp_nicoletti.db")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Mapa de tablas viejas -> nuevas
    migraciones = {
        'facturas': 'compras_facturas',
        'proveedores': 'compras_proveedores',
        'libroiva': 'compras_libroiva',
        'iva_desglosado': 'compras_iva_desglosado',
        'pagos': 'pagos_vencimientos',
        'liquidaciones_tarjetas': 'tarjetas_liquidaciones',
        'payway_records': 'tarjetas_payway'
    }
    
    print("\nINICIANDO RENOMBRADO MODULAR DE TABLAS (SIN PERDER DATOS)...")
    print("-" * 50)
    
    for vieja, nueva in migraciones.items():
        try:
            # Chequear si la vieja existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (vieja,))
            if cursor.fetchone():
                cursor.execute(f"ALTER TABLE {vieja} RENAME TO {nueva}")
                print(f"EXITO: '{vieja}' renombrada a '{nueva}'")
            else:
                print(f"OMITIDO: La tabla '{vieja}' ya no existe o ya fue migrada.")
        except Exception as e:
            print(f"ERROR con '{vieja}': {e}")
            
    conn.commit()
    conn.close()
    
    print("-" * 50)
    print("✨ Saneamiento estructural finalizado con éxito.\n")

if __name__ == "__main__":
    sanear_tablas()
