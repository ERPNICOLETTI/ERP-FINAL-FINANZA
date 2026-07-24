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
