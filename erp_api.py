from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import os
import sys
import re
from typing import List, Dict, Any
from pydantic import BaseModel
from erp_master import ERPMaster

class AdjuntarRequest(BaseModel):
    identificador: str
    ruta: str

class ForzarAdjuntarRequest(BaseModel):
    identificador: str
    proveedor: str
    ruta: str

# Setup UTF-8 for Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = FastAPI(title="ERP Final API", version="2.0.0")

# Workspace Context
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
master = ERPMaster(WORKSPACE)

@app.get("/", response_class=HTMLResponse)
async def home():
    """Centro de control para la IA."""
    return """
    <html>
        <head>
            <title>ERP API - Modo Cerebro</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #0f172a; color: #f8fafc; padding: 50px; }
                .container { max-width: 800px; margin: auto; background: #1e293b; padding: 30px; border-radius: 15px; border: 1px solid #334155; }
                h1 { color: #38bdf8; border-bottom: 1px solid #334155; padding-bottom: 10px; }
                .status { color: #10b981; font-weight: bold; }
                ul { line-height: 2; color: #cbd5e1; }
                code { background: #0f172a; padding: 2px 6px; border-radius: 4px; color: #f472b6; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🧠 ERP Final API Server</h1>
                <p>Estado del Motor de Análisis: <span class="status">OPERATIVO EN SERVICIO IA</span></p>
                <p>Endpoints expuestos para "cerebro.py":</p>
                <ul>
                    <li><code>/search?q=Termino</code>: Motor de búsqueda difuso en SQL sobre todas las tablas.</li>
                    <li><code>/facturas</code>: Filtro avanzado de facturas (rango de fechas, tipos).</li>
                    <li><code>/audit</code>: Ejecuta el motor para ver las falencias crudas (JSON).</li>
                    <li><code>/facturas/discrepancias</code>: Ver facturas que están en ARCA pero no en CALIM o viceversa.</li>
                    <li><code>/iva</code>: Devuelve el cálculo contable (Débito y Crédito) del IVA.</li>
                    <li><code>/summary</code>: Devuelve un resumen estadístico de lo que existe en la DB.</li>
                    <li><code>/sync</code>: Regenerar FTS5 índices para búsquedas.</li>
                </ul>
            </div>
        </body>
    </html>
    """

@app.get("/search")
async def search(q: str):
    """Búsqueda global FTS5 en toda la base de datos."""
    import sqlite3
    conn = master._get_conn()
    try:
        # FTS5 matcher
        safe_q = f'"{q}"'
        cur = conn.execute("SELECT source, id, name, amount, date, extra FROM search_index WHERE search_index MATCH ? ORDER BY rank LIMIT 30", (safe_q,))
        rows = cur.fetchall()
        results = [{"source": r["source"], "id": r["id"], "name": r["name"], "amount": r["amount"], "date": r["date"], "extra": r["extra"]} for r in rows]
        return {"term": q, "results": results}
    except Exception as e:
        return {"error": str(e), "results": []}
    finally:
        conn.close()

@app.get("/facturas")
async def get_facturas(desde: str = None, hasta: str = None, tipo: str = None, operacion: str = None, q: str = None):
    """Consulta avanzada de comprobantes."""
    import sqlite3
    conn = master._get_conn()
    query = "SELECT * FROM facturas WHERE 1=1"
    params = []
    
    if q:
        query += " AND (proveedor LIKE ? OR numero_completo LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    
    if desde:
        query += " AND fecha_emision >= ?"
        params.append(desde)
    if hasta:
        query += " AND fecha_emision <= ?"
        params.append(hasta)
    if tipo:
        query += " AND tipo_comprobante LIKE ?"
        params.append(f"%{tipo}%")
    if operacion:
        query += " AND tipo_operacion = ?"
        params.append(operacion.upper())
        
    query += " ORDER BY fecha_emision ASC"
    
    try:
        cur = conn.execute(query, params)
        rows = [dict(row) for row in cur.fetchall()]
        
        # Native Sum Calculation
        total_sum = sum(r['monto_total'] for r in rows)
        
        return {
            "count": len(rows), 
            "total_monto": total_sum,
            "results": rows
        }
    except Exception as e:
        return {"error": str(e), "results": []}
    finally:
        conn.close()

@app.post("/facturas/adjuntar")
async def adjuntar_pdf(req: AdjuntarRequest):
    """Asocia un PDF a una factura existente, moviéndolo a una carpeta estructurada y renombrándolo."""
    import sqlite3
    import shutil
    import os
    import re
    
    conn = master._get_conn()
    try:
        cur = conn.execute("SELECT numero_completo, proveedor, fecha_emision, ruta_archivo FROM facturas WHERE numero_completo LIKE ? OR id = ?", (f"%{req.identificador}%", req.identificador))
        row = cur.fetchone()
        if not row:
             return {"status": "Error", "mensaje": f"Factura con llave '{req.identificador}' no encontrada en la DB."}
             
        num_oficial = row[0]
        proveedor_raw = row[1]
        fecha_emision = row[2]
        ruta_existente = row[3]
        
        if ruta_existente:
            return {"status": "Aviso", "mensaje": f"Factura {num_oficial} ya fue archivada previamente en: {ruta_existente}"}
        
        # 1. Limpiar el nombre del proveedor de caracteres ilegales para Windows (<>:/\|?*)
        proveedor_limpio = re.sub(r'[<>:"/\\|?*]', '', proveedor_raw).strip()
        
        # 2. Fabricar la súper carpeta de Archivo en: \ERP FINAL\static\archivadas\PROVEEDOR\
        boveda_path = os.path.join(WORKSPACE, "static", "archivadas", proveedor_limpio)
        os.makedirs(boveda_path, exist_ok=True)
        
        # 3. Fabricar el nombre del archivo final corto (Ej: 2026-01-23_FC-6-207.pdf)
        _, ext = os.path.splitext(req.ruta)
        if not ext:
            ext = ".pdf"
            
        partes = num_oficial.split('-', 2)
        if len(partes) == 3:
            tipo_map = {
                "001": "FA", "002": "NDA", "003": "NCA",
                "006": "FB", "007": "NDB", "008": "NCB",
                "011": "FC", "012": "NDC", "013": "NCC",
                "051": "FM", "052": "NDM", "053": "NCM"
            }
            tipo_str = tipo_map.get(partes[0], f"T{partes[0].lstrip('0') or '0'}")
            pto_str = str(int(partes[1]))
            num_str = str(int(partes[2]))
            nombre_corto = f"{tipo_str}-{pto_str}-{num_str}"
        else:
            nombre_corto = num_oficial # Fallback por si hay un formato raro
            
        nombre_final = f"{fecha_emision}_{nombre_corto}{ext}"
        
        ruta_definitiva = os.path.join(boveda_path, nombre_final)
        
        # 4. Mover y reemplazar el original (Elimina la ruta de origen para no repetir erroes)
        if not os.path.exists(req.ruta):
            return {"status": "Error", "mensaje": f"El archivo original propuesto no existe físicamente en Windows: {req.ruta}"}
            
        shutil.move(req.ruta, ruta_definitiva)
        
        # 5. Guardar la ruta estructurada perfecta en la base de datos de AFIP
        cur = conn.execute("UPDATE facturas SET ruta_archivo = ? WHERE numero_completo = ?", (ruta_definitiva, num_oficial))
        conn.commit()
        
        return {"status": "Éxito", "mensaje": f"Archivo reorganizado y archivado corporativamente en {proveedor_limpio}\\{nombre_final}"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

@app.post("/facturas/forzar_adjunto")
async def forzar_adjunto_pdf(req: ForzarAdjuntarRequest):
    """Fuerza la creación de bóveda y adjunto, creando un registro Shell (Fantasma) si no existe en AFIP."""
    import sqlite3
    import shutil
    import os
    import re
    from datetime import datetime
    
    conn = master._get_conn()
    try:
        cur = conn.execute("SELECT numero_completo, proveedor, fecha_emision, ruta_archivo FROM facturas WHERE numero_completo LIKE ?", (f"%{req.identificador}%",))
        row = cur.fetchone()
        
        if row and row[3]: # row[3] es ruta_archivo
            return {"status": "Aviso", "mensaje": f"Factura {row[0]} ya fue archivada previamente con éxito."}
            
        num_oficial = req.identificador
        proveedor_raw = row[1] if row else req.proveedor
        fecha_emision = row[2] if row else datetime.now().strftime("%Y-%m-%d")
        
        proveedor_limpio = re.sub(r'[<>:"/\\|?*]', '', proveedor_raw).strip()
        boveda_path = os.path.join(WORKSPACE, "static", "archivadas", proveedor_limpio)
        os.makedirs(boveda_path, exist_ok=True)
        
        _, ext = os.path.splitext(req.ruta)
        if not ext: ext = ".pdf"
            
        partes = num_oficial.split('-', 2)
        if len(partes) == 3:
            tipo_map = {
                "001": "FA", "002": "NDA", "003": "NCA",
                "006": "FB", "007": "NDB", "008": "NCB",
                "011": "FC", "012": "NDC", "013": "NCC",
                "051": "FM", "052": "NDM", "053": "NCM"
            }
            tipo_str = tipo_map.get(partes[0], f"T{partes[0].lstrip('0') or '0'}")
            pto_str = str(int(partes[1]))
            num_str = str(int(partes[2]))
            nombre_corto = f"{tipo_str}-{pto_str}-{num_str}"
        else:
            nombre_corto = num_oficial
            
        nombre_final = f"{fecha_emision}_{nombre_corto}{ext}"
        ruta_definitiva = os.path.join(boveda_path, nombre_final)
        
        if not os.path.exists(req.ruta):
            return {"status": "Error", "mensaje": f"El archivo original propuesto no existe físicamente en Windows: {req.ruta}"}
            
        shutil.move(req.ruta, ruta_definitiva)
        
        if row: # EXISTE, SOLO ACTUALIZA RUTA
            conn.execute("UPDATE facturas SET ruta_archivo = ? WHERE numero_completo = ?", (ruta_definitiva, num_oficial))
        else: # NO EXISTE: CREA REGISTRO SHELL PARA FUTURA CONCILIACION
            tcod = partes[0] if len(partes) == 3 else ""
            pvta = partes[1] if len(partes) == 3 else ""
            ncom = partes[2] if len(partes) == 3 else ""
            conn.execute('''
                INSERT INTO facturas (fecha_emision, tipo_comprobante, numero_completo, proveedor, monto_total, monto_iva, neto_gravado, tipo_operacion, esta_en_calim, ruta_archivo, estado_proceso)
                VALUES (?, 'MANUAL-ESPERANDO-SINC.', ?, ?, 0, 0, 0, 'COMPRA', 0, ?, 'FANTASMA')
            ''', (fecha_emision, num_oficial, proveedor_raw, ruta_definitiva))
        
        conn.commit()
        msg_fin = f"Archivo organizado corporativamente en [{proveedor_limpio}\\{nombre_final}]. "
        msg_fin += "¡Actualizado Oficial!" if row else "¡Creado el registro Shell-Fantasma a la espera del próximo Excel de CALIM!"
        return {"status": "Éxito", "mensaje": msg_fin}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

@app.get("/audit")
async def get_audit():
    """Genera datos crudos para que la IA los analice en el prompt."""
    import sqlite3
    conn = master._get_conn()
    
    # Pendientes payway
    cur = conn.execute("SELECT id, compra_date, cupon, monto_bruto FROM payway_records WHERE matching_tx_id IS NULL AND monto_bruto > 0")
    unmatched_pw = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    return {
        "unmatched_payway_count": len(unmatched_pw),
        "unmatched_payway": unmatched_pw[:50] # Top 50 para no reventar memoria del bot
    }

@app.get("/facturas/discrepancias")
async def facturas_audit():
    import sqlite3
    conn = master._get_conn()
    
    # Lo que bajó de AFIP pero el contador NO subió a CALIM
    cur_afip = conn.execute("SELECT numero_completo, proveedor, fecha_emision, monto_total FROM facturas WHERE esta_en_calim = 0")
    afip_sin_calim = [dict(row) for row in cur_afip.fetchall()]
    
    # Lo que está en CALIM de forma manual o desalineada y NO bajó en los CSV's de la AFIP
    cur_calim = conn.execute("SELECT numero_completo, proveedor, fecha_emision, monto_total FROM facturas_calim WHERE numero_completo NOT IN (SELECT numero_completo FROM facturas)")
    calim_sin_afip = [dict(row) for row in cur_calim.fetchall()]
    
    conn.close()
    return {
        "afip_pendientes_en_calim": afip_sin_calim,
        "calim_huerfanas_de_afip": calim_sin_afip
    }

@app.get("/iva")
async def get_iva(anio: str = None):
    """Calcula el IVA a pagar o a favor basado en compras vs ventas."""
    import sqlite3
    conn = master._get_conn()
    params = []
    
    query_compras = "SELECT SUM(monto_iva) as iva_compras FROM facturas WHERE tipo_operacion = 'COMPRA'"
    query_ventas = "SELECT SUM(monto_iva) as iva_ventas FROM facturas WHERE tipo_operacion = 'VENTA'"
    
    if anio:
        query_compras += " AND fecha_emision LIKE ?"
        query_ventas += " AND fecha_emision LIKE ?"
        params.append(f"{anio}%")
        
    try:
        iva_compras = conn.execute(query_compras, params).fetchone()[0] or 0.0
        iva_ventas = conn.execute(query_ventas, params).fetchone()[0] or 0.0
        saldo = float(iva_ventas) - float(iva_compras)
        
        return {
            "periodo": anio or "Histórico Completo",
            "iva_ventas_debito": round(iva_ventas, 2),
            "iva_compras_credito": round(iva_compras, 2),
            "saldo_a_depositar": round(saldo, 2)
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

@app.get("/iva/auditar")
async def auditar_iva_contra_contador(periodo: str):
    import sqlite3
    conn = master._get_conn()
    
    # 1. Contador (F.2051 Libro IVA)
    dj_debito = conn.execute("SELECT debito_fiscal FROM libroiva WHERE periodo=?", (periodo,)).fetchone()
    dj_credito = conn.execute("SELECT credito_fiscal FROM libroiva WHERE periodo=?", (periodo,)).fetchone()
    dj_debito = dj_debito[0] if dj_debito else 0.0
    dj_credito = dj_credito[0] if dj_credito else 0.0
    
    # 2. AFIP Oficial
    afip_debito = conn.execute("SELECT SUM(monto_iva) FROM facturas WHERE tipo_operacion='VENTA' AND fecha_emision LIKE ?", (f"{periodo}%",)).fetchone()[0] or 0.0
    afip_credito = conn.execute("SELECT SUM(monto_iva) FROM facturas WHERE tipo_operacion='COMPRA' AND fecha_emision LIKE ?", (f"{periodo}%",)).fetchone()[0] or 0.0
    
    # 3. CALIM
    calim_debito = conn.execute("SELECT SUM(monto_iva) FROM facturas_calim WHERE tipo_operacion='VENTA' AND fecha_emision LIKE ?", (f"{periodo}%",)).fetchone()[0] or 0.0
    calim_credito = conn.execute("SELECT SUM(monto_iva) FROM facturas_calim WHERE tipo_operacion='COMPRA' AND fecha_emision LIKE ?", (f"{periodo}%",)).fetchone()[0] or 0.0

    conn.close()
    
    return {
        "periodo": periodo,
        "contador_f2051": {"ventas_debito": round(dj_debito, 2), "compras_credito": round(dj_credito, 2)},
        "afip_crudo": {"ventas_debito": round(afip_debito, 2), "compras_credito": round(afip_credito, 2)},
        "calim_interno": {"ventas_debito": round(calim_debito, 2), "compras_credito": round(calim_credito, 2)},
        "diferencias_vs_afip": {
            "brecha_debito": round(dj_debito - afip_debito, 2),
            "brecha_credito": round(dj_credito - afip_credito, 2)
        }
    }

@app.get("/summary")
async def get_summary(anio: str = None):
    import sqlite3
    conn = master._get_conn()
    
    params = []
    
    # Base queries
    q_tx = "SELECT COUNT(*), MIN(date), MAX(date), SUM(amount) FROM transactions"
    q_pw = "SELECT COUNT(*), MIN(compra_date), MAX(compra_date), SUM(monto_bruto) FROM payway_records"
    q_fac_count = "SELECT COUNT(*), MIN(fecha_emision), MAX(fecha_emision) FROM facturas"
    q_fac_ventas = "SELECT SUM(monto_total) FROM facturas WHERE tipo_operacion = 'VENTA'"
    q_fac_compras = "SELECT SUM(monto_total) FROM facturas WHERE tipo_operacion = 'COMPRA'"

    # Si nos piden un año particular, le enseñamos a la API a calcularlo sola en SQL puro
    if anio:
        params = [f"{anio}%"]
        q_tx += " WHERE date LIKE ?"
        q_pw += " WHERE compra_date LIKE ?"
        
        q_fac_count += " WHERE fecha_emision LIKE ?"
        q_fac_ventas += " AND fecha_emision LIKE ?"
        q_fac_compras += " AND fecha_emision LIKE ?"

    try:
        # Transactions stats
        tx_stats = conn.execute(q_tx, params).fetchone()
        
        # Payway stats
        pw_stats = conn.execute(q_pw, params).fetchone()
        
        # Facturas stats
        fac_count = conn.execute(q_fac_count, params).fetchone()
        fac_ventas = conn.execute(q_fac_ventas, params).fetchone()[0] or 0.0
        fac_compras = conn.execute(q_fac_compras, params).fetchone()[0] or 0.0
        
        return {
            "transacciones": {
                "total_registros": tx_stats[0] or 0,
                "fecha_inicio": tx_stats[1] or "N/A",
                "fecha_fin": tx_stats[2] or "N/A",
                "monto_total": round(tx_stats[3] or 0, 2)
            },
            "payway": {
                "total_cupones": pw_stats[0] or 0,
                "fecha_inicio": pw_stats[1] or "N/A",
                "fecha_fin": pw_stats[2] or "N/A",
                "monto_total_bruto": round(pw_stats[3] or 0, 2)
            },
            "facturas": {
                "total_comprobantes": fac_count[0] or 0,
                "fecha_inicio": fac_count[1] or "N/A",
                "fecha_fin": fac_count[2] or "N/A",
                "monto_ventas": round(fac_ventas, 2),
                "monto_compras": round(fac_compras, 2)
            }
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

@app.post("/sync")
async def sync_data():
    master.setup_schema()
    return {"status": "success", "message": "Schema and FTS5 indices updated"}

if __name__ == "__main__":
    import uvicorn
    # Se levanta en el puerto 5005 para no solapar si quedaba algo en el 5001
    uvicorn.run(app, host="127.0.0.1", port=5005)
