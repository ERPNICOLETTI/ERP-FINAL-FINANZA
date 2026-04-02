import sqlite3
import pandas as pd
import sys
import os
import re
from datetime import datetime, timedelta
from core_sistema import db_ingesta

# Configuración de salida UTF-8 para Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class ERPMaster:
    """
    Maestro de Auditoría y Procesamiento para ERP FINAL (Modo Inteligencia Centralizada)
    Ingiere datos, crea índices FTS5 y realiza auditorías automáticas (Ej: Payway vs Banco vs Facturas).
    """
    
    def __init__(self, workspace_path):
        self.workspace = workspace_path
        self.db_path = os.path.join(workspace_path, 'erp_nicoletti.db')

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def setup_schema(self):
        """DELEGADO: Llama al nuevo sistema de inicialización modular."""
        db_ingesta.initialize_all()

    def run_audit(self):
        """Cruza los datos entre Payway, Banco (Transactions) y Facturas buscando alertas de falencias."""
        conn = self._get_conn()
        
        print("\n" + "="*80)
        print(" REPORTE DE FALENCIAS ERP (MOTOR ANALÍTICO)")
        print("="*80)

        # 1. Auditoría Payway: Cupones que no hicieron match con movimientos bancarios
        cur = conn.execute("SELECT id, compra_date, cupon, monto_bruto FROM payway_records WHERE matching_tx_id IS NULL AND monto_bruto > 0 ORDER BY compra_date DESC LIMIT 50")
        unmatched_payway = cur.fetchall()
        
        print("\n[!] ALERTAS PAYWAY (Cupones sin acreditar en banco):")
        for p in unmatched_payway:
            print(f"   -> Fecha: {p['compra_date']} | Cupón {p['cupon']} | Monto bruto: ${p['monto_bruto']} | NO ESTÁ EN BANCO")

        # 2. Facturas Huérfanas (Están en sistema pero no archivadas, o viceversa)
        cur = conn.execute("SELECT numero_completo, proveedor, estado_proceso, esta_en_afip, esta_en_calim FROM facturas WHERE estado_proceso != 'ARCHIVADO' ORDER BY fecha_emision DESC LIMIT 50")
        pending_fac = cur.fetchall()
        
        print("\n[!] FACTURAS PENDIENTES DE ARCHIVAR/DISCREPANCIAS CALIM vs ARCA:")
        for f in pending_fac:
            msg = []
            if f['esta_en_afip'] and not f['esta_en_calim']: msg.append("SÓLO EN ARCA")
            elif f['esta_en_calim'] and not f['esta_en_afip']: msg.append("SÓLO EN CALIM")
            print(f"   -> FC {f['numero_completo']} | Prov: {f['proveedor'][:20]} | Estado: {f['estado_proceso']} | [{', '.join(msg) if msg else 'NORMAL'}]")

        conn.close()

    def search(self, term):
        """Buscador 360 usando el cerebro SQL"""
        print(f"\n[BÚSQUEDA 360] Resultados para '{term}':")
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM search_index WHERE search_index MATCH ? ORDER BY rank LIMIT 15", (term,))
            rows = cur.fetchall()
            for r in rows:
                print(f"   [{r['source']}] ID:{r['id']} | {r['name']} | $ {r['amount']} | Fecha: {r['date']} | Info: {r['extra']}")
        except Exception as e:
            print(f"   Error de búsqueda: {e}")
        conn.close()

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
