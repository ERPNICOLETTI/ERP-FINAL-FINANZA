import sqlite3
import os

db_path = r'C:\Users\essao\Desktop\ERP FINAL\erp_nicoletti.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- REFORZANDO RUTAS DE SALA DE ESPERA ---")
cursor.execute("SELECT id, path_archivo, status FROM facturas WHERE status = 'SALA_ESPERA'")
rows = cursor.fetchall()
repaired = 0

for row in rows:
    old_path = row['path_archivo'] or ""
    # Si la ruta no tiene PENDIENTES CALIM, la forzamos a la carpeta correcta
    if "PENDIENTES CALIM" not in old_path:
        filename = old_path.split('/')[-1].split('\\')[-1]
        # Reconstruir la ruta correcta de la Sala de Espera
        # Estructura: Facturas/00000000000 - PENDIENTES CALIM/YYYY/MM/Nombre_Factura_...
        # Como no tengo la fecha exacta de la transaccion aqui de forma limpia sin parsear,
        # simplemente reemplazaremos el fragmento de la entidad si es detectable.
        
        # O mejor, lo hacemos atomico buscando el archivo real
        # ID 125, etc.
        
        # Busquemos en la carpeta 00000000000 - PENDIENTES CALIM
        new_path = old_path.replace('00000000000%20-%20PINTURERIA%20EL%20SOL', '00000000000 - PENDIENTES CALIM') \
                            .replace('00000000000 - PINTURERIA EL SOL', '00000000000 - PENDIENTES CALIM') \
                            .replace('\\', '/')
        
        print(f"Corrigiendo Pendiente ID {row['id']}: {new_path}")
        cursor.execute("UPDATE facturas SET path_archivo = ? WHERE id = ?", (new_path, row['id']))
        repaired += 1

conn.commit()
conn.close()
print(f"--- LISTO. {repaired} ENLACES DE CUARENTENA SINCRONIZADOS ---")
