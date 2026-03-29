import sys
import os
import requests

# CEREBRO ERP - Consola de Control Central 🦾🏗️🧱🧠⚖️

API_URL = "http://127.0.0.1:5005"

def query_api(endpoint, params=None, method="GET", data=None):
    try:
        url = f"{API_URL}/{endpoint}"
        if method.upper() == "POST":
            response = requests.post(url, json=data, params=params)
        else:
            response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error de conexion con API: {e}")
        return None

def mostrar_ayuda():
    print("\nCEREBRO ERP - CONSOLA DE INTERACCION (MULTI-AREA)")
    print("-" * 65)
    print("AREA: tarjetas (Payway, Patagonia 365, Naranja)")
    print("   -> resumen [anio]      | Consolidado de todas las liquidaciones.")
    print("   -> importar <src> <p>  | Importar PDF/CSV (Fuentes: PAYWAY, PATAGONIA365).")
    print("   -> audit               | Cruce de ventas diarias vs depositos.")
    print("   -> cupon <id/numero>   | Detalle tecnico de un cupon.")
    
    print("\nAREA: facturas (ARCA/CALIM)")
    print("   -> resumen [anio]      | Balance Ventas vs Compras.")
    print("   -> buscar <termino>    | Buscar comprobantes en DB.")
    print("-" * 65 + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        mostrar_ayuda()
        sys.exit(0)
    
    area = sys.argv[1].lower()
    cmd = sys.argv[2].lower()
    
    # --- ÁREA: TARJETAS ---
    if area == "tarjetas":
        if cmd == "resumen":
            anio = sys.argv[3] if len(sys.argv) > 3 else "2026"
            res = query_api("summary", params={"anio": anio})
            if res:
                print(f"\nRESUMEN CONSOLIDADO DE TARJETAS ({anio})")
                print("-" * 85)
                print(f"{'FUENTE':<15} | {'TIPO':<10} | {'CANT':<5} | {'MONTO BRUTO':<15} | {'NETO REAL':<15}")
                print("-" * 85)
                for l in res['tarjetas']['liquidaciones']:
                    print(f"{l['fuente']:<15} | {l['tipo']:<10} | {l['cantidad']:<5} | ${l['bruto']:>14,.2f} | ${l['neto']:>14,.2f}")
                print("-" * 85 + "\n")
        
        elif cmd == "importar":
            if len(sys.argv) < 5:
                print("Uso: python cerebro.py tarjetas importar <FUENTE> <PATH_ARCHIVO>")
            else:
                fuente = sys.argv[3]
                path = sys.argv[4]
                print(f"Iniciando importacion de {fuente}...")
                res = query_api("tarjetas/importar", method="POST", data={"fuente": fuente, "path": path})
                if res and res.get('status') == 'success':
                    print(f"OK: Datos de {fuente} procesados e ingresados.")
                else:
                    print(f"ERROR: {res.get('message') if res else 'API Caida'}")

        elif cmd == "audit":
            res = query_api("tarjetas/audit")
            if res:
                print("\nAUDITORIA DE VENTAS (Cruce Diarios Payway)")
                print(f"   Pendientes de Deposito: {len(res.get('missing_liquidations', []))}")
                print(f"   Depositos sin Tickets:  {len(res.get('missing_coupons', []))}\n")
            
        elif cmd == "cupon":
            cid = sys.argv[3]
            res = query_api(f"tarjetas/cupon/{cid}")
            if res:
                print(f"\nDETALLE CUPON {res['cupon']}")
                print(f"   - Monto: $ {res['monto_bruto']:,.2f} | Marca: {res['marca']}")

    # --- ÁREA: FACTURAS ---
    elif area == "facturas":
        if cmd == "resumen":
            anio = sys.argv[3] if len(sys.argv) > 3 else "2026"
            res = query_api("summary", params={"anio": anio})
            if res:
                f = res['facturacion']
                print(f"\nRESUMEN FACTURACION ({anio})")
                print(f"   - Ingresos: $ {f['monto_ventas']:,.2f}")
                print(f"   - Egresos:  $ {f['monto_compras']:,.2f}\n")
        
        elif cmd == "buscar":
            termino = sys.argv[3]
            res = query_api("facturas/buscar", params={"q": termino})
            if res:
                print(f"\nRESULTADOS BUSQUEDA: {termino}")
                for f in res[:5]:
                    print(f"   - {f['fecha_emision']} | {f['proveedor'][:25]:<25} | $ {f['monto_total']:>10,.2f}")
                print()

    else:
        mostrar_ayuda()
