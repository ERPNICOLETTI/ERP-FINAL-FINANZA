from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path, PurePosixPath

PARSER_VERSION = "arca-recibidos/1.0.0"
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
TIPOS = {
    1: "Factura A", 2: "Nota de Débito A", 3: "Nota de Crédito A",
    6: "Factura B", 7: "Nota de Débito B", 8: "Nota de Crédito B",
    11: "Factura C", 12: "Nota de Débito C", 13: "Nota de Crédito C",
    51: "Factura M", 52: "Nota de Débito M", 53: "Nota de Crédito M",
    63: "Liquidación A", 64: "Liquidación B", 81: "Tique Factura A",
    201: "Factura de Crédito MiPyME A", 203: "Nota de Crédito MiPyME A",
    206: "Factura de Crédito MiPyME B", 208: "Nota de Crédito MiPyME B",
    211: "Factura de Crédito MiPyME C", 213: "Nota de Crédito MiPyME C",
}
CREDIT_NOTES = {3, 8, 13, 53, 203, 208, 213}


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")


def _cents(value: str | None) -> int:
    raw = (value or "").strip().replace("$", "")
    if not raw:
        return 0
    raw = raw.replace(".", "").replace(",", ".")
    try:
        return int((Decimal(raw) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ValueError(f"Importe ARCA invalido: {value!r}") from exc


def _date(value: str) -> str:
    value = value.strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Fecha ARCA invalida: {value!r}")


def _parse_csv(content: bytes, member_name: str) -> dict:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin1")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise ValueError(f"CSV ARCA sin encabezado: {member_name}")
    rows = []
    for line_no, source in enumerate(reader, start=2):
        row = {_key(k): (v or "").strip() for k, v in source.items() if k is not None}
        required = ("fecha_de_emision", "tipo_de_comprobante", "punto_de_venta", "numero_desde", "nro_doc_emisor")
        if not all(row.get(k) for k in required):
            raise ValueError(f"Fila {line_no} incompleta en {member_name}")
        type_code = int(row["tipo_de_comprobante"])
        sign = -1 if type_code in CREDIT_NOTES else 1
        amounts = {
            "neto_gravado_centavos": _cents(row.get("imp_neto_gravado_total")),
            "neto_iva_0_centavos": _cents(row.get("imp_neto_gravado_iva_0")),
            "iva_25_centavos": _cents(row.get("iva_2_5")),
            "neto_iva_25_centavos": _cents(row.get("imp_neto_gravado_iva_2_5")),
            "iva_5_centavos": _cents(row.get("iva_5")),
            "neto_iva_5_centavos": _cents(row.get("imp_neto_gravado_iva_5")),
            "iva_105_centavos": _cents(row.get("iva_10_5")),
            "neto_iva_105_centavos": _cents(row.get("imp_neto_gravado_iva_10_5")),
            "iva_21_centavos": _cents(row.get("iva_21")),
            "neto_iva_21_centavos": _cents(row.get("imp_neto_gravado_iva_21")),
            "iva_27_centavos": _cents(row.get("iva_27")),
            "neto_iva_27_centavos": _cents(row.get("imp_neto_gravado_iva_27")),
            "no_gravado_centavos": _cents(row.get("imp_neto_no_gravado")),
            "exento_centavos": _cents(row.get("imp_op_exentas")),
            "otros_tributos_centavos": _cents(row.get("otros_tributos")),
            "total_iva_centavos": _cents(row.get("total_iva")),
            "total_centavos": _cents(row.get("imp_total")),
        }
        rows.append({
            "numero_linea": line_no, "fecha": _date(row["fecha_de_emision"]),
            "tipo_comprobante_codigo": type_code, "tipo_comprobante": TIPOS.get(type_code, f"Tipo {type_code}"),
            "signo": sign, "punto_venta": row["punto_de_venta"].zfill(5),
            "numero_comprobante": row["numero_desde"].zfill(8), "numero_hasta": row.get("numero_hasta", "").zfill(8),
            "cae": row.get("cod_autorizacion", ""), "tipo_doc_emisor": row.get("tipo_doc_emisor", ""),
            "cuit_proveedor": row["nro_doc_emisor"], "proveedor": row.get("denominacion_emisor", ""),
            "tipo_doc_receptor": row.get("tipo_doc_receptor", ""), "documento_receptor": row.get("nro_doc_receptor", ""),
            "moneda": row.get("moneda", "$") or "$", "tipo_cambio": row.get("tipo_cambio", "1,00"),
            **amounts, "row_raw": source,
        })
    if not rows:
        raise ValueError(f"CSV ARCA sin comprobantes: {member_name}")
    return {"nombre": member_name, "hash_sha256": _sha256_bytes(content), "contenido_raw": text, "filas": rows}


def parse_zip(path: str) -> dict:
    zip_path = Path(path).resolve()
    zip_bytes = zip_path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        infos = archive.infolist()
        if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("ZIP ARCA excede el limite descomprimido")
        csv_files = []
        manifest = []
        for info in infos:
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise ValueError("ZIP ARCA contiene una ruta insegura")
            manifest.append({"nombre": info.filename, "bytes": info.file_size, "crc": info.CRC})
            if info.filename.lower().endswith(".csv") and not info.is_dir():
                csv_files.append(_parse_csv(archive.read(info), info.filename))
    if not csv_files:
        raise ValueError("ZIP ARCA sin archivos CSV")
    all_rows = [row for source in csv_files for row in source["filas"]]
    return {
        "path_archivo": zip_path.as_posix(), "nombre_archivo": zip_path.name,
        "hash_sha256": _sha256_bytes(zip_bytes), "parser_version": PARSER_VERSION,
        "manifest_raw": json.dumps(manifest, ensure_ascii=False), "csvs": csv_files,
        "fecha_min": min(row["fecha"] for row in all_rows), "fecha_max": max(row["fecha"] for row in all_rows),
        "formato_fuente": "ZIP",
    }


def parse_csv(path: str) -> dict:
    csv_path = Path(path).resolve()
    content = csv_path.read_bytes()
    parsed = _parse_csv(content, csv_path.name)
    dates = [row['fecha'] for row in parsed['filas']]
    return {
        'path_archivo': csv_path.as_posix(), 'nombre_archivo': csv_path.name,
        'hash_sha256': parsed['hash_sha256'], 'parser_version': PARSER_VERSION,
        'manifest_raw': json.dumps([{'nombre': csv_path.name, 'bytes': len(content)}], ensure_ascii=False),
        'csvs': [parsed], 'fecha_min': min(dates), 'fecha_max': max(dates), 'formato_fuente': 'CSV',
    }
