import sys

# NEURONA COMPRAS - Especialista en Facturación (ARCA/AFIP, CALIM) 🧾🧠

def handle_command(cmd, args, query_api):
    if cmd == "help" or cmd == "--help":
        print("\n🧬 NEURONA FACTURAS - Comandos disponibles:")
        print("   -> resumen [anio]      | Balance Ventas vs Compras.")
        print("   -> buscar <termino>    | Buscar comprobantes en DB (Proveedor/Cuit/Número).")
        print("   -> importar <AFIP|CALIM> <path> | Inyección de datos desde archivos oficiales.")
        print("   -> sync                | Sincronizar archivos físicos y base de datos.")
        return

    if cmd == "resumen":
        anio = args[0] if len(args) > 0 else "2026"
        res = query_api("summary", params={"anio": anio})
        if res:
            f = res['facturacion']
            print(f"\nRESUMEN FACTURACION ({anio})")
            print(f"   - Ingresos: $ {f['monto_ventas']:,.2f}")
            print(f"   - Egresos:  $ {f['monto_compras']:,.2f}\n")
    
    elif cmd == "buscar":
        if len(args) < 1:
            print("Uso: python cerebro.py facturas buscar <TERMINO>")
        else:
            termino = args[0]
            res = query_api("facturas/buscar", params={"q": termino})
            if res:
                print(f"\nRESULTADOS BUSQUEDA: {termino}")
                for f in res[:5]:
                    print(f"   - {f['fecha_emision']} | {f['proveedor'][:25]:<25} | $ {f['monto_total']:>10,.2f}")
                print()

    elif cmd == "importar":
        if len(args) < 2:
            print("Uso: python cerebro.py facturas importar <AFIP|CALIM> <PATH_ARCHIVO>")
        else:
            fuente = args[0].upper()
            path = args[1]
            print(f"Iniciando importación de {fuente}...")
            res = query_api("facturas/importar", method="POST", data={"fuente": fuente, "path": path})
            if res and res.get('status') == 'success':
                print(f"OK: Datos de {fuente} procesados.")
            else:
                print(f"ERROR: {res.get('message') if res else 'API Caída'}")

    elif cmd == "sync":
        print("Sincronizando archivos físicos y base de datos...")
        res = query_api("facturas/sync_archivos")
        if res and res.get('status') == 'success':
            print("OK: Archivos organizados y sincronizados.")
        else:
            print(f"ERROR: {res.get('message') if res else 'API Caída'}")

    else:
        print(f"Comando '{cmd}' no reconocido en el área Facturas.")
        print("Usa 'python cerebro.py facturas help' para ver la lista.")
