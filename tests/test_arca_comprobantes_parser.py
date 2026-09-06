from pathlib import Path

import pytest

from modulo_compras.arca_comprobantes_parser import parse_zip


FILES = {
    'comprobantes_consulta_csv_recibidos_209469520_27329549971_20260906-0928.zip': (28, '2026-08-04', '2026-08-29'),
    'comprobantes_consulta_csv_recibidos_209469591_27329549971_20260906-0929.zip': (6, '2026-09-01', '2026-09-04'),
    'comprobantes_consulta_csv_recibidos_209469560_27329549971_20260906-0929.zip': (176, '2026-01-04', '2026-06-30'),
    'comprobantes_consulta_csv_recibidos_209469533_27329549971_20260906-0928.zip': (39, '2026-07-01', '2026-07-31'),
}


@pytest.mark.parametrize('filename, expected', FILES.items())
def test_arca_zip_period_and_rows(filename, expected):
    path = Path.home() / 'Downloads' / filename
    if not path.exists():
        pytest.skip('Exportación ARCA local no disponible')
    result = parse_zip(str(path))
    assert (sum(len(source['filas']) for source in result['csvs']), result['fecha_min'], result['fecha_max']) == expected


def test_banco_chubut_is_liquidacion_a():
    path = Path.home() / 'Downloads' / 'comprobantes_consulta_csv_recibidos_209469533_27329549971_20260906-0928.zip'
    if not path.exists():
        pytest.skip('Exportación ARCA local no disponible')
    rows = parse_zip(str(path))['csvs'][0]['filas']
    chubut = next(row for row in rows if row['proveedor'] == 'BANCO DEL CHUBUT S.A.')
    assert chubut['tipo_comprobante_codigo'] == 63
    assert chubut['tipo_comprobante'] == 'Liquidación A'
    assert chubut['iva_21_centavos'] == 415952
    assert chubut['iva_105_centavos'] == 1174849
