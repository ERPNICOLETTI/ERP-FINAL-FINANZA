import unittest
from pathlib import Path

import PyPDF2

from modulo_bancos.lectores.visa_galicia_parser import parse_visa_galicia_text


class VisaGaliciaParserTest(unittest.TestCase):
    def test_august_2026_reconciles_and_separates_holders(self):
        source = Path.home() / 'Downloads' / 'cee97732-f6f8-4e9e-af4f-3258a3190c93.pdf'
        if not source.exists():
            self.skipTest('El resumen Visa Galicia no está disponible')
        with source.open('rb') as stream:
            text = '\n'.join(page.extract_text() or '' for page in PyPDF2.PdfReader(stream).pages)
        data = parse_visa_galicia_text(text)
        summary = data['resumen']
        self.assertTrue(summary['conciliado'])
        self.assertFalse(summary['clasificar_automaticamente'])
        self.assertFalse(summary['iva_computable_segun_leyenda'])
        self.assertEqual(summary['diferencia_ars_centavos'], 0)
        self.assertEqual(summary['saldo_actual_ars_centavos'], 1097234888)
        self.assertEqual(summary['intereses_ars_centavos'], 57387431)
        self.assertEqual(summary['impuestos_ars_centavos'], 15330842)
        by_holder = {
            holder: sum(row['monto_ars_centavos'] for row in data['consumos'] if row['titular_codigo'] == holder)
            for holder in ('JOA', 'JOR')
        }
        self.assertEqual(by_holder['JOA'], 19397755)
        self.assertEqual(by_holder['JOR'], 136129084)


if __name__ == '__main__':
    unittest.main()
