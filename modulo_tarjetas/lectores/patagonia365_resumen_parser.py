from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import pdfplumber

PARSER_VERSION = 'patagonia365-resumen/1.0.0'


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _cents(value: str) -> int:
    raw = value.strip().replace('$', '').replace(' ', '').replace('.', '').replace(',', '.')
    try:
        return int((Decimal(raw) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ValueError(f'Importe Patagonia 365 inválido: {value!r}') from exc


def _date(value: str) -> str:
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def _required(pattern: str, text: str, label: str, flags: int = 0):
    match = re.search(pattern, text, flags)
    if not match:
        raise ValueError(f'No se encontró {label} en el resumen Patagonia 365')
    return match


def parse(path: str) -> dict:
    source = Path(path).resolve()
    with pdfplumber.open(source) as pdf:
        pages = [page.extract_text(x_tolerance=2, y_tolerance=3) or '' for page in pdf.pages]
    text = '\n'.join(pages)

    period = _required(r'Periodo Liquidado:\s*(\d{4}-\d{2})', text, 'período').group(1)
    summary_number = _required(r'N.?\s*Resumen:\s*(\d+)', text, 'número de resumen').group(1)
    merchant = _required(r'Comercio:\s*([\d-]+)', text, 'comercio').group(1)
    merchant_id = _required(r'ID Comercio:\s*(\d+)', text, 'ID de comercio').group(1)
    cuit = _required(r'CUIT:\s*([\d-]+)', text, 'CUIT').group(1)

    detail_pattern = re.compile(
        r'^(\d{8})\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+'
        r'([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+'
        r'([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})$', re.MULTILINE)
    settlements = []
    for number, payment, presentation, gross, fee, financing, other, taxes, net in detail_pattern.findall(text):
        settlements.append({
            'numero_liquidacion': number,
            'fecha_pago': _date(payment),
            'fecha_presentacion': _date(presentation),
            'bruto_centavos': _cents(gross),
            'arancel_centavos': _cents(fee),
            'financiero_centavos': _cents(financing),
            'otras_deducciones_centavos': _cents(other),
            'deducciones_impositivas_centavos': _cents(taxes),
            'neto_centavos': _cents(net),
        })
    if not settlements:
        raise ValueError('El resumen Patagonia 365 no contiene liquidaciones reconocibles')

    totals = _required(
        r'Monto Presentado\s+Arancel\s+Costo Financiero\s+Otros Cargos\s+Promociones\s*\n'
        r'([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+'
        r'([\d.]+,\d{2})\s+([\d.]+,\d{2})', text, 'totales')
    tax_totals = _required(
        r'IVA RI\s+IVA Retenci.n\s+IVA Retenci.n Ganancias.*?\n'
        r'([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+'
        r'([\d.]+,\d{2})\s+([\d.]+,\d{2})', text, 'impuestos', re.DOTALL)
    net = _cents(_required(r'Importe Neto\s*\n\$\s*([\d.]+,\d{2})', text, 'importe neto').group(1))

    result = {
        'path_archivo': source.as_posix(),
        'nombre_archivo': source.name,
        'hash_sha256': _sha256(source),
        'parser_version': PARSER_VERSION,
        'contenido_raw': json.dumps({'paginas': pages}, ensure_ascii=False),
        'periodo': period,
        'numero_resumen': summary_number.zfill(8),
        'comercio': merchant,
        'comercio_id': merchant_id,
        'cuit': re.sub(r'\D', '', cuit),
        'bruto_centavos': _cents(totals.group(1)),
        'arancel_centavos': _cents(totals.group(2)),
        'financiero_centavos': _cents(totals.group(3)),
        'otros_cargos_centavos': _cents(totals.group(4)),
        'promociones_centavos': _cents(totals.group(5)),
        'iva_ri_centavos': _cents(tax_totals.group(1)),
        'retencion_iva_centavos': _cents(tax_totals.group(2)) + _cents(tax_totals.group(3)),
        'retencion_ganancias_centavos': _cents(tax_totals.group(4)),
        'retencion_iibb_centavos': _cents(tax_totals.group(5)),
        'neto_centavos': net,
        'liquidaciones': settlements,
    }

    summed = {key: sum(row[key] for row in settlements) for key in (
        'bruto_centavos', 'arancel_centavos', 'financiero_centavos',
        'otras_deducciones_centavos', 'deducciones_impositivas_centavos', 'neto_centavos')}
    expected = {
        'bruto_centavos': result['bruto_centavos'],
        'arancel_centavos': result['arancel_centavos'],
        'financiero_centavos': result['financiero_centavos'],
        'otras_deducciones_centavos': result['otros_cargos_centavos'],
        'deducciones_impositivas_centavos': result['iva_ri_centavos'] + result['retencion_iva_centavos']
            + result['retencion_ganancias_centavos'] + result['retencion_iibb_centavos'],
        'neto_centavos': result['neto_centavos'],
    }
    if summed != expected:
        raise ValueError(f'El detalle Patagonia 365 no concilia con la cabecera: detalle={summed}, cabecera={expected}')
    calculated_net = (result['bruto_centavos'] - result['arancel_centavos'] - result['financiero_centavos']
                      - result['otros_cargos_centavos'] - result['iva_ri_centavos']
                      - result['retencion_iva_centavos'] - result['retencion_ganancias_centavos']
                      - result['retencion_iibb_centavos'] + result['promociones_centavos'])
    if calculated_net != result['neto_centavos']:
        raise ValueError(f'El neto Patagonia 365 no concilia: calculado={calculated_net}, informado={result["neto_centavos"]}')
    return result
