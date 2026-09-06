"""Lector ELT y parser puro del resumen Mastercard Banco Galicia."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import PyPDF2

from modulo_bancos import storage_bancos
from modulo_gastos import storage_gastos

logger = logging.getLogger(__name__)
PARSER_VERSION = "mastercard-galicia/1.0.0"
MONEY = r"-?[\d.]+,\d{2}"


def _ascii(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value or "")
                   if not unicodedata.combining(char))


def _cents(value: str) -> int:
    number = Decimal(value.strip().replace(".", "").replace(",", "."))
    return int((number * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _date(value: str) -> str:
    months = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
              "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}
    day, month, year = value.upper().split("-")
    return datetime(2000 + int(year), months[month], int(day)).date().isoformat()


def _operation(*, order, line, date, description, kind, holder, currency,
               amount, receipt=None, installment=None, original_country=None,
               original_currency=None, original_amount=None):
    return {
        "orden": order, "linea_origen": line, "fecha_compra": date,
        "comprobante": receipt, "descripcion": description, "cuota": installment,
        "tipo_movimiento": kind, "titular_codigo": holder,
        "moneda_original": currency, "monto_original_centavos": amount,
        "monto_ars_centavos": amount if currency == "ARS" else 0,
        "monto_usd_centavos": amount if currency == "USD" else 0,
        # No se inventa un tipo de cambio para pesificar consumos en USD.
        "monto_ars_valorizado_centavos": amount if currency == "ARS" else 0,
        "tipo_cambio_milesimas": 1000 if currency == "ARS" else 0,
        "pais_operacion_original": original_country,
        "moneda_operacion_original": original_currency,
        "monto_operacion_original_centavos": original_amount,
    }


def _parse_detail(text: str) -> tuple[list[dict], dict]:
    start = text.find("DETALLE DEL CONSUMO")
    end_match = re.search(r"TOTAL ADICIONAL DE\s+NICOLETTI,JOAQUIN", text, re.I)
    if start < 0 or not end_match:
        raise ValueError("Detalle Mastercard Galicia incompleto")
    detail = text[start:end_match.end()]
    split_at = detail.rfind("\nSUBTOTAL ")
    if split_at < 0:
        raise ValueError("No se pudo separar titular y adicional Mastercard Galicia")

    operations = []
    row_re = re.compile(
        rf"^(\d{{2}}-[A-Za-z]{{3}}-\d{{2}})\s+(.+?)\s+(\d{{5}})\s+({MONEY})\s*$"
    )
    foreign_re = re.compile(rf"\(([A-Z]{{3}}),([A-Z]{{3}}),\s*({MONEY})\)", re.I)
    running_offset = 0
    for line_number, line in enumerate(detail.splitlines(keepends=True), 1):
        match = row_re.match(line.strip())
        if match:
            date_raw, reference, receipt, billed_raw = match.groups()
            holder = "JOR" if running_offset < split_at else "JOA"
            installment_match = re.search(r"\b(\d{2}/\d{2})\b", reference)
            foreign_match = foreign_re.search(reference)
            currency = "USD" if foreign_match else "ARS"
            original_country = foreign_match.group(1).upper() if foreign_match else None
            original_currency = foreign_match.group(2).upper() if foreign_match else None
            original_amount = _cents(foreign_match.group(3)) if foreign_match else None
            description = re.sub(r"\s+", " ", reference).strip()
            if installment_match:
                description = re.sub(r"\b\d{2}/\d{2}\b", "", description).strip()
            operations.append(_operation(
                order=len(operations) + 1,
                line=text[:start].count("\n") + line_number,
                date=_date(date_raw), description=description, kind="CONSUMO",
                holder=holder, currency=currency, amount=_cents(billed_raw),
                receipt=receipt,
                installment=installment_match.group(1) if installment_match else None,
                original_country=original_country, original_currency=original_currency,
                original_amount=original_amount,
            ))
        running_offset += len(line)

    jor_subtotal = re.search(rf"SUBTOTAL\s+({MONEY})\s+({MONEY})", detail, re.I)
    joa_subtotal = re.search(
        rf"TOTAL ADICIONAL DE\s+NICOLETTI,JOAQUIN\s+({MONEY})\s+({MONEY})", text, re.I)
    if not operations or not jor_subtotal or not joa_subtotal:
        raise ValueError("Consumos o subtotales Mastercard Galicia incompletos")
    declared = {
        "JOR_ARS": _cents(jor_subtotal.group(1)), "JOR_USD": _cents(jor_subtotal.group(2)),
        "JOA_ARS": _cents(joa_subtotal.group(1)), "JOA_USD": _cents(joa_subtotal.group(2)),
    }
    for holder in ("JOR", "JOA"):
        for currency in ("ARS", "USD"):
            parsed_total = sum(row["monto_original_centavos"] for row in operations
                               if row["titular_codigo"] == holder
                               and row["moneda_original"] == currency)
            if parsed_total != declared[f"{holder}_{currency}"]:
                raise ValueError(
                    f"Subtotal {holder} {currency} no concilia: "
                    f"PDF={declared[f'{holder}_{currency}']} parser={parsed_total}"
                )
    return operations, declared


def _rate_milli(value: str) -> int:
    return int((Decimal(value.replace(",", ".")) * 1000)
               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _parse_financing(text: str) -> dict:
    principal = re.search(rf"saldo adeudado de\s*\$\s*({MONEY})", text, re.I)
    valid_until = re.search(r"beneficio hasta el\s+(\d{2}/\d{2}/\d{2})", text, re.I)
    options = []
    option_re = re.compile(
        rf"(\d{{1,2}}) cuotas de \$\s*({MONEY})\*\s*\(TNA:\s*([\d,]+)%\s*-\s*"
        rf"TEA:\s*([\d,]+)%\s*-\s*CFT:\s*([\d,]+)%\s*-\s*CFT S/IVA:\s*([\d,]+)%\)",
        re.I,
    )
    for match in option_re.finditer(text):
        installments, amount, tna, tea, cft, cft_no_vat = match.groups()
        options.append({
            "cuotas": int(installments), "cuota_centavos": _cents(amount),
            "tna_milesimas": _rate_milli(tna), "tea_milesimas": _rate_milli(tea),
            "cft_milesimas": _rate_milli(cft),
            "cft_sin_iva_milesimas": _rate_milli(cft_no_vat),
            "incluye_comision": False, "incluye_iva_intereses_comisiones": False,
        })
    if not principal or not valid_until or len(options) != 23:
        raise ValueError("Oferta de financiación Mastercard Galicia incompleta")
    return {
        "capital_ofrecido_centavos": _cents(principal.group(1)),
        "vigente_hasta": datetime.strptime(valid_until.group(1), "%d/%m/%y").date().isoformat(),
        "opciones": options,
    }


def parse_mastercard_galicia_text(text: str) -> dict:
    """Convierte el texto Mastercard a centavos y exige conciliación exacta."""
    normalized = _ascii(text)
    number = re.search(r"Resumen N.?\s*(\d{12})", normalized, re.I)
    member = re.search(r"N.? de Socio:\s*([\d-]+)", normalized, re.I)
    dates = re.search(
        r"(\d{2}-[A-Za-z]{3}-\d{2})\s+(\d{2}-[A-Za-z]{3}-\d{2})\s+"
        r"(\d{2}-[A-Za-z]{3}-\d{2})\s+(\d{2}-[A-Za-z]{3}-\d{2})\s+"
        r"(\d{2}-[A-Za-z]{3}-\d{2})\s+(\d{2}-[A-Za-z]{3}-\d{2})", normalized)
    status = re.search(r"DOMINGUEZ,JORGELINA B\s+([A-Z ]+?)\s+CUIT Banco", normalized, re.I)
    if not number or not member or not dates or not status:
        raise ValueError("Cabecera Mastercard Galicia incompleta")
    date_values = [_date(value) for value in dates.groups()]
    close_date, due_date = date_values[2], date_values[3]

    previous = re.search(rf"SALDO ANTERIOR\s+({MONEY})\s+({MONEY})", normalized, re.I)
    total = re.search(rf"TOTAL A PAGAR\s+({MONEY})\s+({MONEY})", normalized, re.I)
    minimum = re.search(rf"PAGO MINIMO.*?\$\s*({MONEY})", normalized, re.I | re.S)
    purchases_total = re.search(rf"TOTAL CONSUMOS DEL MES\s+({MONEY})\s+({MONEY})", normalized, re.I)
    if not previous or not total or not minimum or not purchases_total:
        raise ValueError("Saldos Mastercard Galicia incompletos")

    operations = []
    payment = re.search(rf"^(\d{{2}}-[A-Za-z]{{3}}-\d{{2}})\s+SU PAGO\s+({MONEY})", normalized, re.I | re.M)
    transfers = re.findall(rf"^(\d{{2}}-[A-Za-z]{{3}}-\d{{2}})\s+TRANSFER FINANC\. PESOS\s+({MONEY})",
                           normalized, re.I | re.M)
    if not payment or len(transfers) != 2:
        raise ValueError("Pago o transferencias financieras Mastercard incompletos")
    operations.append(_operation(
        order=1, line=normalized[:payment.start()].count("\n") + 1,
        date=_date(payment.group(1)), description="SU PAGO", kind="PAGO",
        holder="JOR", currency="ARS", amount=_cents(payment.group(2))))
    for index, (date_raw, amount_raw) in enumerate(transfers):
        currency = "ARS" if index == 0 else "USD"
        operations.append(_operation(
            order=len(operations) + 1,
            line=next(i for i, row in enumerate(normalized.splitlines(), 1)
                      if date_raw in row and "TRANSFER FINANC" in row and amount_raw in row),
            date=_date(date_raw), description="TRANSFER FINANC. PESOS",
            kind="TRANSFERENCIA_DEUDA", holder="JOR", currency=currency,
            amount=_cents(amount_raw)))

    detail_operations, declared = _parse_detail(normalized)
    for row in detail_operations:
        row["orden"] = len(operations) + 1
        operations.append(row)

    charge_specs = (("INTERESES DE FINANCIACION", "INTERES"),
                    ("IMPUESTO DE SELLOS", "IMPUESTO"),
                    ("I.V.A. 21,0%", "IMPUESTO"),
                    ("PERCEPCION IVA DTO 354/18", "IMPUESTO"),
                    ("PERCEP.AFIP RG 4815 30%", "IMPUESTO"))
    for label, kind in charge_specs:
        charge = re.search(rf"^{re.escape(label)}\s+({MONEY})(?:\s+({MONEY}))?", normalized, re.I | re.M)
        if not charge:
            raise ValueError(f"Cargo Mastercard faltante: {label}")
        for index, currency in ((1, "ARS"), (2, "USD")):
            if charge.group(index) is not None:
                operations.append(_operation(
                    order=len(operations) + 1,
                    line=normalized[:charge.start()].count("\n") + 1,
                    date=close_date, description=label, kind=kind, holder="JOR",
                    currency=currency, amount=_cents(charge.group(index))))

    previous_ars, previous_usd = _cents(previous.group(1)), _cents(previous.group(2))
    total_ars, total_usd = _cents(total.group(1)), _cents(total.group(2))
    movement_ars = sum(row["monto_ars_centavos"] for row in operations)
    movement_usd = sum(row["monto_usd_centavos"] for row in operations)
    expenses = [row for row in operations
                if row["tipo_movimiento"] not in {"PAGO", "TRANSFERENCIA_DEUDA"}]
    financing = _parse_financing(normalized)
    fiscal_warning = bool(re.search(
        r"IVA discriminado no puede computarse como credito fiscal", normalized, re.I))
    summary = {
        "fuente": "Mastercard Galicia", "titular_codigo": "JOR",
        "numero_cuenta": member.group(1), "clasificar_automaticamente": False,
        "numero_resumen": number.group(1), "periodo": close_date[:7],
        "fecha_cierre": close_date, "fecha_vencimiento": due_date,
        "fecha_cierre_anterior": date_values[0], "fecha_vencimiento_anterior": date_values[1],
        "fecha_proximo_cierre": date_values[4], "fecha_proximo_vencimiento": date_values[5],
        "cuenta_debito": None, "condicion_iva_impresa": status.group(1).strip(),
        "iva_computable_segun_leyenda": not fiscal_warning,
        "saldo_anterior_ars_centavos": previous_ars, "saldo_anterior_usd_centavos": previous_usd,
        "saldo_actual_ars_centavos": total_ars, "saldo_actual_usd_centavos": total_usd,
        "pago_minimo_ars_centavos": _cents(minimum.group(1)), "pago_minimo_anterior_ars_centavos": None,
        "consumos_declarados_ars_centavos": _cents(purchases_total.group(1)),
        "consumos_declarados_usd_centavos": _cents(purchases_total.group(2)),
        "nuevos_cargos_ars_centavos": sum(row["monto_ars_centavos"] for row in expenses),
        "nuevos_cargos_usd_centavos": sum(row["monto_usd_centavos"] for row in expenses),
        "intereses_ars_centavos": sum(row["monto_ars_centavos"] for row in expenses
                                      if row["tipo_movimiento"] == "INTERES"),
        "impuestos_ars_centavos": sum(row["monto_ars_centavos"] for row in expenses
                                      if row["tipo_movimiento"] == "IMPUESTO"),
        "pagos_ars_centavos": sum(row["monto_ars_centavos"] for row in operations
                                  if row["tipo_movimiento"] == "PAGO"),
        "transferencia_deuda_ars_centavos": sum(row["monto_ars_centavos"] for row in operations
                                                if row["tipo_movimiento"] == "TRANSFERENCIA_DEUDA"),
        "transferencia_deuda_usd_centavos": sum(row["monto_usd_centavos"] for row in operations
                                                if row["tipo_movimiento"] == "TRANSFERENCIA_DEUDA"),
        "diferencia_ars_centavos": total_ars - previous_ars - movement_ars,
        "diferencia_usd_centavos": total_usd - previous_usd - movement_usd,
        "tna_ars_milesimas": 76700, "tem_ars_milesimas": 6317,
        "tea_ars_milesimas": 110701, "cftea_ars_iva_milesimas": 144580,
        "cantidad_operaciones": len(operations), "cantidad_consumos": len(expenses),
    }
    if declared["JOR_ARS"] + declared["JOA_ARS"] != summary["consumos_declarados_ars_centavos"]:
        raise ValueError("Los subtotales ARS por tarjeta no coinciden con el consolidado")
    if declared["JOR_USD"] + declared["JOA_USD"] != summary["consumos_declarados_usd_centavos"]:
        raise ValueError("Los subtotales USD por tarjeta no coinciden con el consolidado")
    # Una línea física puede contener dos importes (ARS y USD). Conservamos su
    # ubicación documental y usamos el orden de operación como clave productiva.
    for order, operation in enumerate(operations, 1):
        operation["linea_documento"] = operation["linea_origen"]
        operation["orden"] = order
        operation["linea_origen"] = order
    summary["conciliado"] = (summary["diferencia_ars_centavos"] == 0
                             and summary["diferencia_usd_centavos"] == 0)
    summary["documento_clave"] = (
        f"MASTERCARD_GALICIA|{member.group(1)}|{number.group(1)}|{close_date}")
    summary["hash_contenido_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {"resumen": summary, "operaciones": operations, "consumos": expenses,
            "subtotales_documentales": declared, "financiacion_ofrecida": financing}


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _extract_text(path: str) -> str:
    with open(path, "rb") as source:
        return "\n".join(page.extract_text() or "" for page in PyPDF2.PdfReader(source).pages)


def procesar_archivo(file_path: str, force_reprocess: bool = False):
    """Orquesta RAW, parser y persistencia; el archivado físico lo hace el master."""
    if not os.path.isfile(file_path):
        return False, {"motivo": "ARCHIVO_INEXISTENTE"}
    digest = _sha256(file_path)
    previous_raw = storage_bancos.obtener_staging_por_hash(digest)
    staging_id = None
    try:
        text = _extract_text(file_path)
        staging_id, should_process = storage_bancos.iniciar_staging_documento(
            nombre_archivo=os.path.basename(file_path), hash_sha256=digest, modulo="gastos",
            tipo_fuente="MASTERCARD_GALICIA", formato_raw="TEXT",
            parser_version=PARSER_VERSION, contenido_raw=text, reprocesar=force_reprocess)
        if not should_process:
            return False, {"motivo": "HASH_EXISTENTE", "staging_id": staging_id}
        parsed = parse_mastercard_galicia_text(text)
        summary = parsed["resumen"]
        persisted, detail = storage_gastos.guardar_resumen_tarjeta(
            parsed, staging_id=staging_id, parser_version=PARSER_VERSION,
            reconstruir=force_reprocess)
        if not persisted:
            canonical = detail["raw_canonico_id"]
            if canonical != staging_id:
                storage_bancos.marcar_staging_duplicado(
                    staging_id, raw_canonico_id=canonical,
                    filas_leidas=summary["cantidad_operaciones"])
            return True, _info(summary, digest, duplicado=True, **detail)
        return True, _info(summary, digest, duplicado=False, **detail)
    except Exception as exc:
        if staging_id is not None:
            storage_bancos.finalizar_staging_documento(
                staging_id, 0, error=exc, preservar_estado=bool(previous_raw))
        logger.exception("Error procesando Mastercard Galicia")
        return False, {"motivo": "ERROR_PARSER", "error": str(exc), "staging_id": staging_id}


def _info(summary: dict, digest: str, **extra) -> dict:
    info = {"modulo": "BANCOS", "anio": summary["periodo"][:4],
            "mes": summary["periodo"][5:7], "entidad": "MASTERCARD_GALICIA",
            "db_table": "gastos_tarjeta_resumenes",
            "id_insertado": extra.get("resumen_id", 0), "hash_archivo": digest}
    info.update(extra)
    return info
