import os
import shutil
import pandas as pd
from . import storage_compras as storage
from . import importador_afip, importador_calim

# NEURONA COMPRAS - Especialista en Facturación (ARCA/AFIP, CALIM) 🧾🧠🔍

def detectar_y_procesar(file_path):
    """Detecta el tipo de reporte fiscal y lanza el importador."""
    ext = os.path.splitext(file_path)[1].lower()
    
    # 1. AFIP (CSV)
    if ext == '.csv':
        try:
            # AFIP usa UTF-8 o Latin-1
            with open(file_path, 'r', encoding='utf-8') as f:
                header = f.readline().lower()
                if "fecha de emisión" in header or "cuit" in header:
                    print(f"🔍 [DETECTIVE] Identificado: REPORTE AFIP (CSV)")
                    importador_afip.parse_afip_csv(file_path)
                    return True
        except:
            pass

    # 2. CALIM (EXCEL)
    elif ext in ['.xlsx', '.xls']:
        try:
            # Peek rápido
            df_peek = pd.read_excel(file_path, nrows=5, engine='calamine')
            content_str = df_peek.to_string().lower()
            if "total" in content_str and ("proveedor" in content_str or "cuil/cuit" in content_str):
                print(f"🔍 [DETECTIVE] Identificado: REPORTE CALIM (EXCEL)")
                importador_calim.parse_calim_excel(file_path)
                return True
        except:
            pass
            
    print(f"⚠️ [DETECTIVE] No se pudo identificar el reporte fiscal: {os.path.basename(file_path)}")
    return False

def ejecutar_scan():
    """Escanea la carpeta crudos de compras y procesa."""
    path_crudos = os.path.join(os.path.dirname(__file__), "crudos")
    path_procesados = os.path.join(path_crudos, "procesados")
    
    if not os.path.exists(path_procesados):
        os.makedirs(path_procesados)
        
    print(f"🚀 [COMPRAS] Iniciando escaneo fiscal en {path_crudos}...")
    archivos = [f for f in os.listdir(path_crudos) if os.path.isfile(os.path.join(path_crudos, f))]
    
    count = 0
    for f in archivos:
        if f == ".gitkeep": continue
        full_path = os.path.join(path_crudos, f)
        if detectar_y_procesar(full_path):
            shutil.move(full_path, os.path.join(path_procesados, f))
            count += 1
            
    print(f"✅ [COMPRAS] Scan finalizado. {count} reportes procesados.")

def handle_command(cmd, args, query_api):
    if cmd == "help" or cmd == "--help":
        print("\n🧬 NEURONA FACTURAS - Comandos disponibles:")
        print("   -> scan                | Escaneo automático de carpeta crudos.")
        print("   -> resumen [anio]      | Balance Ventas vs Compras.")
        print("   -> buscar <termino>    | Buscar comprobantes en DB (Proveedor/Cuit/Número).")
        print("   -> importar <AFIP|CALIM> <path> | Importación manual.")
        print("   -> sync                | Sincronizar archivos físicos y base de datos.")
        return

    if cmd == "scan":
        ejecutar_scan()

    elif cmd == "resumen":
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
                    # Nota: Usamos 'fecha' que es el nombre en el nuevo Storage
                    print(f"   - {f['fecha']} | {f['proveedor'][:25]:<25} | $ {f['monto_total']:>10,.2f}")
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
