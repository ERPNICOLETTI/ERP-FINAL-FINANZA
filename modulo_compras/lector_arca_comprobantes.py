from __future__ import annotations

import logging
import os

from . import storage_compras
from .arca_comprobantes_parser import parse_csv, parse_zip

logger = logging.getLogger(__name__)


def procesar_archivo(path: str):
    try:
        package = parse_zip(path) if path.lower().endswith('.zip') else parse_csv(path)
        result = storage_compras.ingest_arca_recibidos(package)
        return True, {
            'modulo': 'COMPRAS', 'anio': package['fecha_max'][:4], 'mes': package['fecha_max'][5:7],
            'entidad': 'ARCA_RECIBIDOS', 'db_table': 'compras_arca_ingestas',
            'id_insertado': result['zip_raw_ingesta_id'], 'hash_archivo': package['hash_sha256'],
            'filas': result['filas'], 'raw_ingesta_id': result['zip_raw_ingesta_id'],
        }
    except Exception as exc:
        logger.exception('No se pudo procesar el ZIP ARCA %s', os.path.basename(path))
        return False, {'error': str(exc)}
