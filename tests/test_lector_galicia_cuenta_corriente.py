import unittest
from pathlib import Path

import PyPDF2

from modulo_bancos.lectores.lector_galicia_cuenta_corriente import (
    parse_galicia_cuenta_corriente_text,
)


PDF = Path(
    r"C:\Users\essao\Downloads\RESUMEN_EXTRACTOS CONSOLIDADOS - CUENTA CORRIENTE 28-08-2026.pdf"
)


class GaliciaCuentaCorrienteParserTest(unittest.TestCase):
    @unittest.skipUnless(PDF.exists(), "El resumen Galicia de referencia no está disponible")
    def test_agosto_concilia_movimientos_saldos_e_impuestos(self):
        with PDF.open("rb") as source:
            text = "\n".join(page.extract_text() or "" for page in PyPDF2.PdfReader(source).pages)
        data = parse_galicia_cuenta_corriente_text(text)
        summary = data["resumen"]

        self.assertTrue(summary["conciliado"])
        self.assertEqual(summary["diferencia_centavos"], 0)
        self.assertEqual(summary["saldo_inicial_centavos"], -490125769)
        self.assertEqual(summary["creditos_centavos"], 726100000)
        self.assertEqual(summary["debitos_centavos"], -588447569)
        self.assertEqual(summary["saldo_final_centavos"], -352473338)
        self.assertEqual(summary["intereses_centavos"], 47552728)
        self.assertEqual(summary["iva_intereses_centavos"], 9986073)
        self.assertEqual(summary["sellos_centavos"], 648446)
        self.assertEqual(summary["impuesto_ley_25413_centavos"], 3509626)
        self.assertEqual(summary["condicion_iva_impresa"], "Consumidor Final")
        self.assertFalse(summary["iva_computable_segun_leyenda"])
        self.assertEqual(len(data["movimientos"]), 33)


if __name__ == "__main__":
    unittest.main()
