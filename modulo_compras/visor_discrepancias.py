import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modulo_compras import storage_compras

def check_discrepancias():
    print("\n" + "="*60)
    print(" REPORTE DE DISCREPANCIAS: AFIP VS CALIM (v4.5)")
    print("="*60)
    
    facturas_pendientes = storage_compras.get_reporte_discrepancias()
    
    if not facturas_pendientes:
        print("¡Excelente! No hay facturas de compras pendientes de subir/conciliar con CALIM.")
    else:
        print(f"Detectadas {len(facturas_pendientes)} facturas pendientes de conciliar con el contador:")
        print("-" * 60)
        for row in facturas_pendientes:
            print(f"[-] {row['fecha']} | {row['numero_comprobante']} | {row['proveedor'][:20]:<20} | ${row['total']:>10,.2f} | {row['origen']}")

if __name__ == "__main__":
    check_discrepancias()
