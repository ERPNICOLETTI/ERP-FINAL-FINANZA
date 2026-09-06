"""Parser puro y conciliado para resúmenes Visa Banco Galicia."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

MONEY = r"-?[\d.]+,\d{2}"


def _ascii(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(c))


def _cents(value: str) -> int:
    raw = value.strip()
    return int((Decimal(raw.replace(".", "").replace(",", ".")) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _date(value: str) -> str:
    months = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
              "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}
    day, month, year = value.upper().split("-")
    return datetime(2000 + int(year), months[month], int(day)).date().isoformat()


def _kind(description: str, amount: int) -> str:
    text = _ascii(description).upper()
    if "SU PAGO" in text:
        return "PAGO"
    if "INTERESES FINANCIACION" in text:
        return "INTERES"
    if "IVA" in text or "IMPUESTO" in text or "PERCEP" in text:
        return "IMPUESTO"
    return "CREDITO_CONSUMO" if amount < 0 else "CONSUMO"


def parse_visa_galicia_text(text: str) -> dict:
    normalized = _ascii(text)
    number = re.search(r"Resumen N.?\s*(VI\d+)", normalized, re.I)
    account = re.search(r"N.? Cuenta:\s*(\d+)", normalized, re.I)
    dates = re.search(
        r"(\d{2}-[A-Za-z]{3}-\d{2})\s+(\d{2}-[A-Za-z]{3}-\d{2})\s+"
        r"(\d{2}-[A-Za-z]{3}-\d{2})\s+(\d{2}-[A-Za-z]{3}-\d{2})\s+"
        r"(\d{2}-[A-Za-z]{3}-\d{2})\s+(\d{2}-[A-Za-z]{3}-\d{2})",
        normalized,
    )
    if not number or not account or not dates:
        raise ValueError("Cabecera Visa Galicia incompleta")
    date_values = [_date(value) for value in dates.groups()]
    close_date, due_date = date_values[2], date_values[3]

    previous = re.search(rf"SALDO ANTERIOR\s+({MONEY})\s+({MONEY})", normalized, re.I)
    total = re.search(rf"TOTAL A PAGAR\s+({MONEY})\s+({MONEY})", normalized, re.I)
    minimum = re.search(rf"PAGO MINIMO.*?\n.*?\$\s*({MONEY})", normalized, re.I | re.S)
    if not previous or not total or not minimum:
        raise ValueError("Saldos Visa Galicia incompletos")

    operations = []
    payment = re.search(rf"^(\d{{2}}-\d{{2}}-\d{{2}})\s+SU PAGO EN PESOS\s+({MONEY})", normalized, re.I | re.M)
    if payment:
        payment_amount = _cents(payment.group(2))
        operations.append({
            "orden": 1, "linea_origen": normalized[:payment.start()].count("\n") + 1,
            "fecha_compra": datetime.strptime(payment.group(1), "%d-%m-%y").date().isoformat(),
            "comprobante": None, "descripcion": "SU PAGO EN PESOS", "cuota": None,
            "tipo_movimiento": "PAGO", "titular_codigo": "JOR", "moneda_original": "ARS",
            "monto_original_centavos": payment_amount, "monto_ars_centavos": payment_amount,
            "monto_usd_centavos": 0, "monto_ars_valorizado_centavos": payment_amount,
            "tipo_cambio_milesimas": 1000,
        })
    holder = "JOR"
    in_detail = False
    for source_line, line in enumerate(normalized.splitlines(), 1):
        if "DETALLE DEL CONSUMO" in line:
            in_detail = True
            continue
        if not in_detail:
            continue
        holder_total = re.search(r"TARJETA\s+(\d+)\s+Total Consumos de\s+(.+?)\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})", line, re.I)
        if holder_total:
            holder = "JOR" if "JOAQUIN" in holder_total.group(2).upper() else "JOA"
            continue
        if "TOTAL A PAGAR" in line:
            break
        match = re.search(r"(\d{2}-\d{2}-\d{2})\s+(.+)$", line.strip())
        if not match:
            continue
        date_raw, rest = match.groups()
        money_matches = list(re.finditer(MONEY, rest))
        if not money_matches:
            continue
        amount_text = money_matches[-1].group(0)
        middle = rest[:money_matches[-1].start()].strip()
        # Líneas como IVA incluyen una base intermedia antes del importe final.
        if "IVA" in middle.upper():
            base = re.match(r"(.+?)\s+([\d.]+,\d{2})$", middle)
            if base:
                middle = base.group(1)
        amount = _cents(amount_text)
        is_usd = "USD" in middle.upper() or "U$S" in middle.upper()
        cuota = re.search(r"\b(\d{2}/\d{2})\b", middle)
        description = re.sub(r"\b\d{6,}\b", " ", middle)
        description = re.sub(r"\b\d{2}/\d{2}\b", " ", description)
        description = re.sub(r"^[*K]\s*", "", description).strip(" $-")
        kind = _kind(description, amount)
        operation_holder = holder if kind == "CONSUMO" else "JOR"
        operations.append({
            "orden": len(operations) + 1, "linea_origen": source_line,
            "fecha_compra": datetime.strptime(date_raw, "%d-%m-%y").date().isoformat(),
            "comprobante": None, "descripcion": description,
            "cuota": cuota.group(1) if cuota else None, "tipo_movimiento": kind,
            "titular_codigo": operation_holder,
            "moneda_original": "USD" if is_usd else "ARS",
            "monto_original_centavos": amount, "monto_ars_centavos": 0 if is_usd else amount,
            "monto_usd_centavos": amount if is_usd else 0,
            "monto_ars_valorizado_centavos": 0 if is_usd else amount,
            "tipo_cambio_milesimas": 1000,
        })
    if not operations:
        raise ValueError("No se encontraron operaciones Visa Galicia")

    subtotals = re.findall(r"TARJETA\s+\d+\s+Total Consumos de.*?([\d.]+,\d{2})\s+([\d.]+,\d{2})", normalized, re.I)
    previous_ars, previous_usd = _cents(previous.group(1)), _cents(previous.group(2))
    total_ars, total_usd = _cents(total.group(1)), _cents(total.group(2))
    movement_ars = sum(row["monto_ars_centavos"] for row in operations)
    movement_usd = sum(row["monto_usd_centavos"] for row in operations)
    expenses = [row for row in operations if row["tipo_movimiento"] != "PAGO"]
    summary = {
        "fuente": "Visa Galicia", "titular_codigo": "JOR", "numero_cuenta": account.group(1),
        "clasificar_automaticamente": False,
        "iva_computable_segun_leyenda": not bool(re.search(
            r"IVA discriminado no puede computarse como credito fiscal", normalized, re.I
        )),
        "numero_resumen": number.group(1), "periodo": close_date[:7], "fecha_cierre": close_date,
        "fecha_vencimiento": due_date, "fecha_cierre_anterior": date_values[0],
        "fecha_vencimiento_anterior": date_values[1], "fecha_proximo_cierre": date_values[4],
        "fecha_proximo_vencimiento": date_values[5], "cuenta_debito": None,
        "saldo_anterior_ars_centavos": previous_ars, "saldo_anterior_usd_centavos": previous_usd,
        "saldo_actual_ars_centavos": total_ars, "saldo_actual_usd_centavos": total_usd,
        "pago_minimo_ars_centavos": _cents(minimum.group(1)), "pago_minimo_anterior_ars_centavos": None,
        "consumos_declarados_ars_centavos": sum(_cents(x[0]) for x in subtotals),
        "consumos_declarados_usd_centavos": sum(_cents(x[1]) for x in subtotals),
        "nuevos_cargos_ars_centavos": sum(x["monto_ars_centavos"] for x in expenses),
        "nuevos_cargos_usd_centavos": sum(x["monto_usd_centavos"] for x in expenses),
        "intereses_ars_centavos": sum(x["monto_ars_centavos"] for x in expenses if x["tipo_movimiento"] == "INTERES"),
        "impuestos_ars_centavos": sum(x["monto_ars_centavos"] for x in expenses if x["tipo_movimiento"] == "IMPUESTO"),
        "pagos_ars_centavos": sum(x["monto_ars_centavos"] for x in operations if x["tipo_movimiento"] == "PAGO"),
        "transferencia_deuda_ars_centavos": 0, "transferencia_deuda_usd_centavos": 0,
        "diferencia_ars_centavos": total_ars - previous_ars - movement_ars,
        "diferencia_usd_centavos": total_usd - previous_usd - movement_usd,
        "tna_ars_milesimas": 76700, "tem_ars_milesimas": 6304, "tea_ars_milesimas": 110390,
        "cftea_ars_iva_milesimas": 144580,
        "cantidad_operaciones": len(operations), "cantidad_consumos": len(expenses),
    }
    summary["conciliado"] = summary["diferencia_ars_centavos"] == 0 and summary["diferencia_usd_centavos"] == 0
    summary["documento_clave"] = f"VISA_GALICIA|{account.group(1)}|{number.group(1)}|{close_date}"
    summary["hash_contenido_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {"resumen": summary, "operaciones": operations, "consumos": expenses}
