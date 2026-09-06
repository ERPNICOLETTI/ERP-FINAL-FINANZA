from __future__ import annotations

import logging
import os

from modulo_tarjetas import storage_tarjetas
from .payway_movimientos_parser import parse

logger = logging.getLogger(__name__)


def procesar_archivo(filepath: str) -> tuple[bool, dict | None]:
    try:
        data = parse(filepath)
        count, raw_id = storage_tarjetas.ingest_payway_movimientos(data)
        # Payway se concilia y archiva por fecha de pago, no por fecha de compra.
        # Un archivo puede cubrir varios meses: se archiva por el cierre del rango.
        first_date = max(row['fecha_pago'] for row in data['movimientos'])
        return True, {
            'modulo': 'TARJETAS', 'anio': first_date[:4], 'mes': first_date[5:7],
            'entidad': 'PAYWAY_MOVIMIENTOS', 'db_table': 'tarjetas_payway_movimientos',
            'id_insertado': raw_id, 'raw_ingesta_id': raw_id, 'hash_archivo': data['hash_sha256'], 'filas': count,
        }
    except Exception as exc:
        logger.exception('No se pudo procesar movimientos Payway %s', os.path.basename(filepath))
        return False, {'error': str(exc)}
