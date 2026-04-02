import sys

# NEURONA BANCOS - Especialista en Tesorería (Extractos y Conciliación) 🏦🧠

def handle_command(cmd, args, query_api):
    if cmd == "help" or cmd == "--help":
        print("\n🧬 NEURONA BANCOS - Comandos disponibles:")
        print("   -> importar <BANCO> <path> | Importar extractos (CHUBUT, HIPOTECARIO, CREDICOOP).")
        print("   -> audit                   | Cruce de Bancos vs Tarjetas (Proximamente).")
        return

    if cmd == "importar":
        if len(args) < 2:
            print("Uso: python cerebro.py bancos importar <BANCO> <PATH_ARCHIVO>")
        else:
            fuente = args[0].upper()
            path = args[1]
            print(f"Iniciando importación de movimientos de {fuente}...")
            res = query_api("bancos/importar", method="POST", data={"fuente": fuente, "path": path})
            if res and res.get('status') == 'success':
                print(f"OK: Extracto de {fuente} procesado y guardado en la base de datos.")
            else:
                print(f"ERROR: {res.get('message') if res else 'API Caída'}")
    
    elif cmd == "audit":
        print("Módulo de Auditoría Bancaria (Cruce de extractos vs Ventas)... próximamente.")
    
    else:
        print(f"Comando '{cmd}' no reconocido en el área Bancos.")
        print("Usa 'python cerebro.py bancos help' para ver la lista.")
