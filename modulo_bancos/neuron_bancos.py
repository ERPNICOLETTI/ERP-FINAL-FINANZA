import os
import shutil
import pandas as pd
from . import storage_bancos as storage
from . import parser_chubut, parser_hipotecario_usd

# NEURONA BANCOS - Especialista en Tesorería 🏦🧠🔍

def detectar_y_procesar(file_path):
    """Detecta el banco por contenido y lanza el parser adecuado."""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in ['.xlsx', '.xls']:
        try:
            # Peek al contenido
            df_peek = pd.read_excel(file_path, nrows=10, header=None)
            content_str = df_peek.to_string().lower()
            
            if "chubut" in content_str or "tipo y nº de cuenta" in content_str:
                print(f"🔍 [DETECTIVE] Identificado: BANCO CHUBUT")
                parser_chubut.parse_chubut_excel(file_path)
                return True
            
            if "hipotecario" in content_str or "ca_usd" in content_str or "ca dolares" in content_str:
                print(f"🔍 [DETECTIVE] Identificado: BANCO HIPOTECARIO (USD)")
                parser_hipotecario_usd.parse_hipotecario_usd(file_path)
                return True
                
        except Exception as e:
            print(f"⚠️ Error en detección: {e}")
            
    print(f"⚠️ [DETECTIVE] No se pudo identificar el banco en: {os.path.basename(file_path)}")
    return False

def ejecutar_scan():
    """Escanea la carpeta crudos de bancos y procesa lo nuevo."""
    path_crudos = os.path.join(os.path.dirname(__file__), "crudos")
    path_procesados = os.path.join(path_crudos, "procesados")
    
    if not os.path.exists(path_procesados):
        os.makedirs(path_procesados)
        
    print(f"🚀 [BANCOS] Iniciando escaneo de extractos en {path_crudos}...")
    archivos = [f for f in os.listdir(path_crudos) if os.path.isfile(os.path.join(path_crudos, f))]
    
    count = 0
    for f in archivos:
        if f == ".gitkeep": continue
        full_path = os.path.join(path_crudos, f)
        if detectar_y_procesar(full_path):
            shutil.move(full_path, os.path.join(path_procesados, f))
            count += 1
            
    print(f"✅ [BANCOS] Scan finalizado. {count} extractos procesados.")

    if cmd == "help" or cmd == "--help":
        print("\n🧬 NEURONA BANCOS - Comandos disponibles:")
        print("   -> scan                     | Escaneo automático de carpeta crudos.")
        print("   -> importar <BANCO> <path>  | Importación manual (CHUBUT, HIPOTECARIO).")
        print("   -> sueldos [anio]           | Listado de haberes y sueldos detectados.")
        print("   -> audit                    | Cruce de Bancos vs Tarjetas.")
        return

    if cmd == "scan":
        ejecutar_scan()

    elif cmd == "importar":
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
        else:
            print("❌ No se encontraron movimientos de sueldos para el periodo indicado.\n")
    
    elif cmd == "audit":
        print("Módulo de Auditoría Bancaria (Cruce de extractos vs Ventas)... próximamente.")
    
    else:
        print(f"Comando '{cmd}' no reconocido en el área Bancos.")
        print("Usa 'python cerebro.py bancos help' para ver la lista.")
