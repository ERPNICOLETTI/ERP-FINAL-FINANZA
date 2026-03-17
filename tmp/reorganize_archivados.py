"""
Reorganiza facturas_archivadas: mueve archivos PDF de la raiz
a subcarpetas por proveedor, extrayendo el nombre del proveedor del filename.

Formato del nombre: FECHA_PROVEEDOR_NOMBRE.ext
Ejemplo: 20260107_GRUPO_AUSTRAL_CHUBUT_S._R._L._526213.pdf
  -> carpeta: GRUPO_AUSTRAL_CHUBUT_S._R._L.
  -> archivo: 20260107_GRUPO_AUSTRAL_CHUBUT_S._R._L._526213.pdf
"""

import os
import shutil
import sqlite3

BASE = r"C:\Users\essao\OneDrive\Escritorio\ERP FINAL\static\facturas_archivadas"
DB   = r"C:\Users\essao\OneDrive\Escritorio\ERP FINAL\erp_nicoletti.db"

def extract_proveedor_from_filename(fname):
    """
    Del nombre FECHA_PROVEEDOR_NUMERO.ext extrae PROVEEDOR.
    El FECHA es 8 dígitos, el NUMERO es el último segmento antes de la extensión.
    """
    name = fname.rsplit('.', 1)[0]          # sin extension
    parts = name.split('_')                 # separar por _
    
    # El primer segmento es la fecha (8 dígitos)
    if len(parts) < 3:
        return None
    
    # El último segmento es el número (solo dígitos)
    # Buscamos desde el final el primer segmento que sea solo dígitos
    last_num_idx = len(parts) - 1
    for i in range(len(parts) - 1, 0, -1):
        if parts[i].isdigit():
            last_num_idx = i
            break
    
    # El proveedor es todo lo que queda entre la fecha y el número
    proveedor_parts = parts[1:last_num_idx]
    if not proveedor_parts:
        return None
    
    return '_'.join(proveedor_parts)

moved = []
skipped = []

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

for fname in sorted(os.listdir(BASE)):
    fpath = os.path.join(BASE, fname)
    
    # Solo archivos PDF/imagen en la raiz (no carpetas, no a_subir)
    if not os.path.isfile(fpath):
        continue
    if fname.startswith('A_SUBIR'):
        skipped.append(f"  SKIP (A_SUBIR): {fname}")
        continue
    
    proveedor = extract_proveedor_from_filename(fname)
    if not proveedor:
        skipped.append(f"  SKIP (no proveedor detectado): {fname}")
        continue
    
    # Crear carpeta del proveedor
    dest_folder = os.path.join(BASE, proveedor)
    os.makedirs(dest_folder, exist_ok=True)
    
    dest_path = os.path.join(dest_folder, fname)
    
    # Mover el archivo
    shutil.move(fpath, dest_path)
    moved.append(f"  ✅ {fname} -> {proveedor}/")
    
    # Actualizar la ruta en la DB
    new_ruta = f"/static/facturas_archivadas/{proveedor}/{fname}"
    conn.execute(
        "UPDATE facturas SET ruta_archivo = ? WHERE ruta_archivo LIKE ?",
        (new_ruta, f"%{fname}%")
    )

conn.commit()
conn.close()

print(f"\n{'='*60}")
print(f"✅ Archivos movidos: {len(moved)}")
for m in moved:
    print(m)

if skipped:
    print(f"\n⚠️  Omitidos: {len(skipped)}")
    for s in skipped:
        print(s)

print(f"\n📁 Estructura nueva en: {BASE}")
for entry in sorted(os.scandir(BASE), key=lambda e: e.name):
    if entry.is_dir():
        count = len([f for f in os.listdir(entry.path) if os.path.isfile(os.path.join(entry.path, f))])
        print(f"  📂 {entry.name}/ ({count} archivos)")
