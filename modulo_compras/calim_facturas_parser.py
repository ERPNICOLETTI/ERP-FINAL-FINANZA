from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

PARSER_VERSION = 'calim-compras/1.0.0'
TYPE_CODES = {
    'Factura A': 1, 'Nota de Débito A': 2, 'Nota de Crédito A': 3,
    'Factura B': 6, 'Nota de Débito B': 7, 'Nota de Crédito B': 8,
    'Factura C': 11, 'Nota de Débito C': 12, 'Nota de Crédito C': 13,
    'Factura M': 51, 'Nota de Débito M': 52, 'Nota de Crédito M': 53,
    'Liquidación A': 63, 'Liquidación B': 64,
    'FACTURA A CON LEYENDA "OPERACIÓN SUJETA A RETENCIÓN"': 1,
}
CREDIT_TYPES = {3, 8, 13, 53}
REQUIRED = {'Fecha', 'Proveedor', 'Tipo', 'Numero', 'Neto', 'Iva', 'Total'}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _cents(value) -> int:
    if value is None or pd.isna(value):
        return 0
    # Falla histórica de CALIM: celdas numéricas son centavos sin separador.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    raw = str(value).strip().replace('$', '').replace(' ', '')
    if not raw:
        return 0
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
        multiplier = 100
    else:
        # Texto sin separador se interpreta como pesos; el bug solo afecta celdas numéricas.
        multiplier = 100
    try:
        return int((Decimal(raw) * multiplier).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ValueError(f'Importe CALIM inválido: {value!r}') from exc


def _date(value) -> str:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.date().isoformat()
    raw = str(value).strip()
    for pattern in ('%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f'Fecha CALIM inválida: {value!r}')


def parse(path: str) -> dict:
    source = Path(path).resolve()
    frame = pd.read_excel(source, engine='calamine', dtype=object)
    missing = REQUIRED.difference(frame.columns)
    if missing:
        raise ValueError(f'Excel CALIM sin columnas: {sorted(missing)}')
    rows = []
    raw_rows = []
    for index, item in frame.iterrows():
        if pd.isna(item.get('Numero')) or pd.isna(item.get('Total')):
            continue
        provider = str(item['Proveedor']).strip()
        provider_match = re.match(r'^(\d{11})\s*-\s*(.+)$', provider)
        if not provider_match:
            raise ValueError(f'Proveedor CALIM sin CUIT en fila {index + 2}: {provider}')
        number_match = re.match(r'^\s*(\d+)\s*-\s*(\d+)\s*$', str(item['Numero']))
        if not number_match:
            raise ValueError(f'Número CALIM inválido en fila {index + 2}: {item["Numero"]}')
        type_name = str(item['Tipo']).strip()
        type_code = TYPE_CODES.get(type_name)
        if type_code is None:
            raise ValueError(f'Tipo CALIM desconocido en fila {index + 2}: {type_name}')
        sign = -1 if type_code in CREDIT_TYPES else 1
        row = {
            'numero_linea': index + 2, 'fecha': _date(item['Fecha']),
            'cuit_proveedor': provider_match.group(1), 'proveedor': provider_match.group(2).strip(),
            'tipo_comprobante': type_name, 'tipo_comprobante_codigo': type_code,
            'punto_venta': number_match.group(1).zfill(5), 'numero_comprobante': number_match.group(2).zfill(8),
            'signo': sign, 'neto_centavos': _cents(item['Neto']) * sign,
            'iva_total_centavos': _cents(item['Iva']) * sign, 'total_centavos': _cents(item['Total']) * sign,
        }
        rows.append(row)
        raw_rows.append({key: (None if pd.isna(value) else str(value)) for key, value in item.to_dict().items()})
    raw_content = json.dumps({'hoja': 'Sheet1', 'columnas': list(frame.columns), 'filas': raw_rows}, ensure_ascii=False)
    dates = [row['fecha'] for row in rows]
    return {
        'path_archivo': source.as_posix(), 'nombre_archivo': source.name, 'hash_sha256': _sha256(source),
        'parser_version': PARSER_VERSION, 'contenido_raw': raw_content, 'filas': rows,
        'fecha_min': min(dates) if dates else None, 'fecha_max': max(dates) if dates else None,
    }
