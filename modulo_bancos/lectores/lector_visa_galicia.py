"""Ingesta ELT del resumen Visa Banco Galicia."""

from __future__ import annotations

import hashlib
import logging
import os

import PyPDF2

from modulo_bancos import storage_bancos
from modulo_bancos.lectores.visa_galicia_parser import parse_visa_galicia_text
from modulo_gastos import storage_gastos

logger = logging.getLogger(__name__)
PARSER_VERSION = "visa-galicia/1.0.1"


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _extract_text(path):
    with open(path, "rb") as source:
        return "\n".join(page.extract_text() or "" for page in PyPDF2.PdfReader(source).pages)


def procesar_archivo(file_path, force_reprocess=False):
    if not os.path.isfile(file_path):
        return False, {"motivo": "ARCHIVO_INEXISTENTE"}
    digest = _sha256(file_path)
    previous_raw = storage_bancos.obtener_staging_por_hash(digest)
    staging_id = None
    try:
        text = _extract_text(file_path)
        staging_id, should_process = storage_bancos.iniciar_staging_documento(
            nombre_archivo=os.path.basename(file_path), hash_sha256=digest, modulo="gastos",
            tipo_fuente="VISA_GALICIA", formato_raw="TEXT", parser_version=PARSER_VERSION,
            contenido_raw=text, reprocesar=force_reprocess,
        )
        if not should_process:
            return False, {"motivo": "HASH_EXISTENTE", "staging_id": staging_id}
        parsed = parse_visa_galicia_text(text)
        summary = parsed["resumen"]
        persisted, detail = storage_gastos.guardar_resumen_visa_hipotecario(
            parsed, staging_id=staging_id, parser_version=PARSER_VERSION,
            reconstruir=force_reprocess,
        )
        if not persisted:
            canonical = detail["raw_canonico_id"]
            if canonical != staging_id:
                storage_bancos.marcar_staging_duplicado(
                    staging_id, raw_canonico_id=canonical, filas_leidas=summary["cantidad_operaciones"])
            return True, _info(summary, hash_archivo=digest, duplicado=True, **detail)
        return True, _info(summary, hash_archivo=digest, duplicado=False, **detail)
    except Exception as exc:
        if staging_id is not None:
            storage_bancos.finalizar_staging_documento(
                staging_id, 0, error=exc, preservar_estado=bool(previous_raw))
        logger.exception("Error procesando Visa Galicia")
        return False, {"motivo": "ERROR_PARSER", "error": str(exc)}


def _info(summary, **extra):
    info = {
        "modulo": "BANCOS", "anio": summary["periodo"][:4], "mes": summary["periodo"][5:7],
        "entidad": "VISA_GALICIA", "db_table": "gastos_tarjeta_resumenes", "id_insertado": extra.get("resumen_id", 0),
    }
    info.update(extra)
    return info
