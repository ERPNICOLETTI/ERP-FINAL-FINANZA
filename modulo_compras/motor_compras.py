import sqlite3
import pandas as pd
import os

# Lógica del Motor de Facturación (ARCA/CALIM) 🧾🏗️🧠
# Determinar la ruta a la base de datos central en la raíz
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')

def get_db_connection():
    return sqlite3.connect(DB_PATH, timeout=30.0)

def resumen_facturacion(anio):
    """Estadísticas de facturas por año."""
    conn = get_db_connection()
    params = [f"{anio}%"] if anio else []
    where = " WHERE fecha_emision LIKE ?" if anio else ""
    
    cur = conn.cursor()
    # Estadísticas facturas
    count = cur.execute(f"SELECT COUNT(*) FROM facturas {where}", params).fetchone()[0] or 0
    ventas = cur.execute(f"SELECT SUM(monto_total) FROM facturas {where} {'AND' if anio else 'WHERE'} tipo_operacion = 'VENTA'", params).fetchone()[0] or 0.0
    compras = cur.execute(f"SELECT SUM(monto_total) FROM facturas {where} {'AND' if anio else 'WHERE'} tipo_operacion = 'COMPRA'", params).fetchone()[0] or 0.0
    
    conn.close()
    return {
        "total_count": count,
        "monto_ventas": ventas,
        "monto_compras": compras
    }

def buscar_global(termino):
    """Busca en facturas por proveedor, numero o id."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Búsqueda multi-campo en facturas
    q = f"%{termino}%"
    rows = cur.execute("""
        SELECT * FROM facturas 
        WHERE numero_completo LIKE ? 
           OR proveedor LIKE ? 
           OR cui_proveedor LIKE ?
        ORDER BY fecha_emision DESC LIMIT 20
    """, (q, q, q)).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]

def reporte_discrepancias():
    """Analiza discrepancias entre fuentes (AFIP vs CALIM)."""
    conn = get_db_connection()
    
    # Pendientes de enviar a CALIM
    afip_solo = pd.read_sql_query("SELECT * FROM facturas WHERE status = 'SOLO_AFIP'", conn)
    # Calim sin AFIP
    calim_solo = pd.read_sql_query("SELECT * FROM facturas WHERE status = 'SOLO_CALIM'", conn)
    
    conn.close()
    return {
        "afip_pendientes_en_calim": afip_solo.to_dict('records'),
        "calim_huerfanas_de_afip": calim_solo.to_dict('records')
    }
