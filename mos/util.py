"""Utilidades pequeñas sin dependencias: tiempo, hashes, JSON y textos."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import unicodedata
import uuid
from typing import Any

ZONA_LIMA = _dt.timezone(_dt.timedelta(hours=-5), "America/Lima")


def ahora_utc() -> str:
    """Marca de tiempo UTC ISO-8601 con segundos."""
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hoy_lima() -> _dt.date:
    return _dt.datetime.now(ZONA_LIMA).date()


def a_json(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def de_json(texto: str | None, por_defecto: Any = None) -> Any:
    if texto is None or texto == "":
        return por_defecto
    return json.loads(texto)


def sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def sha256_archivo(ruta) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def uid() -> str:
    """Identificador opaco para registros con datos personales (no revela orden ni fecha)."""
    return uuid.uuid4().hex


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples: sirve para comparar y deduplicar."""
    return re.sub(r"\s+", " ", sin_tildes(texto).lower()).strip()


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar(texto)).strip("-")
