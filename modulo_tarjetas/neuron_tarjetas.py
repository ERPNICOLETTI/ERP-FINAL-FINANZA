import os
import pandas as pd
from . import storage_tarjetas as storage
from . import parser_payway_liq, parser_patagonia, parser_naranja_xlsx

# NEURONA TARJETAS - v4.0 GOLDEN MASTER 💳🧠🔍⚖️
# Detective de Liquidaciones. Ingesta centralizada en erp_master.py.

def detectar_y_procesar(file_path):
    """Detecta el tipo de archivo por contenido y lanza el parser v4.0."""
    if not os.path.exists(file_path):
        return False, {"error": "Archivo no encontrado"}
        
    ext = os.path.splitext(file_path)[1].lower()
    basename = os.path.upper(os.path.basename(file_path))
    
    # 1. PRUEBA PDF (Payway o Patagonia)
    if ext == '.pdf' or 'PDF' in basename:
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                first_page_text = (pdf.pages[0].extract_text() or "").lower()
                
                if "prisma" in first_page_text or "establec" in first_page_text:
                    print(f"🔍 [DETECTIVE] Identificado: PAYWAY PDF")
                    return parser_payway_liq.procesar_archivo(file_path)
                
                if "banco patagonia" in first_page_text or "patagonia 365" in first_page_text:
                    print(f"🔍 [DETECTIVE] Identificado: PATAGONIA 365 PDF")
                    return parser_patagonia.procesar_archivo(file_path)
        except Exception as e:
            return False, {"error": f"Error en Detective PDF: {e}"}

    # 2. PRUEBA EXCEL (Naranja)
    if ext in ['.xlsx', '.xls']:
        try:
            df_peek = pd.read_excel(file_path, nrows=5)
            content_str = df_peek.to_string().lower()
            if "naranja" in content_str or "monto bruto" in content_str:
                print(f"🔍 [DETECTIVE] Identificado: NARANJA XLSX")
                return parser_naranja_xlsx.procesar_archivo(file_path)
        except:
            pass

    return False, {"error": "No se reconoció el formato de tarjeta"}


def ejecutar(cmd, args):
    """Entry point para el CLI del Cerebro (Módulo Tarjetas) v4.0."""
    
    if cmd in ["help", "--help"]:
        print("\n🧬 NEURONA TARJETAS - Comandos disponibles:")
        print("   -> resumen [anio]      | Consolidado de todas las liquidaciones.")
        print("   -> audit               | Cruce de ventas diarias vs depósitos.")
        print("   -> cupon <id/numero>   | Detalle técnico de un cupón.")
        print("\n💡 La ingesta es automática: suelta los archivos en /inbox/")
        return

    if cmd == "resumen":
        anio = args[0] if len(args) > 0 else "2026"
        print(f"💎 CONSULTANDO RESUMEN TARJETAS ({anio}) - Repository Pattern...")
        res = storage.get_resumen_tarjetas(anio)
        if res:
            print("-" * 85)
            print(f"{'FUENTE':<15} | {'TIPO':<10} | {'CANT':<5} | {'MONTO BRUTO':<15} | {'NETO REAL':<15}")
            print("-" * 85)
            for l in res['liquidaciones']:
                print(f"{l['fuente']:<15} | {l['tipo']:<10} | {l['cantidad']:<5} | ${l['bruto']:>14,.2f} | ${l['neto']:>14,.2f}")
            print("-" * 85 + "\n")
    
    elif cmd == "audit":
        print("💎 EJECUTANDO AUDITORIA 360 (Ventas vs Depósitos)...")
        # Aquí se llamaría a la lógica de conciliación que ya usa Storages
        from . import conciliacion_tarjetas
        conciliacion_tarjetas.ejecutar_auditoria_completa()

    elif cmd == "cupon":
        if len(args) < 1:
            print("Uso: python cerebro.py tarjetas cupon <ID_O_NUMERO>")
        else:
            cid = args[0]
            res = storage.get_cupon_detalle(cid)
            if res:
                print(f"\n💎 DETALLE TÉCNICO DEL CUPÓN")
                print("-" * 40)
                for k, v in res.items():
                    if k != 'metadata_cruda':
                        print(f"   {k.replace('_', ' ').capitalize():<15}: {v}")
                print("-" * 40 + "\n")
            else:
                print(f"❌ Cupón {cid} no encontrado en la base de datos.")
    
    else:
        print(f"Comando '{cmd}' no reconocido en el área Tarjetas.")
        print("Usa 'python cerebro.py tarjetas help' para ver la lista.")
