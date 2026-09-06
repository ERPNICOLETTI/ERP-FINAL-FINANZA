from __future__ import annotations

import logging
import os

from modulo_tarjetas import storage_tarjetas
from .payway_resumen_parser import parse

logger = logging.getLogger(__name__)


def procesar_archivo(filepath: str) -> tuple[bool, dict | None]:
    try:
        data = parse(filepath)
        resumen_id, raw_id = storage_tarjetas.ingest_payway_resumen(data)
        return True, {
            'modulo': 'TARJETAS', 'anio': data['fecha_emision'][:4], 'mes': data['fecha_emision'][5:7],
            'entidad': 'PAYWAY_RESUMEN', 'db_table': 'tarjetas_payway_resumenes',
            'id_insertado': resumen_id, 'raw_ingesta_id': raw_id, 'hash_archivo': data['hash_sha256'],
        }
    except Exception as exc:
        logger.exception('No se pudo procesar el resumen Payway %s', os.path.basename(filepath))
        return False, {'error': str(exc)}
