import sys

# NEURONA TARJETAS - Especialista en Recaudación (Payway, Naranja, Patagonia) 💳🧠

def handle_command(cmd, args, query_api):
    if cmd == "help" or cmd == "--help":
        print("\n🧬 NEURONA TARJETAS - Comandos disponibles:")
        print("   -> resumen [anio]      | Consolidado de todas las liquidaciones.")
        print("   -> importar <src> <p>  | Importar PDF/CSV (PAYWAY, PATAGONIA365, NARANJA).")
        print("   -> audit               | Cruce de ventas diarias vs depósitos.")
        print("   -> cupon <id/numero>   | Detalle técnico de un cupón.")
        return

    if cmd == "resumen":
        anio = args[0] if len(args) > 0 else "2026"
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
        if len(args) < 2:
            print("Uso: python cerebro.py tarjetas importar <FUENTE> <PATH_ARCHIVO>")
        else:
            fuente = args[0]
            path = args[1]
            print(f"Iniciando importación de {fuente}...")
            res = query_api("tarjetas/importar", method="POST", data={"fuente": fuente, "path": path})
            if res and res.get('status') == 'success':
                print(f"OK: Datos de {fuente} procesados e ingresados.")
            else:
                print(f"ERROR: {res.get('message') if res else 'API Caída'}")

    elif cmd == "audit":
        res = query_api("tarjetas/audit")
        if res:
            print("\nAUDITORIA DE VENTAS (Cruce Diarios Payway)")
            print(f"   Pendientes de Depósito: {len(res.get('missing_liquidations', []))}")
            print(f"   Depósitos sin Tickets:  {len(res.get('missing_coupons', []))}\n")
        
    elif cmd == "cupon":
        if len(args) < 1:
            print("Uso: python cerebro.py tarjetas cupon <ID>")
        else:
            cid = args[0]
            res = query_api(f"tarjetas/cupon/{cid}")
            if res and 'error' not in res:
                print(f"\nDETALLE CUPON")
                # Manejamos dinámicamente las claves para evitar KeyError si la estructura cambia
                for k, v in res.items():
                    if k != 'metadata':
                        print(f"   - {k.replace('_', ' ').capitalize()}: {v}")
            else:
                print(f"ERROR: {res.get('error') if res else 'Cupón no encontrado'}")
    else:
        print(f"Comando '{cmd}' no reconocido en el área Tarjetas.")
        print("Usa 'python cerebro.py tarjetas help' para ver la lista.")
