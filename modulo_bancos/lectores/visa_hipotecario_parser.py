"""Parser puro del resumen Visa emitido por Banco Hipotecario.

No escribe en base de datos ni mueve archivos. Los importes contables se
devuelven como enteros en centavos para que la capa de persistencia pueda
conciliar el documento sin errores de punto flotante.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import re
import unicodedata


MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}
MONEY_RE = re.compile(r"\d+(?:\.\d{3})*,\d{2}-?")
LINE_RE = re.compile(
    r"^\s*(\d{2}\.\d{2}\.\d{2})\s+(?:(\d{6}[*K]?)\s+)?(.+?)\s*$"
)


def _ascii(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _date_iso(value: str) -> str:
    match = re.fullmatch(r"\s*(\d{1,2})[ .]+([A-Za-zÁÉÍÓÚáéíóú]{3,})[ .]+(\d{2})\s*", value)
    if not match:
        raise ValueError(f"Fecha de resumen inválida: {value!r}")
    day, month_name, year = match.groups()
    month = MONTHS.get(_ascii(month_name).lower()[:3])
    if not month:
        raise ValueError(f"Mes de resumen desconocido: {month_name!r}")
    return datetime(2000 + int(year), month, int(day)).strftime("%Y-%m-%d")


def _purchase_date_iso(value: str) -> str:
    return datetime.strptime(value, "%d.%m.%y").strftime("%Y-%m-%d")


def _money_cents(value: str) -> int:
    raw = value.strip()
    sign = -1 if raw.endswith("-") else 1
    raw = raw.rstrip("-").replace(".", "").replace(",", ".")
    return sign * int((Decimal(raw) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _percent_milli(value: str | None) -> int | None:
    if not value:
        return None
    return int((Decimal(value.replace(",", ".")) * 1000).quantize(Decimal("1")))


def _clean_description(rest: str, *, is_usd: bool, cuota: str | None) -> str:
    value = rest
    if is_usd:
        # Hipotecario concatena a veces la moneda al identificador del comercio
        # (por ejemplo: ``672896015USD``), por lo que los límites de palabra no
        # son confiables para localizarla.
        value = re.split(r"USD", value, maxsplit=1, flags=re.IGNORECASE)[0]
    else:
        matches = list(MONEY_RE.finditer(value))
        if matches:
            value = value[:matches[-1].start()]
    if cuota:
        value = re.sub(r"\s*Cuota\s+\d{1,2}/\d{1,2}\s*", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\([^)]*\)", " ", value)
    value = MONEY_RE.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip(" $-_")
    value = re.sub(r"\s+P\s*$", "", value).strip()
    return value


def _parse_header(text: str) -> dict:
    close_match = re.search(
        r"CIERRE\s+ACTUAL:\s*(\d{1,2}\s+[A-Za-zÁÉÍÓÚáéíóú]{3,}\s+\d{2})",
        text,
        re.IGNORECASE,
    )
    header_match = re.search(
        r"VENCIMIENTO\s+SALDO\s+\$\s+SALDO\s+U\$S\s+PAGO\s+MIN\.\$\s+PAGO\s+MIN\.U\$S\s*\n"
        r"\s*(\d{1,2}\s+[A-Za-zÁÉÍÓÚáéíóú]{3,}\s+\d{2})\s+"
        r"([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})",
        text,
        re.IGNORECASE,
    )
    if not close_match or not header_match:
        raise ValueError("No se pudo leer la cabecera de cierre/vencimiento Visa Hipotecario")

    previous_match = re.search(
        r"(\d{1,2}\s+[A-Za-zÁÉÍÓÚáéíóú]{3,}\s+\d{2})\s+"
        r"([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+"
        r"(\d{1,2}\s+[A-Za-zÁÉÍÓÚáéíóú]{3,}\s+\d{2})\s*\n\s*"
        r"(\d{1,2}\s+[A-Za-zÁÉÍÓÚáéíóú]{3,}\s+\d{2})\s+"
        r"([\d.]+,\d{2})\s+"
        r"(\d{1,2}\s+[A-Za-zÁÉÍÓÚáéíóú]{3,}\s+\d{2})",
        text,
    )
    saldo_anterior_match = re.search(
        r"SALDO\s+ANTERIOR\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})",
        text,
        re.IGNORECASE,
    )
    summary_number = re.search(r"\b(\d{7}\s*-\s*\d{2}\s*-\s*\d\s*-\s*CR\d+)\b", text)
    debit_account = re.search(r"DEBITAREMOS\s+DE\s+SU\s+C\.A\.(\d+)", text, re.IGNORECASE)
    account_number = re.search(r"\b(0\d{9})\b", text)

    rates = re.search(
        r"TNA\s+([\d,]+)%?,?\s*TEM\s+([\d,]+)%?,?\s*TEA\s+([\d,]+)%?,?\s*"
        r"CFTEA\s*\(con IVA\)\s*([\d,]+)%",
        text,
        re.IGNORECASE,
    )

    header = {
        "fecha_cierre": _date_iso(close_match.group(1)),
        "fecha_vencimiento": _date_iso(header_match.group(1)),
        "saldo_actual_ars_centavos": _money_cents(header_match.group(2)),
        "saldo_actual_usd_centavos": _money_cents(header_match.group(3)),
        "pago_minimo_ars_centavos": _money_cents(header_match.group(4)),
        "numero_resumen": re.sub(r"\s+", "", summary_number.group(1)) if summary_number else None,
        "numero_cuenta": account_number.group(1) if account_number else None,
        "cuenta_debito": debit_account.group(1) if debit_account else None,
        "saldo_anterior_ars_centavos": _money_cents(saldo_anterior_match.group(1)) if saldo_anterior_match else 0,
        "saldo_anterior_usd_centavos": _money_cents(saldo_anterior_match.group(2)) if saldo_anterior_match else 0,
        "tna_ars_milesimas": _percent_milli(rates.group(1)) if rates else None,
        "tem_ars_milesimas": _percent_milli(rates.group(2)) if rates else None,
        "tea_ars_milesimas": _percent_milli(rates.group(3)) if rates else None,
        "cftea_ars_iva_milesimas": _percent_milli(rates.group(4)) if rates else None,
    }
    if previous_match:
        header.update({
            "fecha_vencimiento_anterior": _date_iso(previous_match.group(1)),
            "fecha_proximo_cierre": _date_iso(previous_match.group(4)),
            "fecha_cierre_anterior": _date_iso(previous_match.group(5)),
            "pago_minimo_anterior_ars_centavos": _money_cents(previous_match.group(6)),
            "fecha_proximo_vencimiento": _date_iso(previous_match.group(7)),
        })
    return header


def _operation_kind(description: str, amount: int) -> str:
    normalized = _ascii(description).upper()
    if normalized.startswith("SU PAGO"):
        return "PAGO"
    if normalized.startswith("TRANSFERENCIA DEUDA"):
        return "TRANSFERENCIA_DEUDA"
    if "INTERESES FINANCIACION" in normalized:
        return "INTERES"
    if any(token in normalized for token in ("IMPUESTO", "IVA", "DB.RG", "PERCEPC")):
        return "IMPUESTO"
    return "CREDITO_CONSUMO" if amount < 0 else "CONSUMO"


def _parse_operations(text: str, usd_rate: Decimal) -> list[dict]:
    operations = []
    in_detail = False
    for source_line, raw_line in enumerate(text.splitlines(), start=1):
        if "DETALLE DE TRANSACCION" in raw_line:
            in_detail = True
            continue
        if in_detail and "SALDO ACTUAL" in raw_line:
            break
        if not in_detail:
            continue
        match = LINE_RE.match(raw_line)
        if not match:
            continue
        date_raw, comprobante, rest = match.groups()
        money = MONEY_RE.findall(rest)
        if not money:
            continue

        normalized_rest = _ascii(rest).upper()
        is_transfer = normalized_rest.startswith("TRANSFERENCIA DEUDA")
        is_usd = "USD" in normalized_rest
        cuota_match = re.search(r"Cuota\s+(\d{1,2}/\d{1,2})", rest, re.IGNORECASE)
        cuota = cuota_match.group(1) if cuota_match else None

        ars_cents = 0
        usd_cents = 0
        if is_transfer:
            if len(money) < 2:
                raise ValueError(f"Transferencia de deuda incompleta en línea {source_line}")
            ars_cents = _money_cents(money[-2])
            usd_cents = _money_cents(money[-1])
            description = "TRANSFERENCIA DEUDA"
        elif is_usd:
            usd_cents = _money_cents(money[-1])
            description = _clean_description(rest, is_usd=True, cuota=cuota)
        else:
            ars_cents = _money_cents(money[-1])
            description = _clean_description(rest, is_usd=False, cuota=cuota)

        reference_amount = usd_cents if is_usd else ars_cents
        kind = _operation_kind(description, reference_amount)
        valued_ars = ars_cents
        if is_usd:
            valued_ars = int(
                (Decimal(usd_cents) * usd_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        is_mixed = is_transfer and ars_cents != 0 and usd_cents != 0
        operations.append({
            "orden": len(operations) + 1,
            "linea_origen": source_line,
            "fecha_compra": _purchase_date_iso(date_raw),
            "comprobante": comprobante,
            "descripcion": description,
            "cuota": cuota,
            "tipo_movimiento": kind,
            "moneda_original": "MIXTA" if is_mixed else ("USD" if is_usd else "ARS"),
            "monto_original_centavos": 0 if is_mixed else (usd_cents if is_usd else ars_cents),
            "monto_ars_centavos": ars_cents,
            "monto_usd_centavos": usd_cents,
            "monto_ars_valorizado_centavos": valued_ars,
            "tipo_cambio_milesimas": int(usd_rate * 1000) if is_usd else 1000,
        })
    return operations


def parse_visa_hipotecario_text(text: str, usd_rate: Decimal = Decimal("1400")) -> dict:
    """Convierte el texto del PDF en un resumen conciliado y operaciones firmadas."""
    header = _parse_header(text)
    operations = _parse_operations(text, usd_rate)
    if not operations:
        raise ValueError("El resumen no contiene operaciones reconocibles")

    subtotals = re.findall(
        r"Tarjeta\s+(\d+)\s+Total\s+Consumos.*?([\d.]+,\d{2})\s+([\d.]+,\d{2})",
        text,
        re.IGNORECASE,
    )
    consumos_declarados_ars = sum(_money_cents(item[1]) for item in subtotals)
    consumos_declarados_usd = sum(_money_cents(item[2]) for item in subtotals)

    # La transferencia de deuda trae simultáneamente una pata ARS positiva y
    # una pata USD negativa. Conciliar por ``moneda_original`` perdería una de
    # ellas; por eso cada operación conserva ambos importes contables.
    movement_ars = sum(item["monto_ars_centavos"] for item in operations)
    movement_usd = sum(item["monto_usd_centavos"] for item in operations)
    calculated_ars = header["saldo_anterior_ars_centavos"] + movement_ars
    calculated_usd = header["saldo_anterior_usd_centavos"] + movement_usd
    diff_ars = header["saldo_actual_ars_centavos"] - calculated_ars
    diff_usd = header["saldo_actual_usd_centavos"] - calculated_usd

    expense_operations = [
        item for item in operations
        if item["tipo_movimiento"] not in {"PAGO", "TRANSFERENCIA_DEUDA"}
    ]
    expense_ars = sum(
        item["monto_ars_centavos"] for item in expense_operations
    )
    expense_usd = sum(
        item["monto_usd_centavos"] for item in expense_operations
    )
    interest_ars = sum(
        item["monto_ars_centavos"] for item in expense_operations
        if item["tipo_movimiento"] == "INTERES"
    )
    taxes_ars = sum(
        item["monto_ars_centavos"] for item in expense_operations
        if item["tipo_movimiento"] == "IMPUESTO"
    )
    payments_ars = sum(
        item["monto_ars_centavos"] for item in operations
        if item["tipo_movimiento"] == "PAGO"
    )
    debt_transfer_ars = sum(
        item["monto_ars_centavos"] for item in operations
        if item["tipo_movimiento"] == "TRANSFERENCIA_DEUDA"
    )
    debt_transfer_usd = sum(
        item["monto_usd_centavos"] for item in operations
        if item["tipo_movimiento"] == "TRANSFERENCIA_DEUDA"
    )

    close_period = header["fecha_cierre"][:7]
    document_key = "|".join((
        "VISA_HIPOTECARIO",
        header.get("numero_cuenta") or "SIN_CUENTA",
        header.get("numero_resumen") or "SIN_NUMERO",
        header["fecha_cierre"],
    ))
    summary = {
        **header,
        "fuente": "Visa Hipotecario",
        "titular_codigo": "JOA",
        "periodo": close_period,
        "documento_clave": document_key,
        "hash_contenido_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "consumos_declarados_ars_centavos": consumos_declarados_ars,
        "consumos_declarados_usd_centavos": consumos_declarados_usd,
        "nuevos_cargos_ars_centavos": expense_ars,
        "nuevos_cargos_usd_centavos": expense_usd,
        "intereses_ars_centavos": interest_ars,
        "impuestos_ars_centavos": taxes_ars,
        "pagos_ars_centavos": payments_ars,
        "transferencia_deuda_ars_centavos": debt_transfer_ars,
        "transferencia_deuda_usd_centavos": debt_transfer_usd,
        "diferencia_ars_centavos": diff_ars,
        "diferencia_usd_centavos": diff_usd,
        "conciliado": diff_ars == 0 and diff_usd == 0,
        "cantidad_operaciones": len(operations),
        "cantidad_consumos": len(expense_operations),
    }
    return {"resumen": summary, "operaciones": operations, "consumos": expense_operations}
