import sqlite3
import os
import sys

# Configure UTF-8 encoding for console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DB_PATH = 'erp_nicoletti.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute('''
        SELECT r.id, r.fecha, t.cuenta_codigo, t.nombre as categoria, t.emoji, r.descripcion, r.monto, r.fuente 
        FROM gastos_registros r 
        JOIN gastos_tipos t ON r.gasto_tipo_id = t.id 
        WHERE r.fuente = 'Patagonia 365' 
        ORDER BY r.fecha ASC
    ''').fetchall()
    
    print(f"Encontrados {len(rows)} registros de Patagonia 365:")
    for r in rows:
        print(f"ID: {r['id']} | Fecha: {r['fecha']} | Cuenta: {r['cuenta_codigo']} | Categoria: {r['categoria']} {r['emoji']} | Desc: {r['descripcion']} | Monto: ${r['monto']:.2f}")

    conn.close()

if __name__ == '__main__':
    main()
