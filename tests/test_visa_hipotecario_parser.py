import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modulo_bancos import storage_bancos
from modulo_bancos.lectores.visa_hipotecario_parser import parse_visa_hipotecario_text
from modulo_gastos import storage_gastos


SYNTHETIC_STATEMENT = """
CIERRE ACTUAL: 20 ago 26
VENCIMIENTO SALDO $ SALDO U$S PAGO MIN.$ PAGO MIN.U$S
01 sep 26 39.511,88 10,12 100,00
SALDO ANTERIOR 1.000,00 24,61
Cuenta 0823907210 Resumen 0195313-05-1-CR0702
TNA 78,510% TEM 6,453% TEA 113,999% CFTEA (con IVA) 149,602%
DETALLE DE TRANSACCION
01.08.26 TRANSFERENCIA DEUDA TC 1.508,00 37.111,88 24,61-
02.08.26 123456 COMPRA LOCAL 1.500,00
03.08.26 123457 COMPRA LOCAL 100,00-
04.08.26 123458K NETFLIX.COM 672896015USD 10,12 10,12
Tarjeta 1234 Total Consumos 1.400,00 10,12
SALDO ACTUAL
"""


class VisaHipotecarioParserTests(unittest.TestCase):
    def test_parses_signed_and_mixed_currency_operations(self):
        parsed = parse_visa_hipotecario_text(SYNTHETIC_STATEMENT)
        summary = parsed["resumen"]

        self.assertTrue(summary["conciliado"])
        self.assertEqual(summary["diferencia_ars_centavos"], 0)
        self.assertEqual(summary["diferencia_usd_centavos"], 0)
        self.assertEqual(summary["nuevos_cargos_ars_centavos"], 140000)
        self.assertEqual(summary["nuevos_cargos_usd_centavos"], 1012)
        self.assertEqual(summary["transferencia_deuda_ars_centavos"], 3711188)
        self.assertEqual(summary["transferencia_deuda_usd_centavos"], -2461)
        self.assertEqual(summary["cantidad_operaciones"], 4)
        self.assertEqual(summary["cantidad_consumos"], 3)

        credit = next(item for item in parsed["consumos"] if item["tipo_movimiento"] == "CREDITO_CONSUMO")
        self.assertEqual(credit["monto_original_centavos"], -10000)
        netflix = next(item for item in parsed["consumos"] if item["moneda_original"] == "USD")
        self.assertEqual(netflix["descripcion"], "NETFLIX.COM 672896015")
        self.assertEqual(netflix["monto_original_centavos"], 1012)

    def test_persistence_preserves_category_and_rejects_business_duplicate(self):
        parsed = parse_visa_hipotecario_text(SYNTHETIC_STATEMENT)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "erp_test.db")
            with patch.object(storage_gastos, "DB_PATH", db_path), patch.object(storage_bancos, "DB_PATH", db_path):
                storage_gastos.init_db_gastos()
                conn = sqlite3.connect(db_path)
                conn.executescript("""
                    CREATE TABLE core_staging_raw (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nombre_archivo TEXT NOT NULL,
                        hash_sha256 TEXT UNIQUE NOT NULL,
                        modulo TEXT NOT NULL,
                        tipo_fuente TEXT NOT NULL,
                        formato_raw TEXT NOT NULL,
                        parser_version TEXT NOT NULL,
                        contenido_raw TEXT NOT NULL,
                        filas_leidas INTEGER DEFAULT 0,
                        fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        fecha_procesado TIMESTAMP,
                        estado TEXT DEFAULT 'PENDIENTE',
                        mensaje_error TEXT
                    );
                    CREATE TABLE core_staging_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        staging_id INTEGER,
                        fecha_intento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resultado TEXT NOT NULL,
                        detalles TEXT
                    );
                """)
                conn.executemany("""
                    INSERT INTO gastos_tipos(cuenta_codigo,nombre,tipo,palabras_clave)
                    VALUES ('JOA',?,'EGRESO',?)
                """, [
                    ("Gastos Personales", "COMPRA"),
                    ("Tarjeta", "IMPUESTO,INTERES"),
                    ("Categoría manual", ""),
                ])
                first_raw = conn.execute("""
                    INSERT INTO core_staging_raw(
                        nombre_archivo,hash_sha256,modulo,tipo_fuente,formato_raw,
                        parser_version,contenido_raw
                    ) VALUES ('resumen.pdf','hash-1','gastos','VISA_HIPOTECARIO','TEXT','test',?)
                """, (SYNTHETIC_STATEMENT,)).lastrowid
                conn.commit()
                conn.close()

                saved, detail = storage_gastos.guardar_resumen_visa_hipotecario(
                    parsed, staging_id=first_raw, parser_version="test"
                )
                self.assertTrue(saved)
                self.assertEqual(detail["agregados"], 3)

                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT * FROM gastos_registros WHERE fuente='Visa Hipotecario' ORDER BY id
                """).fetchall()
                self.assertEqual(len(rows), 3)
                self.assertTrue(any(row["monto_original_centavos"] < 0 for row in rows))
                original_ids = [row["id"] for row in rows]
                manual_type = conn.execute("""
                    SELECT id FROM gastos_tipos WHERE nombre='Categoría manual'
                """).fetchone()[0]
                conn.execute(
                    "UPDATE gastos_registros SET gasto_tipo_id=? WHERE id=?",
                    (manual_type, original_ids[0]),
                )
                second_raw = conn.execute("""
                    INSERT INTO core_staging_raw(
                        nombre_archivo,hash_sha256,modulo,tipo_fuente,formato_raw,
                        parser_version,contenido_raw
                    ) VALUES ('copia.pdf','hash-2','gastos','VISA_HIPOTECARIO','TEXT','test',?)
                """, (SYNTHETIC_STATEMENT,)).lastrowid
                conn.commit()
                conn.close()

                rebuilt, rebuilt_detail = storage_gastos.guardar_resumen_visa_hipotecario(
                    parsed, staging_id=first_raw, parser_version="test-2", reconstruir=True
                )
                self.assertTrue(rebuilt)
                self.assertEqual(rebuilt_detail["actualizados"], 3)

                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                rebuilt_rows = conn.execute("""
                    SELECT id,gasto_tipo_id FROM gastos_registros
                    WHERE fuente='Visa Hipotecario' ORDER BY id
                """).fetchall()
                self.assertEqual([row["id"] for row in rebuilt_rows], original_ids)
                self.assertEqual(rebuilt_rows[0]["gasto_tipo_id"], manual_type)
                conn.close()

                duplicated, duplicate_detail = storage_gastos.guardar_resumen_visa_hipotecario(
                    parsed, staging_id=second_raw, parser_version="test"
                )
                self.assertFalse(duplicated)
                self.assertEqual(duplicate_detail["motivo"], "RESUMEN_EXISTENTE")
                self.assertEqual(duplicate_detail["raw_canonico_id"], first_raw)


if __name__ == "__main__":
    unittest.main()
