from __future__ import annotations

import re
from datetime import datetime

import pdfplumber

from .payway_common import cents, sha256_file, slash_path

PARSER_VERSION = "payway-resumen/1.0.0"
MONEY = r"-?[\d.]+,\d{2}"


def _first(pattern: str, text: str, field: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if not match:
        raise ValueError(f"Resumen Payway sin {field}")
    return match.group(1).strip()


def _header_totals(first_page: str) -> tuple[int, int, int]:
    lines = first_page.splitlines()

    def after(label: str) -> int:
        start = next((i for i, line in enumerate(lines) if label in line.upper()), None)
        if start is None:
            raise ValueError(f"Resumen Payway sin {label.lower()}")
        for line in lines[start + 1:start + 8]:
            values = re.findall(MONEY, line)
            if len(values) >= 2:
                return cents(values[-2])
        raise ValueError(f"Resumen Payway sin importe para {label.lower()}")

    return after("TOTAL PRESENTADO"), after("TOTAL DESCUENTO"), after("SALDO $")


def _daily_rows(text: str, year: int) -> list[dict]:
    rows = []
    pattern = re.compile(
        r"FECHA DE PAGO\s+(\d{2}/\d{2})(.*?)(?:Total del d[^\n]*?\$\s*(" + MONEY + r")\s*\$\s*(" + MONEY + r")\s*\$\s*(" + MONEY + r"))",
        re.IGNORECASE | re.DOTALL,
    )
    for line_no, match in enumerate(pattern.finditer(text), start=1):
        block = match.group(2)
        liquidaciones = re.findall(r"Liq\.\s*N.\s*(\d+)\s*-\s*Lote\s*N.\s*(\d+)", block, re.IGNORECASE)
        rows.append({
            "numero_linea": line_no,
            "fecha_pago": datetime.strptime(f"{match.group(1)}/{year}", "%d/%m/%Y").date().isoformat(),
            "bruto_centavos": cents(match.group(3)),
            "descuentos_centavos": cents(match.group(4)),
            "neto_centavos": cents(match.group(5)),
            "liquidaciones": [{"numero": number, "lote": lot} for number, lot in liquidaciones],
        })
    if not rows:
        raise ValueError("Resumen Payway sin detalle diario")
    return rows


def _concepts(text: str) -> list[dict]:
    section = text.split("DESGLOSE DE DESCUENTOS", 1)[-1]
    section = section.split("SR. COMERCIANTE", 1)[0]
    concepts: list[dict] = []

    def add(category: str, description: str, amount: str) -> None:
        concepts.append({"categoria": category, "descripcion": " ".join(description.split()), "importe_centavos": cents(amount)})

    for match in re.finditer(r"^(Arancel Tj\.[^\n$]+)\$\s*(" + MONEY + r")", section, re.IGNORECASE | re.MULTILINE):
        add("ARANCEL", match.group(1), match.group(2))
    for match in re.finditer(r"^(\d+\s+Ventas? en \d+ d.as?)\s*\$\s*(" + MONEY + r")", section, re.IGNORECASE | re.MULTILINE):
        add("FINANCIACION_ADELANTO", match.group(1), match.group(2))
    for match in re.finditer(r"^(\d+\s+Ventas? en \d+ cuotas)\s*\$\s*(" + MONEY + r")", section, re.IGNORECASE | re.MULTILINE):
        add("PLAN_CUOTAS", match.group(1), match.group(2))
    singles = [
        ("SERVICIO_PAYWAY_ADELANTO", r"^Servicio Cobro Anticipado\s*\$\s*(" + MONEY + r")", "Servicio Payway - cobro anticipado"),
        ("SERVICIO_MENSUAL", r"^Cargo por Servicio[^\n$]*\$\s*(" + MONEY + r")", "Cargo mensual Payway"),
        ("BONIFICACION_SERVICIO", r"^Bonif\. Cargo Serv\.[^\n$]*\$\s*(" + MONEY + r")", "Bonificacion cargo mensual"),
        ("IVA_21", r"^IVA 21,00 %\s*\$\s*(" + MONEY + r")", "IVA 21%"),
        ("RETENCION_AFIP", r"^Percep\./Retenc\.AFIP[^\n$]*\$\s*(" + MONEY + r")", "Percepcion/retencion AFIP-DGI"),
    ]
    for category, pattern, description in singles:
        for match in re.finditer(pattern, section, re.IGNORECASE | re.MULTILINE):
            add(category, description, match.group(1))
    return concepts


def parse(path: str) -> dict:
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    if not pages or "RESUMEN MENSUAL DE LIQUIDACIONES" not in pages[0].upper():
        raise ValueError("El PDF no es un resumen mensual Payway")
    text = "\n".join(pages)
    emission_raw = _first(r"FECHA DE EMISION:\s*(\d{2}/\d{2}/\d{4})", text, "fecha de emision")
    emission = datetime.strptime(emission_raw, "%d/%m/%Y").date()
    establishment = _first(r"DE ESTABLECIMIENTO:\s*(\d+)", text, "establecimiento")
    payer = _first(r"PAGADOR:\s*([^\n]+)", text, "pagador")
    summary_number = _first(r"DE RESUMEN:\s*(\d+)", text, "numero de resumen")
    gross, discounts, net = _header_totals(pages[0])
    daily = _daily_rows(text, emission.year)
    if sum(row["bruto_centavos"] for row in daily) != gross:
        raise ValueError("El bruto diario no reconcilia con la cabecera Payway")
    if sum(row["descuentos_centavos"] for row in daily) != discounts:
        raise ValueError("Los descuentos diarios no reconcilian con la cabecera Payway")
    if sum(row["neto_centavos"] for row in daily) != net or gross - discounts != net:
        raise ValueError("El neto diario no reconcilia con la cabecera Payway")
    concepts = _concepts(text)
    if sum(item["importe_centavos"] for item in concepts) != discounts:
        raise ValueError("El desglose de conceptos no reconcilia con los descuentos Payway")
    return {
        "hash_sha256": sha256_file(path), "path_archivo": slash_path(path), "contenido_raw": text,
        "parser_version": PARSER_VERSION, "fecha_emision": emission.isoformat(), "periodo": emission.strftime("%Y-%m"),
        "numero_resumen": summary_number, "pagador_codigo": payer.split()[0], "pagador_nombre": " ".join(payer.split()[1:]),
        "establecimiento": establishment, "marca": "VISA" if establishment.endswith("1707") else "MASTERCARD" if establishment.endswith("1756") else "DESCONOCIDA",
        "bruto_centavos": gross, "descuentos_centavos": discounts, "neto_centavos": net,
        "dias": daily, "conceptos": concepts,
    }
