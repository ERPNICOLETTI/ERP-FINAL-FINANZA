import os
import shutil
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modulo_compras import storage_compras

# Configuración de rutas - Relativas a la raíz del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.join(BASE_DIR, "static", "facturas_origen")  # TODO: Configurar carpeta de origen real
DEST_DIR = os.path.join(BASE_DIR, "static", "facturas_archivadas")

def sync():
    if not os.path.exists(SOURCE_DIR):
        print(f"Error: No se encuentra la carpeta origen: {SOURCE_DIR}")
        return

    os.makedirs(DEST_DIR, exist_ok=True)
    os.makedirs(os.path.join(DEST_DIR, 'a_subir'), exist_ok=True)

    files = [f for f in os.listdir(SOURCE_DIR) if os.path.isfile(os.path.join(SOURCE_DIR, f))]
    
    synced_count = 0
    ghost_count = 0

    print("♻️  Iniciando sincronización con Storage de Compras v4.5...")

    for filename in files:
        if filename.endswith('.rar') or filename.endswith('.zip'):
            continue

        match_full = re.match(r'^(\d{8})_(.+)_(\d+)\.[^.]+$', filename)
        if not match_full:
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

        # Usar patrón repositorio
        match_facturas = storage_compras.buscar_facturas(num_clean)
        
        # Filtramos la que más sentido tenga
        factura_match = None
        for f in match_facturas:
            if num_clean in f['numero_comprobante']:
                factura_match = f
                break

        if factura_match:
            dest_path = os.path.join(DEST_DIR, filename)
            shutil.copy2(os.path.join(SOURCE_DIR, filename), dest_path)
            
            ruta_web = f"/static/facturas_archivadas/{filename}"
            
            # Cero SQL! Usa función de storage
            storage_compras.update_record_path(factura_match['id'], ruta_web, "facturas")
            storage_compras.update_factura_status(factura_match['id'], "ARCHIVADO")
            
            synced_count += 1
            print(f"✅ Vinculada: {filename} -> ID {factura_match['id']}")
        else:
            # GHOST: No está en AFIP/CALIM pero tengo el archivo
            dest_path = os.path.join(DEST_DIR, 'a_subir', filename)
            shutil.copy2(os.path.join(SOURCE_DIR, filename), dest_path)
            ruta_web = f"/static/facturas_archivadas/a_subir/{filename}"
            
            # Crear la huérfana directo en BD sin SQL
            data_huerfana = {
                "punto_venta": "00000",
                "numero_comprobante": num_clean.zfill(8),
                "tipo_operacion": "COMPRA",
                "tipo_comprobante": "HUERFANA",
                "proveedor": provider_guess,
                "fecha": fecha_guess if fecha_guess else "2026-01-01",
                "neto": 0, "total": 0,
                "origen": "MANUAL",
                "status": "A_SUBIR",
                "tiene_foto": 1,
                "path_archivo": ruta_web
            }
            new_id = storage_compras.save_factura(data_huerfana)
            ghost_count += 1
            print(f"⚠️  Huérfana Crada en DB (A Subir): {filename}")

    print(f"\nSincronización finalizada. {synced_count} vinculadas, {ghost_count} huérfanas subidas.")

if __name__ == "__main__":
    sync()
