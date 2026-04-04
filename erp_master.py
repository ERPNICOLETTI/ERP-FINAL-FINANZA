import pandas as pd
import sys
import os
import re
from datetime import datetime
from core_sistema import db_ingesta, archiver_service
from modulo_compras import storage_compras as compras
from modulo_tarjetas import storage_tarjetas as tarjetas

# ERP MASTER - v4.0 GOLDEN MASTER 🚀🧠⚖️🚀
# Orquestador Central: Idempotencia, Ingesta Híbrida y Archivado Legal.

# Configuración de salida UTF-8 para Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class ERPMaster:
    """
    Maestro de Auditoría y Procesamiento para ERP FINAL (Modo Inteligencia Centralizada)
    La única puerta de entrada es el Inbox. La única regla es el Archivado Legal.
    """
    
    def __init__(self, workspace_path):
        self.workspace = workspace_path
        self.inbox_path = os.path.join(self.workspace, 'inbox')
        self._ensure_inbox()

    def _ensure_inbox(self):
        """Garantiza la existencia del punto de entrada universal."""
        if not os.path.exists(self.inbox_path):
            os.makedirs(self.inbox_path)
            print(f"📁 [MASTER] Creada carpeta de entrada: {self.inbox_path}")

    def setup_schema(self):
        """Inicialización total de la base de datos v4.0."""
        print("💎 [MASTER] Reconstruyendo planos maestros (Golden Master v4.0)...")
        db_ingesta.initialize_all()

    def run_audit(self):
        """Ejecuta la auditoría analítica consumiendo los Storages."""
        print("\n" + "="*80)
        print(" REPORTE DE FALENCIAS ERP - v4.0 GOLDEN MASTER")
        print("="*80)

        # Auditoría Tarjetas
        from modulo_tarjetas.storage_tarjetas import get_unmatched_payway_records
        unmatched_payway = get_unmatched_payway_records()
        print("\n[!] ALERTAS TARJETAS (Cupones sin acreditar):")
        for p in unmatched_payway:
            print(f"   -> Fecha: {p['fecha_compra']} | Cupón {p['cupon']} | Monto: ${p['monto_bruto']} | NO EN BANCO")

        # Auditoría Facturación
        from modulo_compras.storage_compras import get_resumen_facturacion
        res = get_resumen_facturacion()
        print("\n[!] BALANCE FISCAL:")
        print(f"   - Ingresos (Ventas):  $ {res['monto_ventas']:,.2f}")
        print(f"   - Egresos (Compras):  $ {res['monto_compras']:,.2f}\n")

    def search(self, term):
        """Buscador 360 sobre todas las metadata_cruda indexadas."""
        print(f"\n🔍 [BÚSQUEDA 360] Resultados para '{term}':")
        results = db_ingesta.search_360(term)
        if not results:
            print("   No se encontraron resultados.")
            return
        for r in results:
            print(f"   [{r['source']}] ID:{r['record_id']} | {r['nombre']} | $ {r['monto']} | Fecha: {r['fecha']}")

    def ingest_inbox(self):
        """Procesa el contenido del inbox/ asignando parsers dinámicamente."""
        archivos = [f for f in os.listdir(self.inbox_path) if os.path.isfile(os.path.join(self.inbox_path, f))]
        if not archivos:
            print("📭 Inbox vacío. Nada que procesar.")
            return

        print(f"🚀 [MASTER] Procesando {len(archivos)} archivos en Inbox...")

        for f in archivos:
            filepath = os.path.join(self.inbox_path, f)
            f_upper = f.upper()
            print(f"\n📦 INGESTANDO: {f}")
            
            success = False
            info = {}

            try:
                # --- DESPACHADOR INTELIGENTE v4.0 ---
                
                # 1. MODULO TARJETAS
                if "PAYWAY" in f_upper and f_upper.endswith(".PDF"):
                    from modulo_tarjetas import parser_payway_liq
                    success, info = parser_payway_liq.procesar_archivo(filepath)
                
                elif "NARANJA" in f_upper and f_upper.endswith(".XLSX"):
                    from modulo_tarjetas import parser_naranja_xlsx
                    success, info = parser_naranja_xlsx.procesar_archivo(filepath)
                
                elif "LIQMENSAL" in f_upper or "PATAGONIA" in f_upper:
                    from modulo_tarjetas import parser_patagonia
                    success, info = parser_patagonia.procesar_archivo(filepath)

                # 2. MODULO COMPRAS (AFIP / CALIM / LIBRO IVA)
                elif ("AFIP" in f_upper or "VENTAS" in f_upper or "COMPRAS" in f_upper or "COMPROBANTES_CONSULTA_CSV" in f_upper) and f_upper.endswith(".CSV"):
                    from modulo_compras import importador_afip
                    success, info = importador_afip.procesar_archivo(filepath)
                
                elif "CALIM" in f_upper and f_upper.endswith(".XLSX"):
                    from modulo_compras import importador_calim
                    success, info = importador_calim.procesar_archivo(filepath)
                
                elif ("LIBRO_IVA" in f_upper or "F2051" in f_upper) and f_upper.endswith(".PDF"):
                    from modulo_compras import generador_libro_iva
                    success, info = generador_libro_iva.procesar_archivo(filepath)

                # 3. MODULO BANCOS
                elif ("CHUBUT" in f_upper or "HISTORICOS" in f_upper) and f_upper.endswith(".XLSX"):
                    from modulo_bancos import parser_chubut
                    success, info = parser_chubut.procesar_archivo(filepath)
                
                elif "CREDICOOP" in f_upper and f_upper.endswith(".XLSX"):
                    from modulo_bancos import parser_credicoop_joaquin
                    success, info = parser_credicoop_joaquin.procesar_archivo(filepath)

                elif "HIPOTECARIO" in f_upper and f_upper.endswith(".XLSX"):
                    if "USD" in f_upper:
                        from modulo_bancos import parser_hipotecario_usd
                        success, info = parser_hipotecario_usd.procesar_archivo(filepath)
                    else:
                        from modulo_bancos import parser_hipotecario
                        success, info = parser_hipotecario.procesar_archivo(filepath)
                
                else:
                    print(f"❓ [MASTER] Sin parser para: {f}")
                    continue

                # --- POST-PROCESAMIENTO: ARCHIVADO Y TRAZABILIDAD ---
                if success and info:
                    new_path = archiver_service.archivar_documento(
                        filepath, 
                        modulo=info['modulo'], 
                        anio=info['anio'], 
                        mes=info['mes'], 
                        entidad=info['entidad']
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
                        
                        print(f"✅ ÉXITO: {f} archivado en {new_path}")
                else:
                    print(f"⚠️ RECHAZADO: {f} (Posible duplicado o error de parser)")

            except Exception as e:
                print(f"❌ ERROR CRÍTICO [{f}]: {e}")

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
        print("\n💎 ERP Master v4.0 - GOLDEN MASTER")
        print("Comandos:")
        print("  --setup    | Reconstruye la DB desde cero (Planos Perfectos).")
        print("  --ingest   | Consume todo lo que haya en la carpeta /inbox/.")
        print("  --audit    | Reporte analítico de falencias.")
        print("  --search <T>| Búsqueda 360 (indexa contenido JSON).")
