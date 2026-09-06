import unittest
from pathlib import Path

from modulo_tarjetas.lectores.patagonia365_resumen_parser import parse


class Patagonia365ResumenParserTest(unittest.TestCase):
    def test_august_2026_summary_reconciles(self):
        source = Path.home() / 'Downloads' / 'LiqMensual202608.pdf'
        if not source.exists():
            self.skipTest('El resumen Patagonia 365 no está disponible')
        data = parse(str(source))
        self.assertEqual(data['numero_resumen'], '00330064')
        self.assertEqual(len(data['liquidaciones']), 8)
        self.assertEqual(data['bruto_centavos'], 114253000)
        self.assertEqual(data['arancel_centavos'], 3427590)
        self.assertEqual(data['financiero_centavos'], 7581340)
        self.assertEqual(data['iva_ri_centavos'], 1515835)
        self.assertEqual(data['neto_centavos'], 101728235)


if __name__ == '__main__':
    unittest.main()
