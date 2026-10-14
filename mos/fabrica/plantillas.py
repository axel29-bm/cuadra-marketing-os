"""Catálogo de plantillas visuales (carpeta plantillas/). Cada plantilla tiene un plantilla.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path


def disponibles(raiz: Path) -> set[str]:
    carpeta = raiz / "plantillas"
    if not carpeta.exists():
        return set()
    return {p.parent.name for p in carpeta.glob("*/plantilla.toml")}


def ficha(raiz: Path, nombre: str) -> dict:
    ruta = raiz / "plantillas" / nombre / "plantilla.toml"
    if not ruta.exists():
        raise KeyError(f"No existe la plantilla «{nombre}». Disponibles: {', '.join(sorted(disponibles(raiz)))}")
    return tomllib.loads(ruta.read_text(encoding="utf-8"))
