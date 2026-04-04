import os
from . import storage_bancos as storage
from . import parser_chubut, parser_hipotecario_usd

# NEURONA BANCOS - v4.0 GOLDEN MASTER 🏦🧠🔍⚖️
# Especialista en Tesorería. La ingesta es ahora centralizada en erp_master.py.

def detectar_y_procesar(file_path):
    """Detecta el banco por contenido y lanza el parser adecuado v4.0."""
    # Esta función puede ser llamada por el Orquestador Global
    if not os.path.exists(file_path):
        return False, {"error": "Archivo no encontrado"}

    content_str = ""
    try:
        # Intento de lectura rápida para identificación
        import pandas as pd
        df_peek = pd.read_excel(file_path, nrows=10, header=None)
        content_str = df_peek.to_string().lower()
    except Exception as e:
        return False, {"error": f"Error leyendo archivo para detección: {e}"}
        
    if "chubut" in content_str or "tipo y nº de cuenta" in content_str:
        print(f"🔍 [DETECTIVE] Identificado: BANCO CHUBUT")
        return parser_chubut.procesar_archivo(file_path)
    
    if "hipotecario" in content_str or "ca_usd" in content_str or "ca dolares" in content_str:
        print(f"🔍 [DETECTIVE] Identificado: BANCO HIPOTECARIO")
        return parser_hipotecario_usd.procesar_archivo(file_path)
            
    return False, {"error": "No se reconoció el formato bancario"}


def ejecutar(cmd, args):
    """Entry point para el CLI del Cerebro (Módulo Bancos)."""
    
    if cmd in ["help", "--help"]:
        print("\n🧬 NEURONA BANCOS - Comandos disponibles:")
        print("   -> sueldos [anio]           | Listado de haberes y sueldos detectados.")
        print("   -> audit                    | Cruce de Bancos vs Tarjetas.")
        print("\n💡 La ingesta es automática: suelta los archivos en /inbox/")
        return

    if cmd == "sueldos":
        anio = args[0] if len(args) > 0 else "2026"
        print(f"💎 CONSULTANDO SUELDOS (HABERES) - v4.0 Repository Pattern...")
        res = storage.get_sueldos(anio)
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
        print("Módulo de Auditoría Bancaria (Cruce 360)... próximamente.")
    
    else:
        print(f"Comando '{cmd}' no reconocido en el área Bancos.")
        print("Usa 'python cerebro.py bancos help' para ver la lista.")
