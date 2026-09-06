from __future__ import annotations

import logging
import os
from datetime import datetime

from . import storage_compras
from .calim_facturas_parser import parse

logger = logging.getLogger(__name__)


def procesar_archivo(path: str):
    try:
        data = parse(path)
        result = storage_compras.ingest_calim_compras(data)
        closing = data['fecha_max'] or datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-00-00')
        return True, {
            'modulo': 'COMPRAS', 'anio': closing[:4], 'mes': closing[5:7],
            'entidad': 'CALIM_ESTUDIO', 'db_table': 'compras_calim_ingestas',
            'id_insertado': result['raw_ingesta_id'], 'raw_ingesta_id': result['raw_ingesta_id'],
            'hash_archivo': data['hash_sha256'], **{k: result[k] for k in ('filas','conciliadas','diferencias','solo_calim')},
        }
    except Exception as exc:
        logger.exception('No se pudo procesar CALIM %s', os.path.basename(path))
        return False, {'error': str(exc)}
