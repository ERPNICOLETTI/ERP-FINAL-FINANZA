def categorizar_movimiento(descripcion: str, importe: float) -> str:
    """
    Motor de Reglas para Auto-Conciliación de Bancos.
    Analiza la descripción y el monto para asignar una categoría dura.
    """
    desc = descripcion.lower()
    
    # 1. Movimientos Internos (No alteran el patrimonio)
    if "ctas propias" in desc or "cuenta propia" in desc or "extraccion" in desc or "cajero automatico" in desc:
        return "MOVIMIENTO_INTERNO"
        
    # 2. Ventas y Cobros (Entradas de plata de 3ros)
    elif "transferencia de terceros" in desc and importe > 0:
        return "VENTA_COBRO"
    elif "credito transferencia coelsa" in desc and importe > 0:
        return "VENTA_COBRO"
    elif "recaudacion" in desc or "liquid" in desc or "payway" in desc or "naranja" in desc:
        return "VENTA_COBRO" # Liquidaciones de tarjetas
        
    # 3. Comisiones e Impuestos del Banco
    elif "i.v.a" in desc or "iva" in desc or "sircreb" in desc or "comision" in desc or "mantenimiento" in desc or "impuesto" in desc or "perc." in desc or "percepcion" in desc or "iibb" in desc or "ley 25413" in desc:
        return "IMPUESTOS_Y_COMISIONES"
        
    # 4. Sueldos y Honorarios
    elif "haberes" in desc or "sueldo" in desc or "honorarios" in desc:
        return "SUELDOS_HONORARIOS"
        
    # 5. Gastos Específicos (Supermercados, Salud, Servicios, Personales)
    elif "coto" in desc or "carrefour" in desc or "jumbo" in desc or "dia " in desc or "almacen" in desc or "supermercado" in desc or "fiambreria" in desc:
        return "GASTO_SUPERMERCADO"
    elif "psicologo" in desc or "cosmetologa" in desc or "farmacia" in desc or "farmacity" in desc or "osde" in desc or "galeno" in desc or "swiss medical" in desc or "salud" in desc or "medico" in desc:
        return "GASTO_SALUD"
    elif "edesur" in desc or "edenor" in desc or "ayesa" in desc or "metrogas" in desc or "telecom" in desc or "personal" in desc or "movistar" in desc or "claro" in desc or "internet" in desc or "wifi" in desc:
        return "GASTO_SERVICIOS"
    elif "netflix" in desc or "spotify" in desc or "steam" in desc or "cine" in desc or "restaurante" in desc or "pedidosya" in desc or "rappi" in desc or "mcdonalds" in desc or "burger" in desc:
        return "GASTO_PERSONAL"

    # 6. Pagos a Proveedores / Gastos del Negocio
    elif "compra debito" in desc or "pago mis cuentas" in desc or "debito automatico" in desc or "pago tj" in desc:
        return "GASTO_NEGOCIO"
    elif "transferencia de terceros" in desc and importe < 0:
        return "GASTO_NEGOCIO" # Transferencia enviada a un proveedor/empleado
        
    # 7. Devoluciones de compras
    elif "dev.compra" in desc or "devolucion" in desc or "reverso" in desc:
        return "DEVOLUCION_GASTO"
        
    return "SIN_CATEGORIZAR"
