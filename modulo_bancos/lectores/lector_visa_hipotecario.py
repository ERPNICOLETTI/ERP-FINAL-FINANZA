"""Ingesta ELT del resumen Visa emitido por Banco Hipotecario (JOA)."""

from __future__ import annotations

import hashlib
import logging
import os

import PyPDF2

from modulo_bancos import storage_bancos
from modulo_bancos.lectores.visa_hipotecario_parser import parse_visa_hipotecario_text
from modulo_gastos import storage_gastos


logger = logging.getLogger(__name__)
PARSER_VERSION = "v7.0.0"


def calculate_sha256(file_path):
    digest = hashlib.sha256()
    with open(file_path, "rb") as source:
        for block in iter(lambda: source.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _extract_text(file_path):
    with open(file_path, "rb") as source:
        reader = PyPDF2.PdfReader(source)
        return "\n".join(page.extract_text() or "" for page in reader.pages)


def _master_info(summary, **extra):
    info = {
        "modulo": "BANCOS",
        "anio": summary["periodo"][:4],
        "mes": summary["periodo"][5:7],
        "entidad": "VISA_HIPOTECARIO",
        "db_table": "bancos_movimientos",
        "id_insertado": 0,
    }
    info.update(extra)
    return info


def procesar_archivo(file_path, force_reprocess=False):
    """Ingiere, concilia y persiste una liquidación sin duplicarla.

    La identidad física se controla por SHA-256 en ``core_staging_raw`` y la
    identidad comercial por cuenta + número de resumen + fecha de cierre.
    Sólo se guardan los consumos/reintegros; pagos y transferencia de deuda
    quedan en la cabecera de conciliación y no contaminan el gasto mensual.
    """
    if not os.path.isfile(file_path):
        logger.error("El archivo no existe: %s", file_path)
        return False, {"motivo": "ARCHIVO_INEXISTENTE"}

    file_hash = calculate_sha256(file_path)
    previous_raw = storage_bancos.obtener_staging_por_hash(file_hash)
    staging_id = None
    try:
        # Fase RAW obligatoria: el texto extraído queda registrado antes de que
        # cualquier dato llegue a las tablas productivas.
        text = _extract_text(file_path)
        staging_id, should_process = storage_bancos.iniciar_staging_documento(
            nombre_archivo=os.path.basename(file_path),
            hash_sha256=file_hash,
            modulo="gastos",
            tipo_fuente="VISA_HIPOTECARIO",
            formato_raw="TEXT",
            parser_version=PARSER_VERSION,
            contenido_raw=text,
            reprocesar=force_reprocess,
        )
        if not should_process:
            logger.info("RAW Visa Hipotecario ya procesado: %s", os.path.basename(file_path))
            return False, {"motivo": "HASH_EXISTENTE", "staging_id": staging_id}

        parsed = parse_visa_hipotecario_text(text)
        summary = parsed["resumen"]
        persisted, detail = storage_gastos.guardar_resumen_visa_hipotecario(
            parsed,
            staging_id=staging_id,
            parser_version=PARSER_VERSION,
            reconstruir=force_reprocess,
        )
        if not persisted:
            canonical_raw = detail["raw_canonico_id"]
            if canonical_raw != staging_id:
                storage_bancos.marcar_staging_duplicado(
                    staging_id,
                    raw_canonico_id=canonical_raw,
                    filas_leidas=summary["cantidad_operaciones"],
                )
            return True, _master_info(summary, duplicado=True, **detail)

        logger.info(
            "Visa Hipotecario conciliada: %s (%s consumos)",
            summary["documento_clave"], summary["cantidad_consumos"],
        )
        return True, _master_info(summary, duplicado=False, **detail)
    except Exception as error:
        if staging_id is not None:
            try:
                storage_bancos.finalizar_staging_documento(
                    staging_id,
                    0,
                    error=error,
                    preservar_estado=bool(previous_raw),
                )
            except Exception:
                logger.exception("No se pudo registrar el error de staging Visa Hipotecario")
        logger.exception("Error procesando Visa Hipotecario: %s", error)
        return False, {"motivo": "ERROR_PARSER", "error": str(error)}
