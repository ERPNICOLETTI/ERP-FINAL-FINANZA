import unittest
from pathlib import Path

from modulo_compras.calim_facturas_parser import _cents, parse


class CalimFacturasParserTest(unittest.TestCase):
    def test_numeric_cells_are_already_cents(self):
        self.assertEqual(_cents(30400), 30400)
        self.assertEqual(_cents(6384), 6384)
        self.assertEqual(_cents(36784), 36784)

    def test_formatted_text_is_converted_from_pesos(self):
        self.assertEqual(_cents('304,00'), 30400)
        self.assertEqual(_cents('1.234,56'), 123456)

    def test_august_payway_invoice_is_not_multiplied_by_one_hundred(self):
        source = Path.home() / 'Downloads' / 'Facturas de Compra (6).xlsx'
        if not source.exists():
            self.skipTest('El XLSX CALIM de agosto no está disponible')
        rows = parse(str(source))['filas']
        payway = next(row for row in rows if row['cuit_proveedor'] == '30717664406')
        self.assertEqual(payway['neto_centavos'], 30400)
        self.assertEqual(payway['iva_total_centavos'], 6384)
        self.assertEqual(payway['total_centavos'], 36784)


if __name__ == '__main__':
    unittest.main()
