from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cents(value: str | int | Decimal | None) -> int:
    """Convierte importes argentinos o decimales Payway a centavos exactos."""
    if value is None or value == "":
        return 0
    if isinstance(value, (int, Decimal)):
        number = Decimal(value)
    else:
        raw = str(value).strip().replace("$", "").replace("U$S", "")
        raw = "".join(char for char in raw if char.isdigit() or char in ",.-")
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        try:
            number = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError(f"Importe Payway invalido: {value!r}") from exc
    return int((number * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def slash_path(path: str) -> str:
    return Path(path).resolve().as_posix()
