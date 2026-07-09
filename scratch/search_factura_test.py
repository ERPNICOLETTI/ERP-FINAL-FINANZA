import sqlite3

def check():
    conn = sqlite3.connect('erp_nicoletti.db')
    cursor = conn.cursor()
    
    print("--- BUSCANDO POR NÚMERO 245 ---")
    cursor.execute("SELECT id, fecha, proveedor, cuit_proveedor, punto_venta, numero_comprobante, total, origen, tiene_foto, path_archivo FROM compras_facturas WHERE numero_comprobante = '00000245'")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- BUSCANDO POR PROVEEDOR COCO / CUIT ---")
    cursor.execute("SELECT id, fecha, proveedor, cuit_proveedor, punto_venta, numero_comprobante, total, origen FROM compras_facturas WHERE proveedor LIKE '%COCO%' OR cuit_proveedor = '30716557363'")
    for row in cursor.fetchall():
        print(row)
        
    conn.close()

if __name__ == '__main__':
    check()
