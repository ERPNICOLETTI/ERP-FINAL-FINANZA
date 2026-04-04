import pandas as pd
import sys
import os
import re
from datetime import datetime, timedelta
from core_sistema import db_ingesta, archiver_service
from modulo_compras import storage_compras as compras
from modulo_tarjetas import storage_tarjetas as tarjetas

# Configuración de salida UTF-8 para Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class ERPMaster:
    """
    Maestro de Auditoría y Procesamiento para ERP FINAL (Modo Inteligencia Centralizada)
    Consume servicios de dominio para realizar auditorías automáticas y búsquedas.
    """
    
    def __init__(self, workspace_path):
        self.workspace = workspace_path

    def setup_schema(self):
        """DELEGADO: Llama al nuevo sistema de inicialización modular."""
        db_ingesta.initialize_all()

    def run_audit(self):
        """Cruza los datos consumiendo servicios de Storage (Fase 1 Desacoplada)."""
        
        print("\n" + "="*80)
        print(" REPORTE DE FALENCIAS ERP (MOTOR ANALÍTICO)")
        print("="*80)

        # 1. Auditoría Payway: Cupones que no hicieron match con movimientos bancarios
        unmatched_payway = tarjetas.get_unmatched_payway_records()
        
        print("\n[!] ALERTAS PAYWAY (Cupones sin acreditar en banco):")
        for p in unmatched_payway:
            # Nota: Usamos 'fecha_compra' que es como se llama en el nuevo Storage
            print(f"   -> Fecha: {p['fecha_compra']} | Cupón {p['cupon']} | Monto bruto: ${p['monto_bruto']} | NO ESTÁ EN BANCO")

        # 2. Facturas Huérfanas (Están en sistema pero no archivadas, o viceversa)
        pending_fac = compras.get_facturas_pendientes_archivo()
        
        print("\n[!] FACTURAS PENDIENTES DE ARCHIVAR/DISCREPANCIAS CALIM vs ARCA:")
        for f in pending_fac:
            msg = []
            if f['status'] == 'SOLO_AFIP': msg.append("SÓLO EN ARCA")
            elif f['status'] == 'SOLO_CALIM': msg.append("SÓLO EN CALIM")
            print(f"   -> FC {f['numero_completo']} | Prov: {f['proveedor'][:20]} | Estado: {f['status']} | [{', '.join(msg) if msg else 'NORMAL'}]")

    def search(self, term):
        """Buscador 360 usando el servicio de Core Ingesta"""
        print(f"\n[BÚSQUEDA 360] Resultados para '{term}':")
        results = db_ingesta.search_360(term)
        
        if not results:
            print("   No se encontraron resultados.")
            return

        for r in results:
            print(f"   [{r['source']}] ID:{r['record_id']} | {r['nombre']} | $ {r['monto']} | Fecha: {r['fecha']} | Info: {r['extra']}")

    def ingest_inbox(self):
        """
        Bucle de Ingesta Inteligente (Phase 3):
        Escanea 'inbox/', procesa con el parser adecuado y archiva legalmente.
        """
        inbox_path = os.path.join(self.workspace, 'inbox')
        if not os.path.exists(inbox_path):
            os.makedirs(inbox_path)
            print(f"📁 Creada carpeta de entrada: {inbox_path}")
            return

        archivos = [f for f in os.listdir(inbox_path) if os.path.isfile(os.path.join(inbox_path, f))]
        if not archivos:
            print("📭 Inbox vacío. Nada que procesar.")
            return

        print(f"🚀 Iniciando procesamiento de {len(archivos)} archivos en Inbox...")

        for f in archivos:
            filepath = os.path.join(inbox_path, f)
            f_upper = f.upper()
            print(f"\n📦 Procesando: {f}")
            
            success = False
            info = {}

            # --- ENRUTAMIENTO INTELIGENTE (Phase 3) ---
            try:
                # 1. MODULO TARJETAS
                if "PAYWAY" in f_upper and f_upper.endswith(".PDF"):
                    from modulo_tarjetas import parser_payway_liq
                    success, info = parser_payway_liq.procesar_archivo(filepath)
                elif "NARANJA" in f_upper and f_upper.endswith(".XLSX"):
                    from modulo_tarjetas import parser_naranja_xlsx
                    success, info = parser_naranja_xlsx.procesar_archivo(filepath)
                elif "LIQMENSAL" in f_upper and f_upper.endswith(".PDF"):
                    from modulo_tarjetas import parser_patagonia
                    success, info = parser_patagonia.procesar_archivo(filepath)

                # 2. MODULO COMPRAS (AFIP / CALIM)
                elif ("AFIP" in f_upper or "VENTAS" in f_upper or "COMPRAS" in f_upper) and f_upper.endswith(".CSV"):
                    from modulo_compras import importador_afip
                    success, info = importador_afip.procesar_archivo(filepath)
                elif "CALIM" in f_upper and f_upper.endswith(".XLSX"):
                    from modulo_compras import importador_calim
                    success, info = importador_calim.procesar_archivo(filepath)

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
                    print(f"❓ Formato desconocido: {f}. No se encontró parser.")
                    continue

                # --- FLUJO DE ÉXITO: ARCHIVADO LEGAL ---
                if success and info:
                    # Mover a static/archivadas/ con jerarquía legal
                    new_path = archiver_service.archivar_documento(
                        filepath, 
                        modulo=info['modulo'], 
                        anio=info['anio'], 
                        mes=info['mes'], 
                        entidad=info['entidad']
                    )
                    
                    # Actualización de puntero físico en DB
                    if new_path:
                        if info['db_table'] == 'liquidaciones_tarjetas':
                            tarjetas.update_record_path(info['id_insertado'], new_path)
                        elif info['db_table'] == 'facturas':
                            compras.update_record_path(info['id_insertado'], new_path)
                        elif info['db_table'] == 'bancos_movimientos':
                            from modulo_bancos import storage_bancos
                            storage_bancos.update_record_path(info['id_insertado'], new_path)
                        
                        print(f"✅ ÉXITO: {f} -> Archivador Legal ({info['entidad']})")
                else:
                    print(f"⚠️ El archivo {f} fue rechazado por el parser (Duplicado o Error).")

            except Exception as e:
                print(f"❌ Error crítico procesando {f}: {e}")

if __name__ == "__main__":
    WORKSPACE = os.path.dirname(os.path.abspath(__file__))
    master = ERPMaster(WORKSPACE)
    
    if "--setup" in sys.argv:
        master.setup_schema()
    if "--audit" in sys.argv:
        master.run_audit()
    if "--search" in sys.argv:
        idx = sys.argv.index("--search")
        if idx + 1 < len(sys.argv): master.search(sys.argv[idx + 1])
    
    if len(sys.argv) == 1:
        print("ERP Master Operativo. Comandos: --setup, --audit, --search [TERMINO]")

if __name__ == "__main__":
    WORKSPACE = os.path.dirname(os.path.abspath(__file__))
    master = ERPMaster(WORKSPACE)
    
    if "--setup" in sys.argv:
        master.setup_schema()
    if "--audit" in sys.argv:
        master.run_audit()
    if "--search" in sys.argv:
        idx = sys.argv.index("--search")
        if idx + 1 < len(sys.argv): master.search(sys.argv[idx + 1])
    
    if len(sys.argv) == 1:
        print("ERP Master Operativo. Comandos: --setup, --audit, --search [TERMINO]")
