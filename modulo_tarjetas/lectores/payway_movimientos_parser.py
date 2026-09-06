from __future__ import annotations

import csv
from datetime import datetime

from .payway_common import cents, sha256_file, slash_path

PARSER_VERSION = "payway-movimientos/1.0.0"
REQUIRED = {"COMPRA", "PRESENTACION", "TIPO", "LOTE", "NUM.CUPON", "MARCA", "ESTABLECIMIENTO", "PAGO", "MONTO_BRUTO"}


def _date(value: str) -> str:
    return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()


def parse(path: str) -> dict:
    with open(path, "r", encoding="latin1", newline="") as source:
        raw = source.read()
    lines = raw.splitlines()
    if len(lines) < 2:
        raise ValueError("CSV Payway vacio")
    reader = csv.DictReader(lines[1:])
    if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
        raise ValueError("CSV sin las columnas requeridas de Movimientos Presentados Payway")
    movements = []
    for line_no, row in enumerate(reader, start=3):
        if not any(row.values()):
            continue
        movements.append({
            "numero_linea": line_no, "fecha_compra": _date(row["COMPRA"]),
            "fecha_presentacion": _date(row["PRESENTACION"]), "fecha_pago": _date(row["PAGO"]),
            "tipo": row["TIPO"].strip(), "lote": row["LOTE"].strip(), "cupon": row["NUM.CUPON"].strip(),
            "marca": row["MARCA"].strip(), "establecimiento": row["ESTABLECIMIENTO"].strip(),
            "bruto_centavos": cents(row["MONTO_BRUTO"]), "detalle": row.get("DETALLE", "").strip(),
            "tarjeta_enmascarada": row.get("NUM.TARJETA", "").strip(), "cuotas": int(row.get("CANT.CUOTAS") or 0),
            "modalidad": row.get("MODALIDAD", "").strip(), "autorizacion": row.get("NRO_AUT", "").strip(),
            "operacion_asociada": row.get("OP_ASOCIADA", "").strip(),
        })
    if not movements:
        raise ValueError("CSV Payway sin movimientos")
    return {"hash_sha256": sha256_file(path), "path_archivo": slash_path(path), "contenido_raw": raw,
            "parser_version": PARSER_VERSION, "descripcion_fuente": lines[0], "movimientos": movements}
