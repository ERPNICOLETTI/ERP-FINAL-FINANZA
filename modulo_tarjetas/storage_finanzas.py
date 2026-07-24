import sqlite3
import os

# REPOSITORIO DE PERSISTENCIA Y CONCILIACIÓN DE FINANZAS v1.0.0 📊🧠⚖️

DB_PATH = 'c:/Users/essao/Desktop/ERP FINAL/erp_nicoletti.db'
ADM_GLOBAL_PATH = 'c:/Users/essao/Desktop/ERP FINAL/admglobal.db'

def get_db_connection():
    """Retorna una conexión activa con WAL habilitado y admglobal.db adjunta para consultas de conciliación."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    
    # Adjuntar base de datos histórica del local
    if os.path.exists(ADM_GLOBAL_PATH):
        conn.execute(f"ATTACH DATABASE '{ADM_GLOBAL_PATH}' AS adm_local")
    return conn


def obtener_reporte_conciliacion(anio: str = None, mes: str = None) -> list:
    """
    Ejecuta el cruce de conciliación en cascada:
    Ventas del Local -> Lotes Diarios de Liquidaciones (tarjetas_liquidaciones_detalles) -> Banco (bancos_movimientos)
    """
    conn = get_db_connection()
    
    # Validar si admglobal está adjuntada correctamente
    has_adm = False
    try:
        conn.execute("SELECT count(*) FROM adm_local.Documentos")
        has_adm = True
    except:
        pass
        
    if not has_adm:
        conn.close()
        return []
        
    # Query que cruza las ventas con tarjeta del local con las liquidaciones de tarjetas detalladas
    # y posteriormente busca la acreditación del neto del lote en el banco (Galicia o Chubut)
    query = """
        SELECT 
            d.idDocumento,
            d.FechaDocumento as fecha_venta,
            d.NroDocumento,
            d.PagoTarjeta as monto_venta,
            d.NombreClienteEventual as cliente,
            -- Cruzar con Liquidaciones detalladas de Payway/Naranja (Monto Neto esperado)
            ld.monto_neto as monto_liquidado,
            ld.descripcion as lote_descripcion,
            l.marca as tarjeta_marca,
            l.fuente as liquidacion_fuente,
            -- Cruzar con Acreditaciones de Bancos
            bm.importe_total_dia as monto_acreditado,
            bm.fecha_iso as fecha_acreditacion,
            bm.banco as banco_destino,
            bm.cuenta as cuenta_destino,
            bm.descripcion_banco as banco_descripcion
        FROM adm_local.Documentos d
        -- Unir con los detalles de liquidación (por monto bruto aproximado y fecha cercana)
        LEFT JOIN main.tarjetas_liquidaciones_detalles ld ON (
            abs(ld.monto_bruto - d.PagoTarjeta) < 1.0
            AND abs(julianday(ld.fecha) - julianday(strftime('%Y-%m-%d', d.FechaDocumento))) <= 3
        )
        LEFT JOIN main.tarjetas_liquidaciones l ON ld.liquidacion_id = l.id
        -- Unir con la sumatoria agrupada de depósitos de tarjetas por día en banco
        LEFT JOIN (
            SELECT 
                -- Normalizar fecha a formato YYYY-MM-DD
                case 
                    when fecha LIKE '%/%' then 
                        substr(fecha, 7, 4) || '-' || substr(fecha, 4, 2) || '-' || substr(fecha, 1, 2)
                    else fecha 
                end as fecha_iso,
                banco,
                cuenta,
                sum(importe) as importe_total_dia,
                group_concat(descripcion, ' | ') as descripcion_banco
            FROM main.bancos_movimientos
            WHERE importe > 0
              AND (descripcion LIKE '%PRISMA%' OR descripcion LIKE '%LIQUID COMERC%' OR descripcion LIKE '%ACREDIT%')
            GROUP BY fecha_iso, banco, cuenta
        ) bm ON (
            -- Comparación de fecha cercana de cobro (máximo 4 días hábiles de clearing)
            abs(julianday(bm.fecha_iso) - julianday(ld.fecha)) <= 4
            -- Y que el importe consolidado coincida con tolerancia del 2% por Sircreb/CFT
            AND (ld.monto_neto > 0 AND abs(bm.importe_total_dia - ld.monto_neto) / ld.monto_neto <= 0.02)
        )
        WHERE d.PagoTarjeta > 0 
          AND d.DocAnulado = 0
    """
    
    params = []
    if anio:
        query += " AND strftime('%Y', d.FechaDocumento) = ?"
        params.append(anio)
    if mes:
        query += " AND strftime('%m', d.FechaDocumento) = ?"
        params.append(mes)
        
    query += " ORDER BY d.FechaDocumento DESC"
    
    rows = conn.execute(query, params).fetchall()
    
    reporte = []
    for r in rows:
        m_venta = r['monto_venta'] or 0.0
        m_liq = r['monto_liquidado']
        m_acre = r['monto_acreditado']
        
        # Determinar el estado contable real
        if m_acre and m_acre > 0:
            estado = "ACREDITADO"
            color = "success"
        elif m_liq and m_liq > 0:
            estado = "LIQUIDADO"
            color = "warning"
        else:
            estado = "PENDIENTE"
            color = "danger"
            
        banco_info = "-"
        if r['banco_destino']:
            banco_info = f"{r['banco_destino']} ({r['cuenta_destino']})"
            
        reporte.append({
            "id": r['idDocumento'],
            "fecha": r['fecha_venta'].split(' ')[0] if r['fecha_venta'] else "",
            "comprobante": r['NroDocumento'],
            "cliente": r['cliente'] or "Consumidor Final",
            "monto_venta": m_venta,
            "monto_liquidado": m_liq or 0.0,
            "monto_acreditado": m_acre or 0.0,
            "tarjeta": r['tarjeta_marca'] or "TARJETA",
            "banco": banco_info,
            "lote": r['lote_descripcion'] or "-",
            "estado": estado,
            "color": color,
            "tasa_descuento": round(((m_venta - m_liq) / m_venta * 100), 2) if m_liq and m_venta > 0 else 0.0
        })
        
    conn.close()
    return reporte

def obtener_kpis_finanzas(anio: str = None, mes: str = None) -> dict:
    """Calcula KPIs generales de facturación del local, retenciones estimadas y estado de cobros de tarjetas."""
    conn = get_db_connection()
    
    # Validar si admglobal está adjuntada correctamente
    has_adm = False
    try:
        conn.execute("SELECT count(*) FROM adm_local.Documentos")
        has_adm = True
    except:
        pass
        
    if not has_adm:
        conn.close()
        return {
            "total_ventas": 0.0,
            "ventas_tarjetas": 0.0,
            "comisiones_aranceles": 0.0,
            "tasa_acreditacion": 0.0
        }
        
    # 1. Total Ventas del Local (Efectivo + Tarjeta)
    q_ventas = "SELECT sum(ValorAPagar) as total, sum(PagoTarjeta) as tarjetas FROM adm_local.Documentos WHERE DocAnulado = 0"
    params = []
    if anio:
        q_ventas += " AND strftime('%Y', FechaDocumento) = ?"
        params.append(anio)
    if mes:
        q_ventas += " AND strftime('%m', FechaDocumento) = ?"
        params.append(mes)
        
    r_ventas = conn.execute(q_ventas, params).fetchone()
    total_ventas = r_ventas['total'] or 0.0
    ventas_tarjetas = r_ventas['tarjetas'] or 0.0
    
    # 2. Total Retenciones y Aranceles en Liquidaciones de Payway
    q_liq = "SELECT sum(costo_arancel + costo_financiero + iva_21 + iva_105 + retenciones) as costos FROM main.tarjetas_liquidaciones"
    params_liq = []
    if anio and mes:
        q_liq += " WHERE periodo = ?"
        params_liq.append(f"{anio}-{mes}")
    elif anio:
        q_liq += " WHERE strftime('%Y', fecha_liquidacion) = ?"
        params_liq.append(anio)
        
    r_liq = conn.execute(q_liq, params_liq).fetchone()
    costos_liq = r_liq['costos'] or 0.0
    
    # 3. Calcular porcentaje de acreditación
    # Cuántas ventas con tarjeta tienen correspondencia en bancos
    reporte = obtener_reporte_conciliacion(anio, mes)
    acreditadas = sum(1 for x in reporte if x['estado'] == "ACREDITADO")
    totales = len(reporte) if len(reporte) > 0 else 1
    tasa_acre = (acreditadas / totales) * 100
    
    conn.close()
    return {
        "total_ventas": total_ventas,
        "ventas_tarjetas": ventas_tarjetas,
        "comisiones_aranceles": costos_liq,
        "tasa_acreditacion": round(tasa_acre, 1)
    }

def obtener_auditoria_clearing(anio: str, mes: str) -> dict:
    """Retorna los matches consolidados, depósitos huérfanos y liquidaciones huérfanas de un mes."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    periodo_tarjetas = f"{anio}-{mes}" if mes else anio
    mes_banco = f"/{mes}/{anio}" if mes else f"/{anio}"
    
    # 1. Obtener todas las liquidaciones detalladas (diarias) del período
    if mes:
        query_liq = """
            SELECT ld.fecha, ld.monto_bruto, ld.monto_neto, l.marca, ld.descripcion as lote_desc
            FROM main.tarjetas_liquidaciones_detalles ld
            JOIN main.tarjetas_liquidaciones l ON ld.liquidacion_id = l.id
            WHERE l.fuente = 'PAYWAY'
              AND l.periodo = ?
            ORDER BY ld.fecha ASC
        """
        liquidaciones = conn.execute(query_liq, (periodo_tarjetas,)).fetchall()
    else:
        query_liq = """
            SELECT ld.fecha, ld.monto_bruto, ld.monto_neto, l.marca, ld.descripcion as lote_desc
            FROM main.tarjetas_liquidaciones_detalles ld
            JOIN main.tarjetas_liquidaciones l ON ld.liquidacion_id = l.id
            WHERE l.fuente = 'PAYWAY'
              AND l.periodo LIKE ?
            ORDER BY ld.fecha ASC
        """
        liquidaciones = conn.execute(query_liq, (f"{anio}-%",)).fetchall()
    
    # 2. Obtener todas las acreditaciones de tarjetas en Chubut (incluidos débitos para compensar)
    query_bco = """
        SELECT id, fecha, descripcion, importe
        FROM main.bancos_movimientos
        WHERE banco = 'CHUBUT'
          AND cuenta = 'CA$ ...00106'
          AND (descripcion LIKE '%PRISMA%' OR descripcion LIKE '%LIQUID COMERC%' OR descripcion LIKE '%ACREDIT%')
    """
    depósitos_raw = conn.execute(query_bco).fetchall()
    
    # Filtrar depósitos por mes
    depósitos_chubut = []
    for d in depósitos_raw:
        fecha_d = d['fecha']
        # Buscar si coincide con el mes/año
        if mes_banco in fecha_d or (fecha_d.startswith(f"{anio}-{mes}") if mes else False):
            depósitos_chubut.append({
                'id': d['id'],
                'fecha': fecha_d,
                'descripcion': d['descripcion'],
                'importe': d['importe'],
                'usado': False
            })
            
    matches = []
    liquidaciones_huerfanas = []
    
    from datetime import datetime
    
    # Auxiliar para normalizar fecha a un objeto datetime real
    def parse_fecha(d_str):
        if not d_str: return None
        d_str = d_str.strip()
        # Probar formato DD/MM/YYYY
        if "/" in d_str:
            try:
                return datetime.strptime(d_str, "%d/%m/%Y")
            except:
                pass
        # Probar formato YYYY-MM-DD
        if "-" in d_str:
            try:
                return datetime.strptime(d_str[:10], "%Y-%m-%d")
            except:
                pass
        return None
        
    for l in liquidaciones:
        fecha_pago_dt = parse_fecha(l['fecha'])
        if not fecha_pago_dt:
            continue
            
        neto = l['monto_neto']
        bruto = l['monto_bruto']
        
        # Agrupamos movimientos del banco por día en un rango de 0 a 4 días posteriores
        deps_por_dia = {}
        for dep in depósitos_chubut:
            if dep['usado']:
                continue
            try:
                diff_days = (parse_fecha(dep['fecha']) - fecha_pago_dt).days
            except:
                diff_days = 999
                
            if 0 <= diff_days <= 4:
                f_str = dep['fecha']
                if f_str not in deps_por_dia:
                    deps_por_dia[f_str] = []
                deps_por_dia[f_str].append(dep)
                
        match_dia = None
        
        # Buscar en qué día hay una combinación exacta de movimientos que sumados/restados den el neto esperado
        for f_str, list_movs in deps_por_dia.items():
            # Caso A: Match 1:1 estricto
            for d in list_movs:
                if abs(d['importe'] - neto) < 5.0:
                    match_dia = [d]
                    break
            if match_dia:
                break
                
            # Caso B: Combinatoria de 2 movimientos del mismo día (ej. desdoblamiento de banco o débito compensatorio)
            n_movs = len(list_movs)
            for i in range(n_movs):
                for j in range(i + 1, n_movs):
                    suma_2 = list_movs[i]['importe'] + list_movs[j]['importe']
                    if abs(suma_2 - neto) < 5.0:
                        match_dia = [list_movs[i], list_movs[j]]
                        break
                if match_dia:
                    break
            if match_dia:
                break
                
            # Caso C: Combinatoria de 3 movimientos del mismo día
            for i in range(n_movs):
                for j in range(i + 1, n_movs):
                    for k in range(j + 1, n_movs):
                        suma_3 = list_movs[i]['importe'] + list_movs[j]['importe'] + list_movs[k]['importe']
                        if abs(suma_3 - neto) < 5.0:
                            match_dia = [list_movs[i], list_movs[j], list_movs[k]]
                            break
                    if match_dia:
                        break
                if match_dia:
                    break
            if match_dia:
                break
                
        if match_dia:
            is_desdoblado = len(match_dia) > 1
            for d in match_dia:
                d['usado'] = True
                fecha_acre_str = parse_fecha(d['fecha']).strftime("%Y-%m-%d") if parse_fecha(d['fecha']) else d['fecha']
                
                matches.append({
                    "fecha_lote": l['fecha'],
                    "marca": l['marca'],
                    "bruto": bruto,
                    "neto": neto,
                    "lote": l['lote_desc'] or "-",
                    "fecha_acreditacion": fecha_acre_str,
                    "acreditado": d['importe'],
                    "diferencia": 0.0 if not is_desdoblado else d['importe'], # mostramos el importe individual para que sume visualmente
                    "banco_desc": d['descripcion'],
                    "tipo_match": "DESDOBLADO" if is_desdoblado else "DIRECTO"
                })
        else:
            liquidaciones_huerfanas.append({
                "fecha_lote": l['fecha'],
                "marca": l['marca'],
                "bruto": bruto,
                "neto": neto,
                "lote": l['lote_desc'] or "-"
            })
            
    # Depósitos huérfanos son los no marcados
    depósitos_huerfanos = []
    for d in depósitos_chubut:
        if not d['usado'] and ("LIQUID COMERC" in d['descripcion'] or "PRISMA" in d['descripcion']):
            fecha_d_dt = parse_fecha(d['fecha'])
            fecha_d_str = fecha_d_dt.strftime("%Y-%m-%d") if fecha_d_dt else d['fecha']
            depósitos_huerfanos.append({
                "fecha": fecha_d_str,
                "importe": d['importe'],
                "descripcion": d['descripcion']
            })
            
    conn.close()
    return {
        "matches": matches,
        "liquidaciones_huerfanas": liquidaciones_huerfanas,
        "depositos_huerfanos": depósitos_huerfanos
    }

