from fastapi import APIRouter, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse
from erp_api.helpers import templates, aprender_categoria_maestra, aprender_palabra_clave, ImportRequest

router = APIRouter()

# Los extractos históricos no usan un único formato: algunos lectores guardan
# YYYY-MM-DD y el Hipotecario (JOA) guarda DD/MM/YYYY. SQLite strftime() no
# interpreta este último, por lo que normalizamos la fecha dentro de la consulta.
FECHA_ISO_SQL = """(
    CASE
        WHEN fecha GLOB '????-??-??*' THEN substr(fecha, 1, 10)
        WHEN fecha GLOB '??/??/????*' THEN substr(fecha, 7, 4) || '-' || substr(fecha, 4, 2) || '-' || substr(fecha, 1, 2)
        ELSE fecha
    END
)"""

CATEGORIAS_FRONTEND = {
    "Pago_Tarjeta": "Pago Tarjeta",
    "Transferencia_recibida": "Transferencia recibida",
}


def _categoria_db(categoria: str | None) -> str | None:
    """Traduce los valores seguros para URL al texto realmente almacenado."""
    return CATEGORIAS_FRONTEND.get(categoria, categoria)


def _filtros_tarjeta_joa(
    fecha_desde=None, fecha_hasta=None, categoria=None, q=None,
    resumen_id=None, resumen_mes=None
):
    filtros = " WHERE r.fuente = 'Visa Hipotecario'"
    params = []
    fecha = "COALESCE(NULLIF(r.fecha_compra, ''), r.fecha)"
    if resumen_id:
        if str(resumen_id).startswith("period:"):
            filtros += " AND substr(r.fecha, 1, 7) = ?"
            params.append(str(resumen_id).split(":", 1)[1])
        else:
            try:
                parsed_summary_id = int(resumen_id)
            except (TypeError, ValueError):
                parsed_summary_id = -1
            filtros += " AND r.resumen_id = ?"
            params.append(parsed_summary_id)
    elif resumen_mes:
        # `r.fecha` usa deliberadamente el período de cierre del resumen;
        # `fecha_compra` conserva el día real que se muestra en la tabla.
        filtros += " AND substr(r.fecha, 1, 7) = ?"
        params.append(resumen_mes)
    else:
        if fecha_desde:
            filtros += f" AND {fecha} >= ?"
            params.append(fecha_desde)
        if fecha_hasta:
            filtros += f" AND {fecha} <= ?"
            params.append(fecha_hasta)
    if categoria:
        filtros += " AND t.nombre = ?"
        params.append(_categoria_db(categoria))
    if q:
        filtros += " AND (r.descripcion LIKE ? OR CAST(r.monto AS TEXT) LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    return filtros, params

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
async def list_bancos_movimientos(request: Request, cuenta: str = None, categoria: str = None, periodo_mes: str = None, q: str = None, agrupar: str = None, area: str = None, entidad: str = None, periodo_anio: str = None, fecha_desde: str = None, fecha_hasta: str = None):
    """Filtra y devuelve movimientos bancarios para HTMX."""
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    import sqlite3
    conn.row_factory = sqlite3.Row
    
    if agrupar == "1":
        query = "SELECT MAX(id) as id, MAX(fecha) as fecha, banco, cuenta, descripcion, categoria, SUM(importe) as importe, COUNT(*) as qty, SUM(saldo) as saldo, MAX(COALESCE(moneda, CASE WHEN cuenta LIKE '%U$D%' THEN 'USD' ELSE 'ARS' END)) AS moneda FROM bancos_movimientos WHERE 1=1"
    else:
        query = "SELECT id, fecha, banco, cuenta, descripcion, categoria, importe, saldo, COALESCE(moneda, CASE WHEN cuenta LIKE '%U$D%' THEN 'USD' ELSE 'ARS' END) AS moneda, 1 as qty FROM bancos_movimientos WHERE 1=1"
    
    params = []
    
    if entidad:
        query += " AND entidad = ?"
        params.append(entidad)
    if cuenta:
        query += " AND cuenta LIKE ?"
        params.append(f"%{cuenta}%")
    if categoria:
        query += " AND categoria = ?"
        params.append(_categoria_db(categoria))
    if periodo_mes:
        query += f" AND substr({FECHA_ISO_SQL}, 6, 2) = ?"
        params.append(periodo_mes)
    if periodo_anio:
        query += f" AND substr({FECHA_ISO_SQL}, 1, 4) = ?"
        params.append(periodo_anio)
    if fecha_desde:
        query += f" AND {FECHA_ISO_SQL} >= ?"
        params.append(fecha_desde)
    if fecha_hasta:
        query += f" AND {FECHA_ISO_SQL} <= ?"
        params.append(fecha_hasta)
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
        query += f" ORDER BY {FECHA_ISO_SQL} ASC, id DESC"
    
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
    storage_bancos._asegurar_esquema_movimientos(conn)
    mov = conn.execute(
        "SELECT id, entidad, categoria, gasto_tipo_id FROM bancos_movimientos WHERE id=?",
        (id,),
    ).fetchone()
    if not mov:
        conn.close()
        raise HTTPException(status_code=404, detail="Movimiento bancario inexistente")

    tipos = []
    if mov["entidad"] == "JOA":
        tipos = conn.execute("""
            SELECT t.id, t.nombre, t.emoji, t.cuenta_codigo,
                   COALESCE(c.nombre, t.cuenta_codigo) AS cuenta_nombre
            FROM gastos_tipos t
            LEFT JOIN gastos_cuentas c ON c.codigo=t.cuenta_codigo
            WHERE t.cuenta_codigo IN ('JOA', 'COMUN', 'JOR')
            ORDER BY CASE t.cuenta_codigo WHEN 'JOA' THEN 1 WHEN 'COMUN' THEN 2 ELSE 3 END,
                     t.tipo, t.nombre
        """).fetchall()
        maestras = conn.execute("""
            SELECT nombre, emoji, tipo FROM categorias_maestras
            WHERE nombre NOT IN (
                SELECT nombre FROM gastos_tipos WHERE cuenta_codigo IN ('JOA', 'COMUN', 'JOR')
            )
            ORDER BY tipo, nombre
        """).fetchall()
    else:
        maestras = conn.execute(
            "SELECT nombre, emoji, tipo FROM categorias_maestras ORDER BY tipo, nombre"
        ).fetchall()
    conn.close()
    return templates.TemplateResponse(request=request, name="bancos_inline_edit.html", context={
        "request": request, "mov": dict(mov), "tipos": [dict(t) for t in tipos],
        "maestras": [dict(c) for c in maestras],
    })

@router.put("/api/bancos/movimientos/{id}/categoria")
async def save_mov_categoria(
    request: Request, id: int, categoria_ref: str = Form(None), categoria: str = Form(None)
):
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    storage_bancos._asegurar_esquema_movimientos(conn)
    mov = conn.execute("SELECT * FROM bancos_movimientos WHERE id=?", (id,)).fetchone()
    if not mov:
        conn.close()
        raise HTTPException(status_code=404, detail="Movimiento bancario inexistente")

    ref = (categoria_ref or (f"maestra:{categoria}" if categoria else "")).strip()
    gasto_tipo_id = None
    aprendizaje = "maestra"
    if ref.startswith("tipo:"):
        if mov["entidad"] != "JOA":
            conn.close()
            raise HTTPException(status_code=400, detail="Los tipos personales sólo aplican a JOA")
        try:
            gasto_tipo_id = int(ref.split(":", 1)[1])
        except ValueError:
            conn.close()
            raise HTTPException(status_code=422, detail="Tipo de gasto inválido")
        tipo = conn.execute("""
            SELECT id, nombre FROM gastos_tipos
            WHERE id=? AND cuenta_codigo IN ('JOA', 'COMUN', 'JOR')
        """, (gasto_tipo_id,)).fetchone()
        if not tipo:
            conn.close()
            raise HTTPException(status_code=422, detail="Tipo de gasto no permitido")
        categoria_nombre = tipo["nombre"]
        aprendizaje = "tipo"
    elif ref.startswith("maestra:"):
        categoria_nombre = ref.split(":", 1)[1].strip()
        existe = conn.execute(
            "SELECT 1 FROM categorias_maestras WHERE nombre=?", (categoria_nombre,)
        ).fetchone()
        if not existe:
            conn.close()
            raise HTTPException(status_code=422, detail="Categoría bancaria inválida")
    else:
        conn.close()
        raise HTTPException(status_code=422, detail="Seleccioná una categoría")

    conn.execute(
        "UPDATE bancos_movimientos SET categoria=?, gasto_tipo_id=? WHERE id=?",
        (categoria_nombre, gasto_tipo_id, id),
    )
    conn.commit()
    mov = conn.execute("SELECT * FROM bancos_movimientos WHERE id=?", (id,)).fetchone()
    conn.close()

    if aprendizaje == "tipo":
        aprender_palabra_clave(gasto_tipo_id, mov["descripcion"])
    else:
        aprender_categoria_maestra(categoria_nombre, mov["descripcion"])
        
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
async def get_bancos_kpis(request: Request, cuenta: str = None, categoria: str = None, periodo_mes: str = None, q: str = None, area: str = None, entidad: str = None, periodo_anio: str = None, fecha_desde: str = None, fecha_hasta: str = None):
    """Devuelve los KPIs financieros actualizados según los filtros actuales."""
    from modulo_bancos import storage_bancos
    conn = storage_bancos.get_db_connection()
    
    query = "SELECT sum(importe) FROM bancos_movimientos WHERE importe > 0"
    query_neg = "SELECT sum(importe) FROM bancos_movimientos WHERE importe < 0"
    
    params = []
    filtros = ""
    if entidad:
        filtros += " AND entidad = ?"
        params.append(entidad)
    if cuenta:
        filtros += " AND cuenta LIKE ?"
        params.append(f"%{cuenta}%")
    if categoria:
        filtros += " AND categoria = ?"
        params.append(_categoria_db(categoria))
    if periodo_mes:
        filtros += f" AND substr({FECHA_ISO_SQL}, 6, 2) = ?"
        params.append(periodo_mes)
    if periodo_anio:
        filtros += f" AND substr({FECHA_ISO_SQL}, 1, 4) = ?"
        params.append(periodo_anio)
    if fecha_desde:
        filtros += f" AND {FECHA_ISO_SQL} >= ?"
        params.append(fecha_desde)
    if fecha_hasta:
        filtros += f" AND {FECHA_ISO_SQL} <= ?"
        params.append(fecha_hasta)
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
        
    moneda_label = "U$D" if cuenta and "U$D" in cuenta else "$"
    moneda_nombre = "USD" if moneda_label == "U$D" else "ARS"
    usd_neto = None
    if entidad == "JOA" and not cuenta:
        # Nunca sumar dólares nominales con pesos. La vista consolidada muestra
        # ARS como principal y la variación USD en una tarjeta independiente.
        filtros_ars = filtros + " AND cuenta NOT LIKE '%U$D%'"
        ingresos = conn.execute(query + filtros_ars, params).fetchone()[0] or 0.0
        egresos = conn.execute(query_neg + filtros_ars, params).fetchone()[0] or 0.0
        usd_ingresos = conn.execute(query + filtros + " AND cuenta LIKE '%U$D%'", params).fetchone()[0] or 0.0
        usd_egresos = conn.execute(query_neg + filtros + " AND cuenta LIKE '%U$D%'", params).fetchone()[0] or 0.0
        usd_neto = usd_ingresos + usd_egresos
    else:
        ingresos = conn.execute(query + filtros, params).fetchone()[0] or 0.0
        egresos = conn.execute(query_neg + filtros, params).fetchone()[0] or 0.0
    conn.close()
    
    html = f'''
        <div class="kpi-card">
            <h4>Entradas bancarias {moneda_nombre} 📈</h4>
            <div class="value val-positive">{moneda_label} {"{:,.2f}".format(ingresos).replace(',', 'X').replace('.', ',').replace('X', '.')}</div>
        </div>
        <div class="kpi-card">
            <h4>Salidas bancarias {moneda_nombre} 📉</h4>
            <div class="value val-negative">{moneda_label} {"{:,.2f}".format(abs(egresos)).replace(',', 'X').replace('.', ',').replace('X', '.')}</div>
        </div>
        <div class="kpi-card">
            <h4>Variación bancaria {moneda_nombre} ⚖️</h4>
            <div class="value" style="color: {'#10b981' if (ingresos+egresos) >= 0 else '#ef4444'}">{moneda_label} {"{:,.2f}".format(ingresos + egresos).replace(',', 'X').replace('.', ',').replace('X', '.')}</div>
        </div>
    '''
    if usd_neto is not None:
        html += f'''
        <div class="kpi-card">
            <h4>Variación bancaria USD 💵</h4>
            <div class="value" style="color: {'#10b981' if usd_neto >= 0 else '#ef4444'}">U$D {"{:,.2f}".format(usd_neto).replace(',', 'X').replace('.', ',').replace('X', '.')}</div>
        </div>
        '''
    return HTMLResponse(content=html)


@router.get("/api/joa/tarjeta/movimientos")
async def get_joa_tarjeta_movimientos(
    request: Request, fecha_desde: str = None, fecha_hasta: str = None,
    categoria: str = None, q: str = None, resumen_id: str = None,
    resumen_mes: str = None
):
    """Consumos de la Visa Hipotecario de Joaquín, separados de la caja de ahorro."""
    from modulo_gastos import storage_gastos
    conn = storage_gastos.get_db_connection()
    filtros, params = _filtros_tarjeta_joa(
        fecha_desde, fecha_hasta, categoria, q, resumen_id, resumen_mes
    )
    rows = conn.execute(f"""
        SELECT r.id, COALESCE(NULLIF(r.fecha_compra, ''), r.fecha) AS fecha,
               r.descripcion, r.monto, COALESCE(r.moneda_original, 'ARS') AS moneda_original,
               COALESCE(r.monto_original, r.monto) AS monto_original,
               COALESCE(r.tipo_movimiento, 'CONSUMO') AS tipo_movimiento,
               t.nombre AS categoria, t.emoji, t.cuenta_codigo AS asignacion
        FROM gastos_registros r
        JOIN gastos_tipos t ON t.id = r.gasto_tipo_id
        {filtros}
        ORDER BY COALESCE(NULLIF(r.fecha_compra, ''), r.fecha) DESC, r.id DESC
    """, params).fetchall()
    conn.close()
    return templates.TemplateResponse(
        request=request,
        name="tabla_joa_tarjeta.html",
        context={"request": request, "movimientos": [dict(row) for row in rows]},
    )


@router.get("/api/joa/tarjeta/movimientos/{id}/edit_categoria")
async def edit_joa_tarjeta_categoria(request: Request, id: int):
    from modulo_gastos import storage_gastos
    conn = storage_gastos.get_db_connection()
    mov = conn.execute("""
        SELECT r.id, r.gasto_tipo_id
        FROM gastos_registros r
        WHERE r.id=? AND r.fuente='Visa Hipotecario'
    """, (id,)).fetchone()
    if not mov:
        conn.close()
        raise HTTPException(status_code=404, detail="Consumo de tarjeta inexistente")
    tipos = conn.execute("""
        SELECT t.id, t.nombre, t.emoji, t.cuenta_codigo,
               COALESCE(c.nombre, t.cuenta_codigo) AS cuenta_nombre
        FROM gastos_tipos t
        LEFT JOIN gastos_cuentas c ON c.codigo=t.cuenta_codigo
        WHERE t.cuenta_codigo IN ('JOA', 'COMUN', 'JOR')
        ORDER BY CASE t.cuenta_codigo WHEN 'JOA' THEN 1 WHEN 'COMUN' THEN 2 ELSE 3 END,
                 t.tipo, t.nombre
    """).fetchall()
    conn.close()
    return templates.TemplateResponse(
        request=request,
        name="tarjeta_joa_inline_edit.html",
        context={"request": request, "mov": dict(mov), "tipos": [dict(t) for t in tipos]},
    )


@router.put("/api/joa/tarjeta/movimientos/{id}/categoria")
async def save_joa_tarjeta_categoria(
    request: Request, id: int, gasto_tipo_id: int = Form(...)
):
    from modulo_gastos import storage_gastos
    conn = storage_gastos.get_db_connection()
    mov = conn.execute("""
        SELECT id, gasto_tipo_id, descripcion
        FROM gastos_registros
        WHERE id=? AND fuente='Visa Hipotecario'
    """, (id,)).fetchone()
    tipo = conn.execute("""
        SELECT id FROM gastos_tipos
        WHERE id=? AND cuenta_codigo IN ('JOA', 'COMUN', 'JOR')
    """, (gasto_tipo_id,)).fetchone()
    if not mov or not tipo:
        conn.close()
        raise HTTPException(status_code=422, detail="Movimiento o tipo de gasto inválido")

    cambio_categoria = mov["gasto_tipo_id"] != gasto_tipo_id
    conn.execute(
        "UPDATE gastos_registros SET gasto_tipo_id=? WHERE id=?",
        (gasto_tipo_id, id),
    )
    conn.commit()
    updated = conn.execute("""
        SELECT r.id, t.nombre AS categoria, t.emoji,
               t.cuenta_codigo AS asignacion
        FROM gastos_registros r
        JOIN gastos_tipos t ON t.id=r.gasto_tipo_id
        WHERE r.id=?
    """, (id,)).fetchone()
    conn.close()
    if cambio_categoria:
        aprender_palabra_clave(gasto_tipo_id, mov["descripcion"])
    return templates.TemplateResponse(
        request=request,
        name="tarjeta_joa_categoria_cells.html",
        context={"request": request, "mov": dict(updated)},
    )


@router.get("/api/joa/tarjeta/kpis")
async def get_joa_tarjeta_kpis(
    fecha_desde: str = None, fecha_hasta: str = None,
    categoria: str = None, q: str = None, resumen_id: str = None,
    resumen_mes: str = None
):
    from modulo_gastos import storage_gastos
    conn = storage_gastos.get_db_connection()
    filtros, params = _filtros_tarjeta_joa(
        fecha_desde, fecha_hasta, categoria, q, resumen_id, resumen_mes
    )
    row = conn.execute(f"""
        SELECT COUNT(*) AS movimientos,
               COALESCE(SUM(CASE WHEN COALESCE(r.moneda_original,'ARS')='ARS'
                                 THEN COALESCE(r.monto_original,r.monto) ELSE 0 END), 0) AS consumos_ars,
               COALESCE(SUM(CASE WHEN r.moneda_original='USD'
                                 THEN COALESCE(r.monto_original,0) ELSE 0 END), 0) AS consumos_usd
        FROM gastos_registros r
        JOIN gastos_tipos t ON t.id = r.gasto_tipo_id
        {filtros}
    """, params).fetchone()
    summary = None
    if resumen_id and str(resumen_id).isdigit():
        summary = conn.execute("""
            SELECT saldo_actual_ars_centavos, saldo_actual_usd_centavos,
                   pago_minimo_ars_centavos
            FROM gastos_tarjeta_resumenes
            WHERE id=? AND fuente='Visa Hipotecario' AND titular_codigo='JOA'
        """, (int(resumen_id),)).fetchone()
    conn.close()

    ars = f"{row['consumos_ars']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    usd = f"{row['consumos_usd']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    balance_ars = summary["saldo_actual_ars_centavos"] / 100 if summary else row["consumos_ars"]
    balance_usd = summary["saldo_actual_usd_centavos"] / 100 if summary else row["consumos_usd"]
    minimum = summary["pago_minimo_ars_centavos"] / 100 if summary else 0
    balance_ars_text = f"{balance_ars:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    balance_usd_text = f"{balance_usd:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    minimum_text = f"{minimum:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return HTMLResponse(content=f'''
        <div class="kpi-card"><h4>SALDO A PAGAR ARS</h4><div class="value val-negative">$ {balance_ars_text}</div></div>
        <div class="kpi-card"><h4>SALDO A PAGAR USD</h4><div class="value val-negative">U$D {balance_usd_text}</div></div>
        <div class="kpi-card"><h4>PAGO MÍNIMO</h4><div class="value">$ {minimum_text}</div></div>
        <div class="kpi-card"><h4>CONSUMOS NETOS · {row['movimientos']} MOV.</h4><div class="value">$ {ars}</div><div style="font-size:.75rem;color:#57606a;margin-top:2px;">U$D {usd}</div></div>
    ''')
