import sys

# NEURONA BANCOS - Especialista en Tesorería (Extractos y Conciliación) 🏦🧠

def handle_command(cmd, args, query_api):
    if cmd == "help" or cmd == "--help":
        print("\n🧬 NEURONA BANCOS - Comandos disponibles:")
        print("   -> importar <BANCO> <pathTransfer> | Importar extractos (CHUBUT, HIPOTECARIO, CREDICOOP).")
        print("   -> sueldos [anio]           | Listado de haberes y sueldos detectados.")
        print("   -> audit                    | Cruce de Bancos vs Tarjetas (Próximamente).")
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
    
    elif cmd == "sueldos":
        anio = args[0] if len(args) > 0 else "2026"
        print(f"💎 ESCANEANDO SUELDOS (HABERES) - BANCO HIPOTECARIO...")
        # Nota: En un entorno ideal, esto se pediría al storage_bancos.
        # Por ahora, mantengamos la lógica de consulta aquí para el CLI.
        params = [f"%{anio}", "%SUELDOS%", "%PINO SUB SA%"]
        query = "SELECT fecha, descripcion, importe FROM bancos_movimientos WHERE (descripcion LIKE ? OR descripcion LIKE ?) AND fecha LIKE ? ORDER BY fecha DESC"
        
        # Como neuron_bancos no tiene acceso directo a la DB (usa query_api),
        # necesitaremos un endpoint en la API para esta consulta.
        res = query_api("bancos/sueldos", params={"anio": anio})
        if res:
            print("-" * 60)
            print(f"{'FECHA':<12} | {'DESCRIPCION':<30} | {'IMPORTE':<12}")
            print("-" * 60)
            total = 0
            for s in res:
                print(f"{s['fecha']:<12} | {s['descripcion'][:30]:<30} | $ {s['importe']:>10,.2f}")
                total += s['importe']
            print("-" * 60)
            print(f"TOTAL DETECTADO: $ {total:,.2f}\n")
    
    elif cmd == "audit":
        print("Módulo de Auditoría Bancaria (Cruce de extractos vs Ventas)... próximamente.")
    
    else:
        print(f"Comando '{cmd}' no reconocido en el área Bancos.")
        print("Usa 'python cerebro.py bancos help' para ver la lista.")
