import os
import pandas as pd
from . import storage_compras as storage
from . import importador_afip, importador_calim

# NEURONA COMPRAS - v4.0 GOLDEN MASTER 🧾🧠🔍⚖️
# Especialista en Facturación (ARCA/AFIP, CALIM). Ingesta centralizada en erp_master.py.

def detectar_y_procesar(file_path):
    """Detecta el tipo de reporte fiscal y lanza el importador v4.0."""
    if not os.path.exists(file_path):
        return False, {"error": "Archivo no encontrado"}
        
    ext = os.path.splitext(file_path)[1].lower()
    basename = os.path.basename(file_path).upper()
    
    # 1. AFIP (CSV)
    if ext == '.csv':
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                header = f.readline().lower()
                if "fecha de emisión" in header or "cuit" in header:
                    print(f"🔍 [DETECTIVE] Identificado: REPORTE AFIP (CSV)")
                    return importador_afip.procesar_archivo(file_path)
        except:
            pass

    # 2. CALIM (EXCEL)
    elif ext in ['.xlsx', '.xls']:
        try:
            df_peek = pd.read_excel(file_path, nrows=5, engine='calamine')
            content_str = df_peek.to_string().lower()
            if "total" in content_str and ("proveedor" in content_str or "cuil/cuit" in content_str):
                print(f"🔍 [DETECTIVE] Identificado: REPORTE CALIM (EXCEL)")
                return importador_calim.procesar_archivo(file_path)
        except:
            pass
            
    # 3. LIBRO IVA (PDF) - Nuevo en v4.0
    elif ext == '.pdf' or 'PDF' in basename:
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = pdf.pages[0].extract_text().lower()
                if "libro iva" in text or "f.2051" in text or "período" in text:
                    print(f"🔍 [DETECTIVE] Identificado: LIBRO IVA PDF (F.2051)")
                    from . import generador_libro_iva
                    return generador_libro_iva.procesar_archivo(file_path)
        except:
            pass

    return False, {"error": "No se reconoció el reporte fiscal"}


def ejecutar(cmd, args):
    """Entry point para el CLI del Cerebro (Módulo Compras) v4.0."""
    
    if cmd in ["help", "--help"]:
        print("\n🧬 NEURONA COMPRAS - Comandos disponibles:")
        print("   -> resumen [anio]      | Balance Ventas vs Compras.")
        print("   -> buscar <termino>    | Buscar comprobantes (Proveedor/Cuit/Número).")
        print("\n💡 La ingesta es automática: suelta los archivos en /inbox/")
        return

    if cmd == "resumen":
        anio = args[0] if len(args) > 0 else "2026"
        print(f"💎 CONSULTANDO RESUMEN FACTURACION ({anio}) - Repository Pattern...")
        res = storage.get_resumen_facturacion(anio)
        if res:
            print(f"\n   - Ingresos (Ventas):  $ {res['monto_ventas']:,.2f}")
            print(f"   - Egresos (Compras):  $ {res['monto_compras']:,.2f}\n")
    
    elif cmd == "buscar":
        if len(args) < 1:
            print("Uso: python cerebro.py compras buscar <TERMINO>")
        else:
            termino = args[0]
            print(f"💎 BUSCANDO COMPROBANTES: {termino}...")
            res = storage.buscar_facturas(termino)
            if res:
                print("-" * 60)
                print(f"{'FECHA':<12} | {'PROVEEDOR':<25} | {'MONTO':<12}")
                print("-" * 60)
                for f in res[:10]:
                    print(f"{f['fecha']:<12} | {f['proveedor'][:25]:<25} | $ {f['monto_total']:>10,.2f}")
                print("-" * 60 + "\n")
            else:
                print(f"❌ No se encontraron comprobantes para '{termino}'.")
    
    else:
        print(f"Comando '{cmd}' no reconocido en el área Compras.")
        print("Usa 'python cerebro.py compras help' para ver la lista.")
