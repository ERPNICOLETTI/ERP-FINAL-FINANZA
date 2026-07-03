import sqlite3
import os
import sys

# Configure UTF-8 encoding for console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DB_PATH = "erp_nicoletti.db"

def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: No se encontro la base de datos en {DB_PATH}")
        return

    print("Conectando a la base de datos...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Contar antes
        bancos_count = cursor.execute("SELECT COUNT(*) FROM bancos_movimientos").fetchone()[0]
        meta_count = cursor.execute("SELECT COUNT(*) FROM bancos_archivos_metadata").fetchone()[0]
        ingestas_count = cursor.execute("SELECT COUNT(*) FROM core_registro_ingestas").fetchone()[0]
        
        # Para gastos_registros, contamos los automáticos (los de tarjetas/bancos)
        gastos_auto_count = cursor.execute(
            "SELECT COUNT(*) FROM gastos_registros WHERE fuente IS NOT NULL AND fuente NOT IN ('Manual', 'Efectivo')"
        ).fetchone()[0]
        gastos_manual_count = cursor.execute(
            "SELECT COUNT(*) FROM gastos_registros WHERE fuente IS NULL OR fuente IN ('Manual', 'Efectivo')"
        ).fetchone()[0]

        print(f"Estado actual:")
        print(f"  - Movimientos de bancos: {bancos_count}")
        print(f"  - Metadatos de archivos bancarios: {meta_count}")
        print(f"  - Registros de ingesta core: {ingestas_count}")
        print(f"  - Gastos de tarjetas (automaticos): {gastos_auto_count}")
        print(f"  - Gastos manuales (efectivo): {gastos_manual_count}")

        print("\nIniciando limpieza...")

        # 1. Vaciar bancos_movimientos
        cursor.execute("DELETE FROM bancos_movimientos")
        print("  Tabla 'bancos_movimientos' vaciada.")

        # 2. Vaciar bancos_archivos_metadata
        cursor.execute("DELETE FROM bancos_archivos_metadata")
        print("  Tabla 'bancos_archivos_metadata' vaciada.")

        # 3. Vaciar core_registro_ingestas
        cursor.execute("DELETE FROM core_registro_ingestas")
        print("  Tabla 'core_registro_ingestas' vaciada.")

        # 4. Eliminar consumos automáticos en gastos_registros (Tarjetas)
        cursor.execute(
            "DELETE FROM gastos_registros WHERE fuente IS NOT NULL AND fuente NOT IN ('Manual', 'Efectivo')"
        )
        print("  Gastos de tarjetas (automaticos) eliminados de 'gastos_registros'.")

        # Confirmar
        conn.commit()
        print("\nLimpieza realizada con exito!")

        # Contar después
        b_after = cursor.execute("SELECT COUNT(*) FROM bancos_movimientos").fetchone()[0]
        m_after = cursor.execute("SELECT COUNT(*) FROM bancos_archivos_metadata").fetchone()[0]
        i_after = cursor.execute("SELECT COUNT(*) FROM core_registro_ingestas").fetchone()[0]
        ga_after = cursor.execute(
            "SELECT COUNT(*) FROM gastos_registros WHERE fuente IS NOT NULL AND fuente NOT IN ('Manual', 'Efectivo')"
        ).fetchone()[0]
        gm_after = cursor.execute(
            "SELECT COUNT(*) FROM gastos_registros WHERE fuente IS NULL OR fuente IN ('Manual', 'Efectivo')"
        ).fetchone()[0]

        print(f"\nEstado final:")
        print(f"  - Movimientos de bancos: {b_after}")
        print(f"  - Metadatos de archivos bancarios: {m_after}")
        print(f"  - Registros de ingesta core: {i_after}")
        print(f"  - Gastos de tarjetas (automaticos): {ga_after}")
        print(f"  - Gastos manuales (efectivo): {gm_after}")

    except Exception as e:
        conn.rollback()
        print(f"Error durante la limpieza: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
