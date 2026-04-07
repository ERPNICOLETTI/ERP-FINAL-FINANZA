import os
import re
from datetime import datetime
from . import storage_pagos as storage
from core_sistema import archiver_service

# LÓGICA DE INTELIGENCIA DE PAGOS - v5.2.0 🧠💳🚀

class PagosClassifier:
    def __init__(self):
        self.taxonomia = self._load_taxonomia()
        self.keywords_comprobante = ['PAGO', 'COMPROBANTE', 'TICKET', 'RECIBO', 'TRANSFERENCIA']

    def _load_taxonomia(self):
        """Carga la taxonomía desde pagos_recurrentes.md."""
        tax = {}
        # Ruta absoluta para evitar fallos de importación
        base_path = os.path.dirname(os.path.abspath(__file__))
        md_path = os.path.join(base_path, 'pagos_recurrentes.md')
        
        if not os.path.exists(md_path):
            return {
                'SERVICIOS': ['SERVICOOP', 'REDUNO', 'ALQUILER', 'TIENDANUBE', 'CONTADOR', 'SEGURO'],
                'IMPUESTOS': ['931', 'AUTONOMO', 'IVA'],
                'SINDICALES': ['SEC', 'FAECYS', 'POLICIA', 'INACAP']
            }

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        categories = re.findall(r'### .*?\((.*?)\)\n(.*?)(?=\n###|---|$)', content, re.DOTALL)
        for cat_name, entries in categories:
            items = re.findall(r'-\s*\*\*([\w\d]+)\*\*', entries)
            tax[cat_name.upper()] = [i.upper() for i in items]
        
        return tax

    def clasificar(self, filename):
        """Identifica categoría, concepto y tipo de documento."""
        f_upper = filename.upper()
        res = {
            'categoria': 'OTROS',
            'concepto': 'DESCONOCIDO',
            'es_comprobante': False
        }

        # 1. Identificar Concepto y Categoría
        for cat, items in self.taxonomia.items():
            for item in items:
                if item in f_upper:
                    res['categoria'] = cat
                    res['concepto'] = item
                    break
        
        # 2. Identificar si es comprobante de pago
        for kw in self.keywords_comprobante:
            if kw in f_upper:
                res['es_comprobante'] = True
                break
                
        return res

def procesar_inbox_pagos(inbox_path):
    """Orquestador de legajo único para el Módulo Pagos."""
    classifier = PagosClassifier()
    archivos = [f for f in os.listdir(inbox_path) if os.path.isfile(os.path.join(inbox_path, f))]
    
    for f in archivos:
        path_origen = os.path.join(inbox_path, f)
        info = classifier.clasificar(f)
        
        print(f"🔍 [PAGOS] Clasificando {f} -> {info['categoria']} | {info['concepto']}")
        
        # Fecha para el archivado (asumimos hoy si no hay fecha en el nombre)
        hoy = datetime.now()
        anio = hoy.year
        mes = hoy.month
        
        # Archivado Jerárquico: modulo_pagos/archivos_pagos/[CATEGORIA]/[AÑO]/[MES]/[CONCEPTO]/
        # Usamos subcategoria = CATEGORIA/CONCEPTO para forzar el legajo único
        target_subcat = f"{info['categoria']}/{info['concepto']}"
        
        path_final = archiver_service.archivar_documento(
            filepath_origen=path_origen,
            modulo='PAGOS',
            anio=anio,
            mes=mes,
            entidad=info['concepto'],
            subcategoria=info['categoria'] # Pasamos la categoría como subcategoria principal
        )
        
        if path_final:
            data_sql = {
                'concepto': info['concepto'],
                'categoria': info['categoria'],
                'fecha_vencimiento': f"{anio}-{mes:02d}-01", # Estimado inicial
            }
            
            if info['es_comprobante']:
                data_sql['path_comprobante'] = path_final
            else:
                data_sql['path_boleta'] = path_final
                
            storage.save_pago(data_sql)
            print(f"✅ [PAGOS] Legajo actualizado para {info['concepto']}")
