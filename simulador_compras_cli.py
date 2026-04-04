import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime

# Asegurar que el ERP FINAL está en el PYTHONPATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modulo_compras import storage_compras

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    clear()
    print("=============================================")
    print(" 🎮 SIMULADOR CLI: VINCULACIÓN VISUAL (v4.5)")
    print("=============================================\n")

    evidencia = input("📎 Ingresa la ruta de la evidencia (PDF/Foto) o arrastra el archivo aquí:\n> ").strip().strip('"').strip("'")
    if not os.path.exists(evidencia):
        print("❌ Error: El archivo no existe.")
        return

    print(f"\n✅ Evidencia detectada: {os.path.basename(evidencia)}")
    
    num_factura = input("🔢 Ingresa el número de comprobante a buscar (ej: 0001-00001234):\n> ").strip()

    print("\n🔍 Buscando coincidencia en DB (AFIP/Calim)...")
    resultados = storage_compras.buscar_facturas(num_factura)

    match = None
    # Priorizamos coincidencias exactas del numero completo
    for r in resultados:
        if num_factura in r['numero_completo']:
            match = r
            break

    if match:
        print("\n🎉 FACTURA ENCONTRADA")
        print(f"   Proveedor: {match['proveedor']} (CUIT: {match['cuit_proveedor']})")
        print(f"   Fecha: {match['fecha']}")
        print(f"   Total: ${match['total']}")
        print(f"   Origen: {match['origen']} | ID DB: {match['id']}")

        confirma = input("\n👉 ¿Deseas vincular esta evidencia a esta factura? (S/N): ").upper()
        if confirma == 'S':
            print("\n⚙️ Vinculando y Archivando...")
            pv, num = match['numero_completo'].split('-') if '-' in match['numero_completo'] else ("0", match['numero_completo'])
            pv = pv.split("-")[1] if len(match['numero_completo'].split('-')) == 3 else pv
            # Formato de numero completo estándar: 011-00001-00000100 o 00001-00000100
            parts = match['numero_completo'].split('-')
            if len(parts) >= 2:
                pv, num = parts[-2], parts[-1]
            else:
                pv, num = "0000", parts[0]

            success, nuevo_path = storage_compras.archivar_evidencia_visual(
                factura_id=match['id'],
                source_path=evidencia,
                cuit=match['cuit_proveedor'],
                nombre_proveedor=match['proveedor'],
                fecha=match['fecha'],
                punto_venta=pv,
                numero=num
            )
            if success:
                print(f"✅ ¡Vinculación Exitosa!")
                print(f"   Archivo movido a: {nuevo_path}")
            else:
                print(f"❌ Falló el archivado: {nuevo_path}")
        else:
            print("❌ Operación Cancelada.")
    else:
        print("\n⚠️ Factura NO ENCONTRADA en las Ingestas de AFIP/Calim.")
        print("   Iniciando Flujo de Carga Manual Asistida...\n")
        
        busqueda_prov = input("🏢 Busca al proveedor (Nombre Fantasía o CUIT):\n> ").strip()
        proveedores = storage_compras.buscar_proveedores_fuzzy(busqueda_prov)
        
        prov_seleccionado = None
        if proveedores:
            print("\n🔎 Coincidencias encontradas:")
            for i, p in enumerate(proveedores):
                print(f"  [{i+1}] {p['nombre_fantasia']} (CUIT: {p['cuit']})")
            print(f"  [0] NINGUNO DE LOS ANTERIORES. Crear nuevo.")
            
            opcion = input("\n👉 Selecciona una opción:\n> ").strip()
            if opcion.isdigit() and int(opcion) > 0 and int(opcion) <= len(proveedores):
                prov_seleccionado = proveedores[int(opcion)-1]
        
        if not prov_seleccionado:
            print("\n➕ CREAR NUEVO PROVEEDOR")
            cuit_nuevo = input("   CUIT: ").strip()
            nombre_nuevo = input("   Razón Social / Nombre: ").strip().upper()
            storage_compras.upsert_proveedor(cuit_nuevo, nombre_nuevo)
            prov_seleccionado = {'cuit': cuit_nuevo, 'nombre_fantasia': nombre_nuevo}
            print("✅ Proveedor guardado en el Maestro.")

        print(f"\n📋 Completando Carga Manual para: {prov_seleccionado['nombre_fantasia']}")
        fecha = input("   Fecha (YYYY-MM-DD): ").strip()
        punto_venta = input("   Punto de Venta (ej: 00003): ").strip().zfill(5)
        numero = input("   Número (ej: 00001234): ").strip().zfill(8)
        total = float(input("   Monto Total: $") or 0)
        
        # Validar formato de fecha o default it
        if not fecha: fecha = datetime.now().strftime('%Y-%m-%d')
        numero_completo = f"011-{punto_venta}-{numero}" # Asumiendo un tipo generico
        
        factura_fake = {
            'fecha': fecha,
            'tipo_comprobante': 'Factura C / Gasto Manual',
            'punto_venta': punto_venta,
            'numero_completo': numero_completo,
            'cuit_proveedor': prov_seleccionado['cuit'],
            'proveedor': prov_seleccionado['nombre_fantasia'],
            'total': total,
            'neto': total,
            'tiene_foto': 1, # Se inserta asumiendo que el archivo se va a vincular
            'origen': 'MANUAL',
            'status': 'CARGA_MANUAL'
        }

        print("\n⚙️ Guardando en Base de Datos...")
        new_id = storage_compras.save_factura(factura_fake)
        
        if new_id:
            print("⚙️ Archivando Evidencia Legal...")
            success, nuevo_path = storage_compras.archivar_evidencia_visual(
                factura_id=new_id,
                source_path=evidencia,
                cuit=prov_seleccionado['cuit'],
                nombre_proveedor=prov_seleccionado['nombre_fantasia'],
                fecha=fecha,
                punto_venta=punto_venta,
                numero=numero
            )
            print("✅ ¡Carga Manual Exitosa!")
            print(f"   Origen: MANUAL | ID DB: {new_id}")
            print(f"   Archivo asegurado en: {nuevo_path}")
        else:
            print("❌ Error al guardar la factura manual en BD.")

if __name__ == '__main__':
    main()
