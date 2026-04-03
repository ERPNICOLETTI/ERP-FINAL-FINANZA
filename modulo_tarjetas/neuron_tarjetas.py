import sys
import os
import glob
import shutil
import pandas as pd
from . import storage_tarjetas as storage
from . import parser_payway_liq, parser_patagonia, parser_naranja_xlsx

# NEURONA TARJETAS - Detective de Liquidaciones 💳🧠🔍
# Esta neurona identifica archivos crudos y decide qué parser usar.

def detectar_y_procesar(file_path):
    """Detecta el tipo de archivo por contenido (blind to extension) y lanza el parser."""
    ext = os.path.splitext(file_path)[1].lower()
    basename = os.path.basename(file_path).upper()
    
    # --- PRUEBA PDF (O ARCHIVOS PESADOS SIN EXTENSIÓN) ---
    # Si es PDF o no tiene extensión o dice PDF en el nombre:
    if ext == '.pdf' or not ext or 'PDF' in basename:
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                first_page_text = (pdf.pages[0].extract_text() or "").lower()
                
                # 1. ¿ES PAYWAY? (Prisma / Liquidación de Comercio / Resumen)
                is_payway = any(k in first_page_text for k in ["resumen mensual", "prisma medios", "establec", "liquid", "pago"])
                if is_payway:
                    print(f"🔍 [DETECTIVE] Identificado: PAYWAY PDF (Prisma)")
                    parser_payway_liq.parse_payway_liq(file_path)
                    return True
                
                # 2. ¿ES PATAGONIA 365? (Banco Patagonia)
                if "banco patagonia" in first_page_text or "patagonia 365" in first_page_text:
                    print(f"🔍 [DETECTIVE] Identificado: PATAGONIA 365 PDF")
                    parser_patagonia.parse_patagonia_365(file_path)
                    return True
        except Exception as e:
            print(f"❌ Error interno en Detective PDF: {e}")

    # --- PRUEBA CSV / TEXTO ---
    try:
        with open(file_path, 'r', encoding='latin1', errors='ignore') as f:
            head = f.read(1000).lower()
            if "pago" in head and "marca" in head and "bruto" in head:
                print(f"🔍 [DETECTIVE] Identificado: PAYWAY CSV")
                parser_payway_liq.parse_payway_liq(file_path)
                return True
    except Exception as e:
        pass

    # --- PRUEBA EXCEL ---
    if ext in ['.xlsx', '.xls']:
        try:
            df_peek = pd.read_excel(file_path, nrows=5)
            content_str = df_peek.to_string().lower()
            if "naranja" in content_str or "monto bruto" in content_str:
                print(f"🔍 [DETECTIVE] Identificado: NARANJA XLSX")
                parser_naranja_xlsx.parse_naranja_xlsx(file_path)
                return True
        except Exception as e:
            pass

    print(f"⚠️ [DETECTIVE] No se pudo identificar el archivo: {os.path.basename(file_path)}")
    return False

def ejecutar_scan():
    """Escanea la carpeta crudos, detecta e ingesta."""
    path_crudos = os.path.join(os.path.dirname(__file__), "crudos")
    path_procesados = os.path.join(path_crudos, "procesados")
    
    if not os.path.exists(path_procesados):
        os.makedirs(path_procesados)
        
    print(f"🚀 [TARJETAS] Iniciando escaneo de crudos en {path_crudos}...")
    archivos = [f for f in os.listdir(path_crudos) if os.path.isfile(os.path.join(path_crudos, f))]
    
    count = 0
    for f in archivos:
        if f == ".gitkeep": continue
        full_path = os.path.join(path_crudos, f)
        if detectar_y_procesar(full_path):
            # shutil.move(full_path, os.path.join(path_procesados, f)) # Desactivado temporalmente a pedido del usuario
            count += 1
            
    print(f"✅ [TARJETAS] Scan finalizado. {count} archivos procesados.")

def handle_command(cmd, args, query_api):
    if cmd == "help" or cmd == "--help":
        print("\n🧬 NEURONA TARJETAS - Comandos disponibles:")
        print("   -> scan                | Escaneo automático de carpeta crudos.")
        print("   -> resumen [anio]      | Consolidado de todas las liquidaciones.")
        print("   -> importar <src> <p>  | Importar PDF/CSV (PAYWAY, PATAGONIA365, NARANJA).")
        print("   -> audit               | Cruce de ventas diarias vs depósitos.")
        print("   -> cupon <id/numero>   | Detalle técnico de un cupón.")
        return

    if cmd == "scan":
        ejecutar_scan()

    elif cmd == "resumen":
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
                for k, v in res.items():
                    if k != 'metadata':
                        print(f"   - {k.replace('_', ' ').capitalize()}: {v}")
            else:
                print(f"ERROR: {res.get('error') if res else 'Cupón no encontrado'}")
    else:
        print(f"Comando '{cmd}' no reconocido en el área Tarjetas.")
        print("Usa 'python cerebro.py tarjetas help' para ver la lista.")
