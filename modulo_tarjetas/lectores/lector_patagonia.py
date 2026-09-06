from __future__ import annotations

import logging

from modulo_tarjetas import storage_tarjetas as storage
from modulo_tarjetas.lectores.patagonia365_resumen_parser import parse

logger = logging.getLogger(__name__)


def procesar_archivo(file_path: str):
    """Ingiere un resumen mensual Patagonia 365 mediante el flujo ELT."""
    try:
        data = parse(file_path)
        summary_id, raw_id = storage.ingest_patagonia_resumen(data)
        return True, {
            'modulo': 'TARJETAS',
            'anio': data['periodo'][:4],
            'mes': data['periodo'][5:7],
            'entidad': 'PATAGONIA365_LIQUIDACIONES_VENTAS',
            'db_table': 'tarjetas_patagonia_resumenes',
            'id_insertado': summary_id,
            'raw_ingesta_id': raw_id,
            'hash_archivo': data['hash_sha256'],
            'filas': len(data['liquidaciones']),
        }
    except Exception as exc:
        logger.exception('No se pudo procesar Patagonia 365')
        return False, {'error': str(exc)}


def parse_patagonia_365(file_path: str):
    """Compatibilidad con la API histórica."""
    success, info = procesar_archivo(file_path)
    if not success:
        raise ValueError(info.get('error', 'Error Patagonia 365'))
    return info
