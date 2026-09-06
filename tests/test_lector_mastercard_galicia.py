import unittest
from pathlib import Path

import PyPDF2

from modulo_bancos.lectores.lector_mastercard_galicia import parse_mastercard_galicia_text


PDF = Path(r"C:\Users\essao\Downloads\877a2308-91f2-4a2f-802a-282f3294db6d.pdf")


class MastercardGaliciaParserTest(unittest.TestCase):
    @unittest.skipUnless(PDF.exists(), "El resumen Mastercard de referencia no está disponible")
    def test_resumen_agosto_concilia_y_conserva_el_documento(self):
        with PDF.open("rb") as source:
            text = "\n".join(page.extract_text() or "" for page in PyPDF2.PdfReader(source).pages)
        data = parse_mastercard_galicia_text(text)
        summary = data["resumen"]

        self.assertTrue(summary["conciliado"])
        self.assertFalse(summary["clasificar_automaticamente"])
        self.assertEqual(summary["diferencia_ars_centavos"], 0)
        self.assertEqual(summary["diferencia_usd_centavos"], 0)
        self.assertEqual(summary["saldo_actual_ars_centavos"], 720407318)
        self.assertEqual(summary["saldo_actual_usd_centavos"], 3868)
        self.assertEqual(summary["pago_minimo_ars_centavos"], 79932000)
        self.assertEqual(summary["intereses_ars_centavos"], 32964405)
        self.assertEqual(summary["condicion_iva_impresa"], "CONSUMIDOR FINAL")
        self.assertFalse(summary["iva_computable_segun_leyenda"])
        self.assertEqual(len(data["operaciones"]), 26)
        self.assertEqual(len(data["consumos"]), 23)
        self.assertEqual(data["subtotales_documentales"], {
            "JOR_ARS": 93826845, "JOR_USD": 299,
            "JOA_ARS": 21696071, "JOA_USD": 3523,
        })
        offer = data["financiacion_ofrecida"]
        self.assertEqual(offer["capital_ofrecido_centavos"], 726325358)
        self.assertEqual(offer["vigente_hasta"], "2026-10-01")
        self.assertEqual(offer["opciones"][-1]["cuotas"], 24)
        self.assertEqual(offer["opciones"][-1]["cuota_centavos"], 59509269)


if __name__ == "__main__":
    unittest.main()
