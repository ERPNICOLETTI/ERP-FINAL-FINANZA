"""Lector único ELT para resúmenes PDF de Cuenta Corriente Galicia."""

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

logger = logging.getLogger(__name__)
PARSER_VERSION = "galicia-cuenta-corriente-pdf/1.0.0"
MONEY = r"-?[\d.]+,\d{2}"


def _ascii(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value or "")
                   if not unicodedata.combining(char))


def _cents(value: str) -> int:
    number = Decimal(value.strip().replace(".", "").replace(",", "."))
    return int((number * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _date(value: str) -> str:
    return datetime.strptime(value, "%d/%m/%Y" if len(value) == 10 else "%d/%m/%y").date().isoformat()


def _movement_type(description: str) -> str:
    upper = description.upper()
    if upper.startswith("ECHEQ"):
        return "ECHEQ"
    if upper.startswith("TRANSF. CTAS PROPIAS"):
        return "TRANSFERENCIA_PROPIA"
    if "LEY 25413" in upper:
        return "IMPUESTO_LEY_25413"
    if "INTERESES SOBRE SALDOS" in upper:
        return "INTERES_SALDO_DEUDOR"
    if "IMPUESTO DE SELLOS" in upper:
        return "IMPUESTO_SELLOS"
    if upper.startswith("IVA"):
        return "IVA_INTERESES"
    return "MOVIMIENTO"


def parse_galicia_cuenta_corriente_text(text: str) -> dict:
    """Lee movimientos, cabecera fiscal y saldos; exige cadena de saldos exacta."""
    normalized = _ascii(text)
    if "Resumen de Cuenta Corriente en Pesos" not in normalized:
        raise ValueError("El PDF no es un resumen de Cuenta Corriente Galicia")
    account = re.search(r"N.?\s*(\d{7}-\d\s+\d{3}-\d)", normalized)
    cbu = re.search(r"CBU\s+(\d{22})", normalized)
    cuit = re.search(r"CUIT del Responsable Impositivo\s*:\s*([\d-]+)", normalized, re.I)
    status = re.search(r"IVA:\s*([^\n]+?)JORGELINA", normalized, re.I)
    period = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})Periodo de movimientos", normalized)
    balances = re.search(rf"\$({MONEY})-\$({MONEY})-Saldos", normalized)
    totals = re.search(rf"Total \$\s*({MONEY})\s+-\$\s*({MONEY})\s+\$\s*({MONEY})-", normalized, re.I)
    if not all((account, cbu, cuit, status, period, balances, totals)):
        raise ValueError("Cabecera o totales de Cuenta Corriente Galicia incompletos")
    fecha_hasta, fecha_desde = _date(period.group(1)), _date(period.group(2))
    saldo_final = -_cents(balances.group(1))
    saldo_inicial = -_cents(balances.group(2))
    creditos = _cents(totals.group(1))
    debitos = -_cents(totals.group(2))
    total_saldo = -_cents(totals.group(3))
    if total_saldo != saldo_final:
        raise ValueError("El saldo final de cabecera difiere del total de movimientos")

    movement_start = normalized.find("Movimientos\n")
    movement_end = normalized.find("   Total $", movement_start)
    if movement_start < 0 or movement_end < 0:
        raise ValueError("Sección de movimientos de Cuenta Corriente incompleta")
    section = normalized[movement_start:movement_end]
    blocks = re.finditer(
        r"(?ms)^(\d{2}/\d{2}/\d{2})\s+(.*?)(?=^\d{2}/\d{2}/\d{2}\s+|\Z)", section)
    movements = []
    running_balance = saldo_inicial
    for block in blocks:
        date_raw, body = block.groups()
        # El salto de página puede agregar encabezados después del saldo; sólo
        # tomamos el primer par importe/saldo perteneciente al movimiento.
        values = re.search(rf"(?s)^(.*?)({MONEY})\s+([\d.]+,\d{{2}})-", body.strip())
        if not values:
            raise ValueError(f"Movimiento Galicia ilegible: {body[:80]!r}")
        description_raw, amount_raw, balance_raw = values.groups()
        description = re.sub(r"\s+", " ", description_raw).strip()
        amount = _cents(amount_raw)
        balance = -_cents(balance_raw)
        running_balance += amount
        if running_balance != balance:
            raise ValueError(
                f"Saldo corrido no concilia en {_date(date_raw)} {description}: "
                f"esperado={running_balance} PDF={balance}"
            )
        movements.append({
            "numero_linea": len(movements) + 1,
            "linea_documento": normalized[:movement_start + block.start()].count("\n") + 1,
            "fecha": _date(date_raw), "descripcion": description,
            "tipo_movimiento": _movement_type(description),
            "importe_centavos": amount, "saldo_centavos": balance,
            "credito_centavos": amount if amount > 0 else 0,
            "debito_centavos": amount if amount < 0 else 0,
        })
    if len(movements) != 33:
        raise ValueError(f"Cantidad inesperada de movimientos Galicia: {len(movements)}")
    if sum(row["credito_centavos"] for row in movements) != creditos:
        raise ValueError("Los créditos detallados no coinciden con el total del PDF")
    if sum(row["debito_centavos"] for row in movements) != debitos:
        raise ValueError("Los débitos detallados no coinciden con el total del PDF")

    def amount_for(kind: str) -> int:
        return abs(sum(row["importe_centavos"] for row in movements
                       if row["tipo_movimiento"] == kind))

    average = re.search(rf"Promedio\s+\d{{6}}\s+\$({MONEY})", normalized, re.I)
    debtor_cost = re.search(rf"Intereses\s+\$({MONEY})", normalized, re.I)
    agreement = re.search(
        rf"Sujeto a condiciones convenidas \$({MONEY})\s+%(\d+,\d{{2}})\s+"
        r"(\d{2}-\d{2}-\d{4})\s+(\d{2}-\d{2}-\d{4})", normalized, re.I)
    tax_debits = re.search(rf"TOTAL RETENCION IMPUESTO LEY 25\.413 SOBRE DEBITOS({MONEY})", normalized, re.I)
    tax_credit = re.search(rf"CREDITO COMPUTABLE COMO PAGO A CUENTA({MONEY})", normalized, re.I)
    if not all((average, debtor_cost, agreement, tax_debits, tax_credit)):
        raise ValueError("Información financiera o fiscal consolidada incompleta")
    interest = amount_for("INTERES_SALDO_DEUDOR")
    vat = amount_for("IVA_INTERESES")
    stamp = amount_for("IMPUESTO_SELLOS")
    if interest + vat + stamp != _cents(debtor_cost.group(1)):
        raise ValueError("Interés + IVA + sellos no coincide con Saldos Deudores")
    warning = bool(re.search(
        r"IVA discriminado no puede computarse como credito fiscal", normalized, re.I))
    difference = saldo_final - saldo_inicial - creditos - debitos
    summary = {
        "banco": "GALICIA", "entidad": "LDK", "tipo_cuenta": "CUENTA_CORRIENTE_ARS",
        "numero_cuenta": account.group(1), "cbu": cbu.group(1), "cuit_titular": cuit.group(1),
        "condicion_iva_impresa": status.group(1).strip(),
        "iva_computable_segun_leyenda": not warning,
        "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta,
        "saldo_inicial_centavos": saldo_inicial, "creditos_centavos": creditos,
        "debitos_centavos": debitos, "saldo_final_centavos": saldo_final,
        "intereses_centavos": interest, "iva_intereses_centavos": vat,
        "sellos_centavos": stamp,
        "impuesto_ley_25413_centavos": amount_for("IMPUESTO_LEY_25413"),
        "impuesto_ley_25413_consolidado_centavos": _cents(tax_debits.group(1)),
        "impuesto_ley_25413_pago_cuenta_centavos": _cents(tax_credit.group(1)),
        "promedio_saldos_deudores_centavos": _cents(average.group(1)),
        "costo_saldos_deudores_centavos": _cents(debtor_cost.group(1)),
        "acuerdo_limite_centavos": _cents(agreement.group(1)),
        "acuerdo_tna_milesimas": int(Decimal(agreement.group(2).replace(",", ".")) * 1000),
        "acuerdo_alta": datetime.strptime(agreement.group(3), "%d-%m-%Y").date().isoformat(),
        "acuerdo_vencimiento": datetime.strptime(agreement.group(4), "%d-%m-%Y").date().isoformat(),
        "tna_extraordinaria_milesimas": 137500,
        "diferencia_centavos": difference, "conciliado": difference == 0,
        "cantidad_movimientos": len(movements),
    }
    summary["documento_clave"] = (
        f"GALICIA_CC|{summary['numero_cuenta']}|{fecha_desde}|{fecha_hasta}")
    return {"resumen": summary, "movimientos": movements}


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
    if not os.path.isfile(file_path):
        return False, {"motivo": "ARCHIVO_INEXISTENTE"}
    digest = _sha256(file_path)
    previous_raw = storage_bancos.obtener_staging_por_hash(digest)
    staging_id = None
    try:
        text = _extract_text(file_path)
        staging_id, should_process = storage_bancos.iniciar_staging_documento(
            nombre_archivo=os.path.basename(file_path), hash_sha256=digest, modulo="bancos",
            tipo_fuente="GALICIA_CUENTA_CORRIENTE_PDF", formato_raw="TEXT",
            parser_version=PARSER_VERSION, contenido_raw=text, reprocesar=force_reprocess)
        if not should_process:
            return False, {"motivo": "HASH_EXISTENTE", "staging_id": staging_id}
        parsed = parse_galicia_cuenta_corriente_text(text)
        persisted, detail = storage_bancos.guardar_extracto_cuenta_corriente(
            parsed, staging_id=staging_id, parser_version=PARSER_VERSION,
            reconstruir=force_reprocess)
        if not persisted:
            canonical = detail["raw_canonico_id"]
            if canonical != staging_id:
                storage_bancos.marcar_staging_duplicado(
                    staging_id, raw_canonico_id=canonical,
                    filas_leidas=len(parsed["movimientos"]))
            return True, _info(parsed["resumen"], digest, duplicado=True, **detail)
        return True, _info(parsed["resumen"], digest, duplicado=False, **detail)
    except Exception as exc:
        if staging_id is not None:
            storage_bancos.finalizar_staging_documento(
                staging_id, 0, error=exc, preservar_estado=bool(previous_raw))
        logger.exception("Error procesando Cuenta Corriente Galicia")
        return False, {"motivo": "ERROR_PARSER", "error": str(exc), "staging_id": staging_id}


def _info(summary: dict, digest: str, **extra) -> dict:
    info = {
        "modulo": "BANCOS", "anio": summary["fecha_hasta"][:4],
        "mes": summary["fecha_hasta"][5:7], "entidad": "GALICIA_CUENTA_CORRIENTE",
        "db_table": "bancos_extractos_resumenes",
        "id_insertado": extra.get("resumen_id", 0), "hash_archivo": digest,
    }
    info.update(extra)
    return info
