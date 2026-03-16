import sqlite3
import os
import shutil
import re

# Configuración de rutas
SOURCE_DIR = r"C:\Users\essao\OneDrive\Escritorio\Escritorio\GestorFacturas\static\facturas_archivadas"
DEST_DIR = r"c:\Users\essao\OneDrive\Escritorio\ERP FINAL\static\facturas_archivadas"
DB_PATH = r"c:\Users\essao\OneDrive\Escritorio\ERP FINAL\erp_nicoletti.db"

def sync():
    if not os.path.exists(SOURCE_DIR):
        print(f"Error: No se encuentra la carpeta origen: {SOURCE_DIR}")
        return

    os.makedirs(DEST_DIR, exist_ok=True)
    os.makedirs(os.path.join(DEST_DIR, 'a_subir'), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    files = [f for f in os.listdir(SOURCE_DIR) if os.path.isfile(os.path.join(SOURCE_DIR, f))]
    
    synced_count = 0
    ghost_count = 0
    already_synced = 0

    # Obtener todas las facturas de la DB para comparar rápido
    facturas_db = cursor.execute("SELECT id, numero_completo, proveedor, estado_proceso FROM facturas").fetchall()
    facturas_map = {f['numero_completo'].lstrip('0'): f for f in facturas_db}

    for filename in files:
        if filename.endswith('.rar') or filename.endswith('.zip'):
            continue

        # Extract bits
        # Pattern: 20260123_PROVIDER_NAME_12345.pdf
        match_full = re.match(r'^(\d{8})_(.+)_(\d+)\.[^.]+$', filename)
        if not match_full:
            # Fallback regex
            match_num = re.search(r'_(\d+)\.[^.]+$', filename)
            if not match_num: continue
            num_clean = match_num.group(1).lstrip('0')
            provider_guess = "Desconocido"
            fecha_guess = None
        else:
            fecha_iso = f"{match_full.group(1)[:4]}-{match_full.group(1)[4:6]}-{match_full.group(1)[6:]}"
            provider_guess = match_full.group(2).replace('_', ' ')
            num_clean = match_full.group(3).lstrip('0')
            fecha_guess = fecha_iso

        # 1. Intentar match
        factura_match = facturas_map.get(num_clean)

        if factura_match:
            # ENCONTRADA en sistemas
            dest_path = os.path.join(DEST_DIR, filename)
            shutil.copy2(os.path.join(SOURCE_DIR, filename), dest_path)
            
            ruta_web = f"/static/facturas_archivadas/{filename}"
            
            cursor.execute('UPDATE facturas SET ruta_archivo = ?, estado_proceso = ? WHERE id = ?', 
                           (ruta_web, "ARCHIVADO", factura_match['id']))
            synced_count += 1
            print(f"✅ Vinculada: {filename}")
        else:
            # GHOST: No está en AFIP/CALIM pero tengo el archivo
            dest_path = os.path.join(DEST_DIR, 'a_subir', filename)
            shutil.copy2(os.path.join(SOURCE_DIR, filename), dest_path)
            
            ruta_web = f"/static/facturas_archivadas/a_subir/{filename}"
            
            # Ver si ya la insertamos
            exists = cursor.execute('SELECT id FROM facturas WHERE numero_completo = ?', (num_clean,)).fetchone()
            if not exists:
                cursor.execute('''
                    INSERT INTO facturas (numero_completo, esta_en_afip, esta_en_calim, estado_proceso, ruta_archivo, proveedor, fecha_emision)
                    VALUES (?, 0, 0, 'A_SUBIR', ?, ?, ?)
                ''', (num_clean, ruta_web, provider_guess, fecha_guess))
                ghost_count += 1
                print(f"⚠️  Huérfana (A Subir): {filename}")
            else:
                # Si existe pero era huérfana de la corrida anterior, actualizar info
                cursor.execute('UPDATE facturas SET proveedor = ?, fecha_emision = ? WHERE numero_completo = ? AND esta_en_afip = 0 AND esta_en_calim = 0',
                               (provider_guess, fecha_guess, num_clean))
                already_synced += 1

    conn.commit()
    conn.close()
    print(f"\nSincronización finalizada.")

if __name__ == "__main__":
    sync()
