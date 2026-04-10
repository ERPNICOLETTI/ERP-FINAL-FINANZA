import os
import re
import logging
from modulo_pagos.storage_pagos import save_pago
from core_sistema.archiver_service import archivar_documento

# LOGIC PAGOS - v5.3.3 (Firmas Correctas + Multi-monto) 🚀🧠⚖️

logger = logging.getLogger(__name__)

# Taxonomía inline (fuente: pagos_recurrentes.md)
TAXONOMIA = {
    'SINDICALES': ['SEC', 'FAECYS', 'INACAP', 'POLICIA', 'SINDICAL'],
    'IMPUESTOS':  ['IIBB', 'IVA', 'GANANCIAS', 'AFIP', 'ARBA', 'AUTONOMO', '931'],
    'SERVICIOS':  ['SERVICOOP', 'REDUNO', 'LUZ', 'GAS', 'AGUA', 'TELEFON', 'ALQUILER', 'TIENDANUBE'],
}

def _clasificar_por_nombre(filename):
    """Clasificación de fallback por nombre de archivo."""
    fname = filename.upper()
    for categoria, conceptos in TAXONOMIA.items():
        for concepto in conceptos:
            if concepto in fname:
                match = re.search(r'_(\d{2})-(\d{4})_', fname)
                anio = match.group(2) if match else None
                mes  = match.group(1) if match else None
                return {
                    'categoria': categoria, 'concepto': concepto,
                    'anio': anio, 'mes': mes,
                    'monto': 0, 'monto_2': 0,
                    'fecha_vencimiento': None, 'fecha_vencimiento_2': None,
                    'es_comprobante': False, 'meta_json': {}
                }
    return {
        'categoria': 'OTROS', 'concepto': 'DESCONOCIDO',
        'anio': None, 'mes': None,
        'monto': 0, 'monto_2': 0,
        'fecha_vencimiento': None, 'fecha_vencimiento_2': None,
        'es_comprobante': False, 'meta_json': {}
    }


def procesar_inbox_pagos(inbox_path):
    """
    Recibe el path del inbox directamente (desde erp_master o llamada directa).
    Parsea PDFs, archiva en Bóveda y persiste en DB.
    """
    if not os.path.exists(inbox_path):
        os.makedirs(inbox_path, exist_ok=True)
        return

    archivos = [f for f in os.listdir(inbox_path) if os.path.isfile(os.path.join(inbox_path, f))]

    for f in archivos:
        path_origen = os.path.join(inbox_path, f)

        # 1. Parser Inteligente de PDF
        info = None
        if f.upper().endswith('.PDF'):
            try:
                from modulo_pagos.parser_pagos import procesar_pago
                ok, data_pdf = procesar_pago(path_origen)
                if ok and data_pdf.get('concepto') not in ['DESCONOCIDO', 'SINDICAL_GENERICO', None]:
                    info = data_pdf
                    # Mapeo de claves para compatibilidad interna
                    info['anio'] = info.get('periodo_anio')
                    info['mes']  = info.get('periodo_mes')
                    # Detectar comprobante por nombre de archivo
                    for kw in ['PAGO', 'COMPROBANTE', 'TICKET', 'RECIBO', 'TRANSFERENCIA']:
                        if kw in f.upper():
                            info['es_comprobante'] = True
                            break
            except Exception as e:
                logger.warning(f"Parser PDF falló para {f}: {e}")

        # 2. Fallback: clasificar por nombre
        if not info:
            info = _clasificar_por_nombre(f)

        print(f"🔍 [PAGOS] {f} -> {info['categoria']} | {info['concepto']}")

        anio = info.get('anio')
        mes  = info.get('mes')

        if not anio or not mes:
            print(f"⚠️ [PAGOS] Sin periodo para {f}, saltando.")
            continue

        # 3. Nombre canónico (Ley de Localía)
        prefijo = "Comprobante" if info.get('es_comprobante') else "Boleta"
        nombre_canonico = f"{prefijo}_{info['concepto']}_{mes}_{anio}.pdf"

        # 4. Archivar en Bóveda
        # archiver_service: archivar_documento(filepath_origen, modulo, anio, mes, entidad, subcategoria, forced_filename)
        # Para PAGOS: entidad=concepto, subcategoria=categoria
        try:
            path_final = archivar_documento(
                filepath_origen=path_origen,
                modulo='pagos',
                anio=anio,
                mes=mes,
                entidad=info['concepto'],
                subcategoria=info['categoria'],
                forced_filename=nombre_canonico
            )

            if not path_final:
                print(f"⚠️ [PAGOS] Archivado retornó None para {f}")
                continue

            # Relativizar path para DB (sin prefijo de disco)
            base_dir = os.path.abspath('.')
            path_relativo = os.path.relpath(path_final, base_dir).replace('\\', '/')

            # 5. Persistir en DB via storage_pagos
            data_sql = {
                'concepto':           info['concepto'],
                'categoria':          info['categoria'],
                'periodo_mes':        mes,
                'periodo_anio':       anio,
                'monto':              info.get('monto') or 0,
                'fecha_vencimiento':  info.get('fecha_vencimiento') or f"{anio}-{mes}-10",
                'monto_2':            info.get('monto_2') or 0,
                'fecha_vencimiento_2':info.get('fecha_vencimiento_2'),
                'meta_json':          info.get('meta_json', {}),
            }

            if info.get('es_comprobante'):
                data_sql['path_comprobante'] = path_relativo
            else:
                data_sql['path_boleta'] = path_relativo

            save_pago(data_sql)
            print(f"✅ [PAGOS] Legajo actualizado para {info['concepto']} {mes}/{anio}")

        except Exception as e:
            print(f"❌ ERROR [{f}]: {e}")
            logger.error(f"Error procesando {f}: {e}", exc_info=True)
