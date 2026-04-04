import pandas as pd
import os
from . import storage_compras as storage

# Lógica del Motor de Facturación (ARCA/CALIM) 🧾🏗️🧠

def resumen_facturacion(anio):
    """Estadísticas de facturas por año. (Usa storage)"""
    return storage.get_resumen_facturacion(anio)

def buscar_global(termino):
    """Busca en facturas por proveedor, numero o id. (Usa storage)"""
    return storage.buscar_facturas(termino)

def reporte_discrepancias():
    """Analiza discrepancias entre fuentes (AFIP vs CALIM). (Usa storage)"""
    return storage.get_reporte_discrepancias()
