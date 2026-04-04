import sqlite3
import os
import json
import sys

# Asegurar que el path del proyecto esté disponible
sys.path.append(os.getcwd())

DB_PATH = 'erp_nicoletti.db'

def migrar():
    if not os.path.exists(DB_PATH):
        print("❌ DB no encontrada.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("🚀 Iniciando migración de Compras a v4.5...")

    try:
        # Verificar si ya existe facturas_old por un intento fallido previo
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='facturas_old'")
        if cursor.fetchone():
            print("⚠️ Detectada tabla facturas_old previa. Intentando limpiar...")
            cursor.execute("DROP TABLE facturas_old")

        # 1. Renombrar tabla vieja para backup temporal
        cursor.execute("ALTER TABLE facturas RENAME TO facturas_old")
        print("📦 Tabla facturas movida a backup temporal.")

        # 2. Crear nuevas tablas con el estándar v4.5
        from modulo_compras import storage_compras
        storage_compras.init_db_compras()
        print("🧱 Nuevos planos v4.5 construidos.")

        # 3. Migrar datos de facturas
        old_rows = cursor.execute("SELECT * FROM facturas_old").fetchall()
        for row in old_rows:
            data = dict(row)
            # Mapear nombres viejos a nuevos v4.5
            new_data = {
                'fecha': data.get('fecha'),
                'tipo_comprobante': data.get('tipo_comprobante'),
                'punto_venta': data.get('punto_venta'),
                'numero_completo': data.get('numero_completo'),
                'cuit_proveedor': data.get('cuit_proveedor'),
                'proveedor': data.get('proveedor'),
                'neto': data.get('neto_gravado', data.get('neto', 0)),
                'iva21': data.get('iva_21', data.get('iva21', 0)),
                'iva105': data.get('iva_105', data.get('iva105', 0)),
                'iva27': data.get('iva_27', data.get('iva27', 0)),
                'exento': data.get('exento', 0),
                'percepcion_iva': data.get('percepciones', data.get('percepcion_iva', 0)),
                'imp_internos': data.get('imp_internos', 0),
                'total': data.get('monto_total', data.get('total', 0)),
                'moneda': data.get('moneda', 'ARS'),
                'tipo_operacion': data.get('tipo_operacion', 'COMPRA'),
                'status': data.get('status', 'SOLO_AFIP'),
                'tiene_foto': data.get('tiene_foto', 0),
                'path_archivo': data.get('path_archivo'),
                'hash_archivo': data.get('hash_archivo'),
                'origen': data.get('origen', 'AFIP'),
                'meta_json': data.get('metadata_cruda', data.get('meta_json', '{}'))
            }
            # Guardar en la nueva tabla
            storage_compras.save_factura(new_data)

        print(f"✅ {len(old_rows)} facturas migradas al nuevo estándar v4.5.")

        # 4. Poblar Maestro de Proveedores
        # Usar la tabla vieja para asegurar nombres limpios originales
        proveedores_unicos = cursor.execute("SELECT DISTINCT cuit_proveedor, proveedor FROM facturas_old").fetchall()
        for p in proveedores_unicos:
            if p['cuit_proveedor'] and p['proveedor']:
                storage_compras.upsert_proveedor(p['cuit_proveedor'], p['proveedor'])
        
        print(f"👥 {len(proveedores_unicos)} proveedores únicos migrados al Maestro.")

        # 5. Limpieza
        cursor.execute("DROP TABLE facturas_old")
        conn.commit()
        print("🧹 Limpieza completada. Tabla temporal eliminada.")
        print("✨ Migración Compras v4.5 Exitosa.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error en migración: {e}")
        try:
            # Intentar restaurar si es posible
            cursor.execute("ALTER TABLE facturas_old RENAME TO facturas")
            conn.commit()
            print("🛡️ Rollback de tabla facturas completado.")
        except:
            pass
    finally:
        conn.close()

if __name__ == '__main__':
    migrar()
