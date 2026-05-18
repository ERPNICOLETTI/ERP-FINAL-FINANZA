import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'erp_nicoletti.db')

def get_categorias_from_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    rows = cursor.execute("SELECT nombre, palabras_clave, tipo FROM categorias_maestras").fetchall()
    conn.close()
    return rows

def categorizar_movimiento(descripcion: str, importe: float) -> str:
    """
    Motor de Reglas Dinámico para Auto-Conciliación de Bancos.
    Lee las palabras clave directamente de la tabla raíz 'categorias_maestras'.
    """
    desc = descripcion.lower()
    
    categorias = get_categorias_from_db()
    
    # 1. Movimientos Internos y Pago de Tarjeta (se chequean sin importar signo si hace falta)
    # Buscamos primero "Pago Tarjeta" y "Movimiento Interno"
    for nombre, palabras, tipo in categorias:
        if nombre in ["Pago Tarjeta", "Movimiento Interno"]:
            keywords = [k.strip() for k in palabras.split(',') if k.strip()]
            for kw in keywords:
                if kw in desc:
                    return nombre
                    
    # 2. Filtrar por tipo (INGRESO O EGRESO)
    if importe > 0:
        # Buscar en Ingresos
        for nombre, palabras, tipo in categorias:
            if tipo == 'INGRESO' and palabras:
                keywords = [k.strip() for k in palabras.split(',') if k.strip()]
                for kw in keywords:
                    if kw in desc:
                        return nombre
        return "Otros Ingresos"
    else:
        # Buscar en Egresos
        for nombre, palabras, tipo in categorias:
            if tipo == 'EGRESO' and palabras:
                keywords = [k.strip() for k in palabras.split(',') if k.strip()]
                for kw in keywords:
                    if kw in desc:
                        return nombre
        return "Otros"
