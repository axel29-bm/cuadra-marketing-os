"""Formatos y límites por canal (semillas/canales.toml)."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from .config import RAIZ


@lru_cache(maxsize=4)
def todos(raiz: Path = RAIZ) -> dict[str, dict]:
    ruta = raiz / "semillas" / "canales.toml"
    if not ruta.exists():
        return {}
    return tomllib.loads(ruta.read_text(encoding="utf-8")).get("canal", {})


def canal(nombre: str, raiz: Path = RAIZ) -> dict:
    return todos(raiz).get(nombre, {})


def limites(nombre: str, raiz: Path = RAIZ) -> dict[str, int]:
    """Campos de texto y su máximo de caracteres, en la forma que espera el auditor."""
    c = canal(nombre, raiz)
    salida = {}
    if "max_copy" in c:
        salida["copy"] = c["max_copy"]
    if "max_titulo" in c:
        salida["titulo"] = c["max_titulo"]
    return salida
