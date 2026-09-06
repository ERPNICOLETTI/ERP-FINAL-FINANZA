import sqlite3
from pathlib import Path

import pytest

from modulo_tarjetas import storage_tarjetas
from modulo_tarjetas.lectores.payway_movimientos_parser import parse as parse_movimientos
from modulo_tarjetas.lectores.payway_resumen_parser import parse as parse_resumen


PDF_CASES = {
    "comprobante-MEN-COM00292717569020002026-08-31.pdf": ("000007618829", "MASTERCARD", "902", 23550000, 549347, 23000653),
    "comprobante-MEN-COM00292717070830302026-08-31.pdf": ("000000531430", "VISA", "083", 154280000, 23815564, 130464436),
    "comprobante-MEN-COM00292717079020002026-08-31.pdf": ("000007618828", "VISA", "902", 46630000, 1379627, 45250373),
    "comprobante-MEN-COM00292717560830302026-08-31.pdf": ("000000531431", "MASTERCARD", "083", 42920000, 1896715, 41023285),
}


@pytest.mark.parametrize("filename, expected", PDF_CASES.items())
def test_august_resumen_reconciles(filename, expected):
    path = Path.home() / "Downloads" / filename
    if not path.exists():
        pytest.skip("Documento Payway local no disponible")
    result = parse_resumen(str(path))
    assert (result["numero_resumen"], result["marca"], result["pagador_codigo"],
            result["bruto_centavos"], result["descuentos_centavos"], result["neto_centavos"]) == expected
    assert sum(x["importe_centavos"] for x in result["conceptos"]) == result["descuentos_centavos"]


def test_movimientos_uses_exact_cents(tmp_path):
    source = tmp_path / "movimientos.csv"
    source.write_text(
        "Detalle Payway Desde: 01/08/2026 Hasta: 31/08/2026\n"
        "COMPRA,PRESENTACION,TIPO,LOTE,NUM.CUPON,MARCA,ESTABLECIMIENTO,PAGO,MONTO_BRUTO,DETALLE,NUM.TARJETA,CANT.CUOTAS,MODALIDAD,NRO_AUT,OP_ASOCIADA\n"
        "01/08/2026,02/08/2026,Venta,1,0001,VISA,29271707,03/08/2026,1234.56,Consumo,************1234,3,PRESENCIAL,999,\n",
        encoding="latin1",
    )
    result = parse_movimientos(str(source))
    assert result["movimientos"][0]["bruto_centavos"] == 123456


def test_resumen_storage_is_semantically_idempotent(tmp_path, monkeypatch):
    db = tmp_path / "erp.db"
    monkeypatch.setattr(storage_tarjetas, "DB_PATH", str(db))
    conn = sqlite3.connect(db)
    conn.executescript('''
      CREATE TABLE core_staging_raw (id INTEGER PRIMARY KEY, nombre_archivo TEXT NOT NULL, hash_sha256 TEXT UNIQUE NOT NULL,
      modulo TEXT NOT NULL, tipo_fuente TEXT NOT NULL, formato_raw TEXT NOT NULL, parser_version TEXT NOT NULL,
      contenido_raw TEXT NOT NULL, filas_leidas INTEGER DEFAULT 0, fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      fecha_procesado TIMESTAMP, estado TEXT DEFAULT 'PENDIENTE', mensaje_error TEXT);
      CREATE TABLE core_staging_logs (id INTEGER PRIMARY KEY, staging_id INTEGER, fecha_intento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      resultado TEXT NOT NULL, detalles TEXT);
    ''')
    conn.close()
    storage_tarjetas.init_db_tarjetas()
    base = {"hash_sha256": "a" * 64, "path_archivo": "C:/inbox/a.pdf", "contenido_raw": "raw", "parser_version": "test",
            "fecha_emision": "2026-08-31", "periodo": "2026-08", "numero_resumen": "1", "pagador_codigo": "902",
            "pagador_nombre": "PAYWAY", "establecimiento": "0029271707", "marca": "VISA", "bruto_centavos": 10000,
            "descuentos_centavos": 1000, "neto_centavos": 9000,
            "dias": [{"numero_linea": 1, "fecha_pago": "2026-08-10", "bruto_centavos": 10000,
                      "descuentos_centavos": 1000, "neto_centavos": 9000, "liquidaciones": []}],
            "conceptos": [{"categoria": "ARANCEL", "descripcion": "Arancel", "importe_centavos": 1000}]}
    first, _ = storage_tarjetas.ingest_payway_resumen(base)
    second, _ = storage_tarjetas.ingest_payway_resumen({**base, "hash_sha256": "b" * 64, "path_archivo": "C:/inbox/b.pdf"})
    assert first == second
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM tarjetas_payway_resumenes").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM core_staging_raw").fetchone()[0] == 2
    conn.close()
