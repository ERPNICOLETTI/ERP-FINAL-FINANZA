from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse
from erp_api.helpers import templates, aprender_categoria_maestra, ImportRequest

router = APIRouter()

@router.post("/bancos/importar")
async def importar_bancos(req: ImportRequest):
    """Importar extractos bancarios al sistema."""
    try:
        fuente = req.fuente.upper()
        if fuente == 'CHUBUT':
            from modulo_bancos.lectores.lector_chubut import parse_chubut_excel
            parse_chubut_excel(req.path)
            return {"status": "success", "fuente": "CHUBUT"}
        return {"status": "error", "message": f"Banco '{fuente}' no soportado"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/bancos/sueldos")
async def get_sueldos_bancarios(anio: str = "2026"):
    """Consulta de sueldos delegada al dominio de bancos."""
    from modulo_bancos import storage_bancos
    return storage_bancos.get_sueldos(anio)

@router.get("/api/bancos/movimientos")
async def list_bancos_movimientos(request: Request, cuenta: str = None, categoria: str = None, mes: str = None, q: str = None, agrupar: str = None, area: str = None):
    """Filtra y devuelve movimientos bancarios para HTMX."""
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    import sqlite3
    conn.row_factory = sqlite3.Row
    
    if agrupar == "1":
        query = "SELECT MAX(id) as id, MAX(fecha) as fecha, banco, cuenta, descripcion, categoria, SUM(importe) as importe, COUNT(*) as qty, SUM(saldo) as saldo FROM bancos_movimientos WHERE 1=1"
    else:
        query = "SELECT id, fecha, banco, cuenta, descripcion, categoria, importe, saldo, 1 as qty FROM bancos_movimientos WHERE 1=1"
    
    params = []
    
    if cuenta:
        query += " AND cuenta LIKE ?"
        params.append(f"%{cuenta}%")
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    if mes:
        query += " AND strftime('%m', fecha) = ?"
        params.append(mes)
    if q:
        query += " AND (descripcion LIKE ? OR CAST(importe AS TEXT) LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if area:
        conn_cat = storage_bancos.get_db_connection()
        cursor_cat = conn_cat.execute("SELECT nombre FROM gastos_tipos WHERE cuenta_codigo = ?", (area,))
        cat_names = [row[0] for row in cursor_cat.fetchall()]
        conn_cat.close()
        
        if cat_names:
            query += f" AND categoria IN ({','.join(['?'] * len(cat_names))})"
            params.extend(cat_names)
        else:
            query += " AND 1=0"
        
    if agrupar == "1":
        query += " GROUP BY descripcion, categoria ORDER BY qty DESC, fecha DESC"
    else:
        query += " ORDER BY fecha ASC, id DESC"
    
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    movimientos = [dict(r) for r in rows]
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request=request, name="tabla_bancos.html", context={"request": request, "movimientos": movimientos})
    return movimientos

@router.get("/api/bancos/movimientos/{id}/edit_categoria")
async def edit_mov_categoria(request: Request, id: int):
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    import sqlite3
    conn.row_factory = sqlite3.Row
    categorias = conn.execute("SELECT nombre, emoji FROM categorias_maestras ORDER BY tipo, nombre").fetchall()
    conn.close()
    return templates.TemplateResponse(request=request, name="bancos_inline_edit.html", context={"request": request, "id": id, "categorias": categorias})

@router.put("/api/bancos/movimientos/{id}/categoria")
async def save_mov_categoria(request: Request, id: int, categoria: str = Form(...)):
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    conn.execute("UPDATE bancos_movimientos SET categoria=? WHERE id=?", (categoria, id))
    conn.commit()
    import sqlite3
    conn.row_factory = sqlite3.Row
    mov = conn.execute("SELECT * FROM bancos_movimientos WHERE id=?", (id,)).fetchone()
    conn.close()
    
    if mov:
        aprender_categoria_maestra(categoria, mov['descripcion'])
        
    return templates.TemplateResponse(request=request, name="bancos_badge_cell.html", context={"request": request, "mov": mov})

@router.post("/api/bancos/movimientos/bulk_categoria")
async def bulk_edit_categoria(request: Request, new_categoria: str = Form(...), cuenta: str = Form(None), categoria: str = Form(None), mes: str = Form(None), q: str = Form(None), agrupar: str = Form(None), area: str = Form(None)):
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    
    where_clause = "1=1"
    params = []
    
    if cuenta:
        where_clause += " AND cuenta LIKE ?"
        params.append(f"%{cuenta}%")
    if categoria:
        where_clause += " AND categoria = ?"
        params.append(categoria)
    if mes:
        where_clause += " AND strftime('%m', fecha) = ?"
        params.append(mes)
    if q:
        where_clause += " AND (descripcion LIKE ? OR CAST(importe AS TEXT) LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if area:
        conn_cat = storage_bancos.get_db_connection()
        cursor_cat = conn_cat.execute("SELECT nombre FROM gastos_tipos WHERE cuenta_codigo = ?", (area,))
        cat_names = [row[0] for row in cursor_cat.fetchall()]
        conn_cat.close()
        
        if cat_names:
            where_clause += f" AND categoria IN ({','.join(['?'] * len(cat_names))})"
            params.extend(cat_names)
        else:
            where_clause += " AND 1=0"
        
    query = f"UPDATE bancos_movimientos SET categoria = ? WHERE {where_clause}"
    update_params = [new_categoria] + params
    conn.execute(query, update_params)
    conn.commit()
    conn.close()
    
    if q and len(q.strip()) >= 3:
        try:
            aprender_categoria_maestra(new_categoria, q)
        except Exception as e:
            print(f"Error en aprendizaje masivo bancario: {e}")
            
    return await list_bancos_movimientos(request, cuenta, categoria, mes, q, agrupar, area)

@router.get("/api/bancos/kpis")
async def get_bancos_kpis(request: Request, cuenta: str = None, categoria: str = None, mes: str = None, q: str = None, area: str = None):
    """Devuelve los KPIs financieros actualizados según los filtros actuales."""
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    
    query = "SELECT sum(importe) FROM bancos_movimientos WHERE importe > 0"
    query_neg = "SELECT sum(importe) FROM bancos_movimientos WHERE importe < 0"
    
    params = []
    filtros = ""
    if cuenta:
        filtros += " AND cuenta LIKE ?"
        params.append(f"%{cuenta}%")
    if categoria:
        filtros += " AND categoria = ?"
        params.append(categoria)
    if mes:
        filtros += " AND strftime('%m', fecha) = ?"
        params.append(mes)
    if q:
        filtros += " AND (descripcion LIKE ? OR CAST(importe AS TEXT) LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if area:
        conn_cat = storage_bancos.get_db_connection()
        cursor_cat = conn_cat.execute("SELECT nombre FROM gastos_tipos WHERE cuenta_codigo = ?", (area,))
        cat_names = [row[0] for row in cursor_cat.fetchall()]
        conn_cat.close()
        
        if cat_names:
            filtros += f" AND categoria IN ({','.join(['?'] * len(cat_names))})"
            params.extend(cat_names)
        else:
            filtros += " AND 1=0"
        
    ingresos = conn.execute(query + filtros, params).fetchone()[0] or 0.0
    egresos = conn.execute(query_neg + filtros, params).fetchone()[0] or 0.0
    conn.close()
    
    html = f'''
        <div class="kpi-card">
            <h4>Total Ingresos 📈</h4>
            <div class="value val-positive">$ {"{:,.2f}".format(ingresos).replace(',', 'X').replace('.', ',').replace('X', '.')}</div>
        </div>
        <div class="kpi-card">
            <h4>Total Egresos 📉</h4>
            <div class="value val-negative">$ {"{:,.2f}".format(egresos).replace(',', 'X').replace('.', ',').replace('X', '.')}</div>
        </div>
        <div class="kpi-card">
            <h4>Flujo Neto ⚖️</h4>
            <div class="value" style="color: {'#10b981' if (ingresos+egresos) >= 0 else '#ef4444'}">$ {"{:,.2f}".format(ingresos + egresos).replace(',', 'X').replace('.', ',').replace('X', '.')}</div>
        </div>
    '''
    return HTMLResponse(content=html)
