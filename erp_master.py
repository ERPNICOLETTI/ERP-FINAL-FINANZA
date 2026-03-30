import sqlite3
import pandas as pd
import sys
import os
import re
from datetime import datetime, timedelta

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
        """Prepara las tablas base de ERP FINAL y añade índices de IA / Búsqueda Full-Text."""
        conn = self._get_conn()
        
        # 1. Asegurar tablas legacy del ERP
        conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY, entity TEXT, account TEXT, category TEXT, type TEXT, amount REAL, desc TEXT, date TEXT, groupId INTEGER, currency TEXT DEFAULT 'ARS'
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS payway_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                fecha_compra TEXT, 
                fecha_presentacion TEXT, 
                fecha_pago TEXT,
                lote TEXT, 
                cupon TEXT, 
                marca TEXT, 
                monto_bruto REAL, 
                estado TEXT DEFAULT 'PENDIENTE', 
                metadata TEXT,
                matching_tx_id INTEGER, 
                FOREIGN KEY(matching_tx_id) REFERENCES transactions(id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS liquidaciones_tarjetas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fuente TEXT, -- Payway, Patagonia365, Naranja
                tipo TEXT,   -- DIARIA, MENSUAL
                fecha_liquidacion TEXT,
                periodo TEXT, -- YYYY-MM
                marca TEXT,
                establecimiento TEXT,
                total_bruto REAL,
                costo_arancel REAL,
                costo_financiero REAL,
                iva_21 REAL,
                iva_105 REAL,
                retenciones REAL, -- Suma de Ganancias, IVA, IIBB
                total_neto REAL,
                metadata TEXT,
                UNIQUE(fuente, fecha_liquidacion, periodo, marca, establecimiento, total_neto)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT, numero_completo TEXT UNIQUE, tipo_operacion TEXT, tipo_comprobante TEXT, proveedor TEXT, fecha_emision TEXT, neto_gravado REAL, monto_iva REAL, monto_total REAL, esta_en_afip INTEGER DEFAULT 0, esta_en_calim INTEGER DEFAULT 0, estado_proceso TEXT DEFAULT 'PENDIENTE', ruta_archivo TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS liquidaciones_detalles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                liquidacion_id INTEGER, -- FK a liquidaciones_tarjetas (el "header")
                fecha TEXT,
                descripcion TEXT,
                monto_bruto REAL,
                arancel REAL,
                financiero REAL,
                iva REAL,
                retenciones REAL,
                monto_neto REAL,
                metadata_raw TEXT, -- JSON con el resto de los campos "cada bit"
                FOREIGN KEY(liquidacion_id) REFERENCES liquidaciones_tarjetas(id)
            )
        ''')
        
        # 2. Tabla Desacoplada para CALIM (Espejo para cruces)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS facturas_calim (
                id INTEGER PRIMARY KEY AUTOINCREMENT, numero_completo TEXT UNIQUE, tipo_operacion TEXT, tipo_comprobante TEXT, proveedor TEXT, fecha_emision TEXT, neto_gravado REAL, monto_iva REAL, monto_total REAL, estado_proceso TEXT DEFAULT 'CALIM_BRUTO'
            )
        ''')

        # 3. Módulo Bancos / Cuenta Corriente (El cruce final)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bancos_movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                banco TEXT, -- CHUBUT, GALICIA, MACRO
                cuenta TEXT, -- e.g. CAJA DE AHORRO, CUENTA CORRIENTE
                fecha TEXT,
                descripcion TEXT,
                codigo_movimiento TEXT, -- ID del movimiento en el banco (no siempre es único)
                importe REAL,
                metadata TEXT,
                UNIQUE(banco, cuenta, fecha, descripcion, codigo_movimiento, importe)
            )
        ''')

        # 3. Tabla Desacoplada para Declaraciones Juradas (F.2051)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS libroiva (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                periodo TEXT UNIQUE,
                debito_fiscal REAL,
                credito_fiscal REAL,
                saldo_tecnico REAL,
                saldo_libre_disponibilidad REAL
            )
        ''')
        
        # 2. Índices de Rendimiento
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions (date, amount)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pw_date ON payway_records (fecha_compra)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fac_num ON facturas (numero_completo)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pw_unique ON payway_records (lote, cupon, fecha_compra, monto_bruto)")

        # 3. Índice FTS5 para Búsqueda 360 estilo Google
        conn.execute("DROP TABLE IF EXISTS search_index")
        conn.execute("CREATE VIRTUAL TABLE search_index USING fts5(source, id, name, amount, date, extra)")
        
        # Poblar el índice (Cross-table View)
        conn.execute("""
            INSERT INTO search_index(source, id, name, amount, date, extra)
            SELECT 'Transaccion', id, desc, amount, date, entity || ' / ' || account FROM transactions
            UNION ALL
            SELECT 'Payway', id, cupon || ' Lote ' || lote, monto_bruto, fecha_compra, marca FROM payway_records
            UNION ALL
            SELECT 'Factura', id, numero_completo || ' ' || proveedor, monto_total, fecha_emision, tipo_comprobante FROM facturas
            UNION ALL
            SELECT 'Liquidacion', id, fuente || ' ' || marca, total_bruto, fecha_liquidacion, 'Periodo: ' || periodo FROM liquidaciones_tarjetas
            UNION ALL
            SELECT 'Banco', id, banco || ' ' || descripcion, importe, fecha, codigo_movimiento FROM bancos_movimientos
        """)
        
        conn.commit()
        conn.close()
        print("[OK] Esquema actualizado. Índices FTS5 regenerados.")

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
