import pandas as pd
import sys
import os
import re
from datetime import datetime
from core_sistema import db_ingesta, archiver_service
from modulo_compras import storage_compras as compras
from modulo_tarjetas import storage_tarjetas as tarjetas

# ERP MASTER - v4.5 GOLDEN MASTER 🚀🧠⚖️🚀
# Orquestador Central: Idempotencia, Ingesta Híbrida y Archivado Legal.

# Configuración de salida UTF-8 para Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def detectar_parser_pdf(filepath):
    """Detecta el parser correspondiente leyendo el contenido del PDF."""
    text = ""
    try:
        import PyPDF2
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:2]:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
    except Exception as e:
        print(f"⚠️ PyPDF2 falló para {os.path.basename(filepath)}, intentando pdfplumber: {e}")
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages[:2]:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted
        except Exception as ex:
            print(f"⚠️ pdfplumber también falló para {os.path.basename(filepath)}: {ex}")

    # Fallback de OCR rápido si no hay suficiente texto legible
    if not text or len(re.sub(r'[^a-zA-Z0-9]', '', text)) < 50:
        try:
            import pypdfium2 as pdfium
            import pytesseract
            
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            tessdata_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'core_sistema', 'tessdata'))
            os.environ['TESSDATA_PREFIX'] = tessdata_dir
            
            doc = pdfium.PdfDocument(filepath)
            try:
                if len(doc) > 0:
                    page = doc[0]
                    bitmap = page.render(scale=2)
                    pil_img = bitmap.to_pil()
                    ocr_result = pytesseract.image_to_string(pil_img, lang='spa+eng')
                    if ocr_result:
                        text += ocr_result
            finally:
                doc.close()
        except Exception as ocr_err:
            pass

    if not text:
        return None

    text_upper = text.upper()
    
    if "PAYWAY" in text_upper or "LA POS" in text_upper or "LIQUIDACION DE PAGO" in text_upper:
        return "PAYWAY"
    elif "LIBRO IVA" in text_upper or "LIBRO DE IVA" in text_upper or "F2051" in text_upper:
        return "LIBRO_IVA"
    elif "HIPOTECARIO" in text_upper and "VISA" in text_upper:
        return "VISA_HIPOTECARIO"
    elif ("GALICIA" in text_upper or "30-50000173-5" in text_upper) and "VISA" in text_upper:
        return "VISA_GALICIA"
    elif ("GALICIA" in text_upper or "30-50000173-5" in text_upper) and "MASTERCARD" in text_upper:
        return "MASTERCARD_GALICIA"
    elif "NARANJA" in text_upper:
        return "TARJETA_NARANJA"
    elif "PATAGONIA 365" in text_upper or "PATAGONIA365" in text_upper:
        return "PATAGONIA365_PDF"
        
    return None

def detectar_parser_excel(filepath):
    """Detecta el parser correspondiente leyendo las primeras celdas del Excel."""
    import pandas as pd
    try:
        df = pd.read_excel(filepath, nrows=15, header=None)
        content = " ".join(df.astype(str).values.flatten()).upper()
        
        if "CREDICOOP" in content or "COOPERATIVO" in content:
            return "CREDICOOP"
        elif "CHUBUT" in content or "PROVINCIA DEL CHUBUT" in content:
            return "CHUBUT"
        elif "HIPOTECARIO" in content:
            if "USD" in filepath.upper() or "CA_USD" in content or "DOLARES" in content or "DÓLARES" in content:
                return "HIPOTECARIO_USD"
            return "HIPOTECARIO_PESOS"
        elif "NARANJA" in content:
            return "NARANJA"
        elif "CALIM" in content or "FACTURAS DE COMPRA" in content:
            return "CALIM"
    except Exception as e:
        print(f"⚠️ Error detectando contenido de Excel {os.path.basename(filepath)}: {e}")
    return None

class ERPMaster:
    """
    Maestro de Auditoría y Procesamiento para ERP FINAL (Modo Inteligencia Centralizada)
    La única puerta de entrada es el Inbox. La única regla es el Archivado Legal.
    """
    
    def __init__(self, workspace_path):
        self.workspace = workspace_path
        self.setup_inbox_and_archives()

    def setup_inbox_and_archives(self):
        """Auto-genera la infraestructura descentralizada v4.6 (Aislamiento Físico)."""
        modulos = ['compras', 'tarjetas', 'bancos', 'pagos']
        self.inbox_paths = []
        self.crudos_paths = []
        self.archivos_paths = []

        for mod in modulos:
            base_mod = os.path.join(self.workspace, f'modulo_{mod}')
            self.inbox_paths.append(os.path.join(base_mod, f'inbox_{mod}'))
            self.crudos_paths.append(os.path.join(base_mod, f'crudos_{mod}'))
            self.archivos_paths.append(os.path.join(base_mod, f'archivos_{mod}'))

        for lst in [self.inbox_paths, self.crudos_paths, self.archivos_paths]:
            for p in lst:
                os.makedirs(p, exist_ok=True)

    def setup_schema(self):
        """Inicialización total de la base de datos v4.0."""
        print("💎 [MASTER] Reconstruyendo planos maestros (Golden Master v4.0)...")
        db_ingesta.initialize_all()

    def run_audit(self):
        """Ejecuta la auditoría analítica consumiendo los Storages."""
        print("\n" + "="*80)
        print(" REPORTE DE FALENCIAS ERP - v4.0 GOLDEN MASTER")
        print("="*80)

        from modulo_tarjetas.storage_tarjetas import get_unmatched_payway_records
        unmatched_payway = get_unmatched_payway_records()
        print("\n[!] ALERTAS TARJETAS (Cupones sin acreditar):")
        for p in unmatched_payway:
            print(f"   -> Fecha: {p['fecha_compra']} | Cupón {p['cupon']} | Monto: ${p['monto_bruto']} | NO EN BANCO")

        from modulo_compras.storage_compras import get_resumen_facturacion
        res = get_resumen_facturacion()
        print("\n[!] BALANCE FISCAL:")
        print(f"   - Ingresos (Ventas):  $ {res['monto_ventas']:,.2f}")
        print(f"   - Egresos (Compras):  $ {res['monto_compras']:,.2f}\n")

    def search(self, term):
        """Buscador 360 sobre todas las metadata indexadas."""
        print(f"\n🔍 [BÚSQUEDA 360] Resultados para '{term}':")
        results = db_ingesta.search_360(term)
        if not results:
            print("   No se encontraron resultados.")
            return
        for r in results:
            print(f"   [{r['source']}] ID:{r['record_id']} | {r['nombre']} | $ {r['monto']} | Fecha: {r['fecha']}")

    def ingest_inbox(self):
        """Procesa el contenido de la zona Inbox y lo traslada a Crudos (Histórico) o Archivos (Bóveda)."""
        archivos_totales = 0
        for inbox_path in self.inbox_paths:
            if not os.path.exists(inbox_path): continue
            
            # Recolectar archivos de forma recursiva para soportar carpetas por fuente
            archivos_encontrados = []
            for root, dirs, files in os.walk(inbox_path):
                for f in files:
                    filepath = os.path.join(root, f)
                    archivos_encontrados.append((f, filepath))
                    
            if not archivos_encontrados: continue
            
            print(f"\n🚀 [MASTER] Procesando {len(archivos_encontrados)} archivos en {os.path.basename(inbox_path)}...")
            archivos_totales += len(archivos_encontrados)

            for f, filepath in archivos_encontrados:
                f_upper = f.upper()
                print(f"\n📦 INGESTANDO: {f}")
                
                success = False
                info = {}

                try:
                    # --- DESPACHADOR INTELIGENTE v6.0 ---
                    
                    # 0. MODULO PAGOS (Nuevo Procesador Autónomo v5.2)
                    if "INBOX_PAGOS" in inbox_path.upper():
                        from modulo_pagos import logic_pagos
                        logic_pagos.procesar_inbox_pagos(inbox_path)
                        # Este proceso es autónomo, saltamos al siguiente archivo
                        continue

                    # Determinar parser mediante detección inteligente de contenido
                    detected_type = None
                    if f_upper.endswith(".PDF"):
                        detected_type = detectar_parser_pdf(filepath)
                    elif f_upper.endswith((".XLSX", ".XLS")):
                        detected_type = detectar_parser_excel(filepath)

                    # 1. MODULO TARJETAS
                    if detected_type == "PAYWAY" or ("PAYWAY" in f_upper and f_upper.endswith(".PDF")):
                        from modulo_tarjetas.lectores import lector_payway_liq
                        success, info = lector_payway_liq.procesar_archivo(filepath)
                    
                    elif detected_type == "NARANJA" or ("NARANJA" in f_upper and f_upper.endswith(".XLSX")):
                        from modulo_tarjetas.lectores import lector_naranja_xlsx
                        success, info = lector_naranja_xlsx.procesar_archivo(filepath)
                    
                    elif detected_type == "PATAGONIA" or ("LIQMENSAL" in f_upper or "PATAGONIA" in f_upper):
                        from modulo_tarjetas.lectores import lector_patagonia
                        success, info = lector_patagonia.procesar_archivo(filepath)

                    # 2. MODULO COMPRAS (AFIP / CALIM / LIBRO IVA)
                    elif ("AFIP" in f_upper or "VENTAS" in f_upper or "COMPRAS" in f_upper or "COMPROBANTES_CONSULTA_CSV" in f_upper) and f_upper.endswith(".CSV"):
                        from modulo_compras import importador_afip
                        success, info = importador_afip.procesar_archivo(filepath)
                    
                    elif detected_type == "CALIM" or (("CALIM" in f_upper or "FACTURAS DE COMPRA" in f_upper) and f_upper.endswith(".XLSX")):
                        from modulo_compras import importador_calim
                        success, info = importador_calim.procesar_archivo(filepath)
                    
                    elif detected_type == "LIBRO_IVA" or (("LIBRO_IVA" in f_upper or "F2051" in f_upper) and f_upper.endswith(".PDF")):
                        from modulo_compras import generador_libro_iva
                        success, info = generador_libro_iva.procesar_archivo(filepath)

                    # 3. MODULO BANCOS
                    elif detected_type == "CHUBUT" or (("CHUBUT" in f_upper or "HISTORICOS" in f_upper) and f_upper.endswith(".XLSX")):
                        from modulo_bancos.lectores import lector_chubut
                        success, info = lector_chubut.procesar_archivo(filepath)
                    
                    elif detected_type == "CREDICOOP" or ("CREDICOOP" in f_upper and f_upper.endswith(".XLSX")):
                        from modulo_bancos.lectores import lector_credicoop_joaquin
                        success, info = lector_credicoop_joaquin.procesar_archivo(filepath)

                    elif detected_type == "HIPOTECARIO_USD" or (detected_type == "HIPOTECARIO" and "USD" in f_upper) or ("HIPOTECARIO" in f_upper and "USD" in f_upper and f_upper.endswith(".XLSX")):
                        from modulo_bancos.lectores import lector_hipotecario_usd
                        success, info = lector_hipotecario_usd.procesar_archivo(filepath)

                    elif detected_type == "HIPOTECARIO_PESOS" or ("HIPOTECARIO" in f_upper and f_upper.endswith(".XLSX")):
                        from modulo_bancos.lectores import lector_hipotecario
                        success, info = lector_hipotecario.procesar_archivo(filepath)
                            
                    elif detected_type == "VISA_HIPOTECARIO" or (("HIPOTECARIO" in f_upper or "HIPOTECARIO" in filepath.replace('\\', '/').upper() or "ULTIMALIQUIDACION" in f_upper or "LIQUIDACION" in f_upper) and f_upper.endswith(".PDF") and "GALICIA" not in f_upper and detected_type != "VISA_GALICIA"):
                        from modulo_bancos.lectores import lector_visa_hipotecario
                        success, info = lector_visa_hipotecario.procesar_archivo(filepath)

                    elif detected_type == "VISA_GALICIA" or (("GALICIA" in f_upper or "GALICIA" in filepath.replace('\\', '/').upper()) and f_upper.endswith(".PDF") and "MASTERCARD" not in f_upper):
                        from modulo_bancos.lectores import lector_visa_galicia
                        success, info = lector_visa_galicia.procesar_archivo(filepath)

                    elif detected_type == "MASTERCARD_GALICIA" or (("GALICIA" in f_upper or "GALICIA" in filepath.replace('\\', '/').upper()) and f_upper.endswith(".PDF") and "MASTERCARD" in f_upper):
                        from modulo_bancos.lectores import lector_mastercard_galicia
                        success, info = lector_mastercard_galicia.procesar_archivo(filepath)

                    elif detected_type == "TARJETA_NARANJA" or ("NARANJA" in f_upper and f_upper.endswith(".PDF")):
                        from modulo_bancos.lectores import lector_naranja_pdf
                        success, info = lector_naranja_pdf.procesar_archivo(filepath)

                    elif detected_type == "PATAGONIA365_PDF" or ("P365" in f_upper and f_upper.endswith(".PDF")):
                        from modulo_bancos.lectores import lector_patagonia_pdf
                        success, info = lector_patagonia_pdf.procesar_archivo(filepath)
                    
                    else:
                        print(f"❓ [MASTER] Sin parser compatible para: {f}")
                        continue

                    # --- POST-PROCESAMIENTO: ARCHIVADO Y TRAZABILIDAD ---
                    if success and info:
                        new_path = archiver_service.archivar_documento(
                            filepath, 
                            modulo=info['modulo'], 
                            anio=info['anio'], 
                            mes=info['mes'], 
                            entidad=info['entidad'],
                            use_vault=False,  # Los reportes masivos van al Histórico (Crudos)
                            overwrite=True    # Evitamos sufijos en reportes masivos
                        )
                        
                        if new_path:
                            # Actualizar puntero físico en la tabla correspondiente
                            if info['db_table'] == 'liquidaciones_tarjetas':
                                tarjetas.update_record_path(info.get('id_insertado', 0), new_path)
                            elif info['db_table'] == 'facturas':
                                compras.update_record_path(info.get('id_insertado', 0), new_path)
                            elif info['db_table'] == 'libroiva':
                                compras.update_record_path(0, new_path, table="libroiva") # Periodo es unique
                            elif info['db_table'] == 'bancos_movimientos':
                                from modulo_bancos import storage_bancos
                                storage_bancos.update_record_path(info.get('id_insertado', 0), new_path)
                            
                            print(f"✅ ÉXITO: {f} archivado jerárquicamente en {new_path}")
                    else:
                        print(f"⚠️ RECHAZADO o YA EXISTE: {f}")
                        # Si es un duplicado idéntico por hash, lo eliminamos del inbox
                        if os.path.exists(filepath):
                            os.remove(filepath)
                            print(f"🧹 Duplicado por Hash eliminado de Inbox: {f}")

                except Exception as e:
                    print(f"❌ ERROR CRÍTICO [{f}]: {e}")
                    
        if archivos_totales == 0:
            print("📭 Los inboxes descentralizados están vacíos. Nada que procesar.")

if __name__ == "__main__":
    WORKSPACE = os.path.dirname(os.path.abspath(__file__))
    master = ERPMaster(WORKSPACE)
    
    if "--setup" in sys.argv:
        master.setup_schema()
    elif "--audit" in sys.argv:
        master.run_audit()
    elif "--search" in sys.argv:
        idx = sys.argv.index("--search")
        if idx + 1 < len(sys.argv): master.search(sys.argv[idx + 1])
    elif "--ingest" in sys.argv:
        master.ingest_inbox()
    else:
        print("\n💎 ERP Master v4.5 - GOLDEN MASTER")
        print("Comandos:")
        print("  --setup    | Reconstruye la DB desde cero (Planos Perfectos).")
        print("  --ingest   | Consume inboxes de forma descentralizada.")
        print("  --audit    | Reporte analítico de falencias.")
        print("  --search <T>| Búsqueda 360 (indexa contenido JSON).")
