"""Identidad visual que leen las plantillas: colores, tipografías, iconos y logo, tomados de marcas/<slug>/marca.toml.

Cada producto hereda el sistema base y cambia solo lo suyo. Todo se incrusta en el HTML (fuentes e iconos en
base64 o en línea) para que el render no dependa de Internet ni de rutas del equipo.
"""

from __future__ import annotations

import base64
import mimetypes
import re
import tomllib
from functools import lru_cache
from pathlib import Path


def _fusionar(base: dict, propio: dict) -> dict:
    salida = dict(base)
    for clave, valor in propio.items():
        salida[clave] = _fusionar(salida[clave], valor) if isinstance(valor, dict) and isinstance(salida.get(clave), dict) else valor
    return salida


@lru_cache(maxsize=16)
def cargar(raiz: Path, slug: str = "base") -> dict:
    base = tomllib.loads((raiz / "marcas" / "base" / "marca.toml").read_text(encoding="utf-8"))
    if slug == "base":
        return base
    ruta = raiz / "marcas" / slug / "marca.toml"
    if not ruta.exists():
        raise KeyError(f"No existe la marca «{slug}» (falta {ruta.relative_to(raiz)}).")
    return _fusionar(base, tomllib.loads(ruta.read_text(encoding="utf-8")))


def variables_css(m: dict) -> str:
    color = "; ".join(f"--{k.replace('_', '-')}: {v}" for k, v in m["color"].items())
    t = m["tipografia"]
    forma = m["forma"]
    return (f"{color}; --fuente-titulos: '{t['titulos']}', {t['respaldo']}; --fuente-texto: '{t['texto']}', {t['respaldo']}; "
            f"--fuente-mono: '{t['mono']}', ui-monospace, monospace; --radio-base: {forma['radio']}; "
            f"--radio-chico-base: {forma['radio_chico']}; --margen-base: {forma['margen']}; --espacio-base: {forma['espacio']}")


def data_uri(ruta: Path) -> str:
    tipo = mimetypes.guess_type(ruta.name)[0] or ("font/woff2" if ruta.suffix == ".woff2" else "application/octet-stream")
    return f"data:{tipo};base64,{base64.b64encode(ruta.read_bytes()).decode('ascii')}"


@lru_cache(maxsize=8)
def fuentes_css(raiz: Path, slug: str = "base") -> str:
    t = cargar(raiz, slug)["tipografia"]
    reglas = []
    for familia, clave in ((t["titulos"], "archivo_titulos"), (t["mono"], "archivo_mono")):
        archivo = raiz / t[clave]
        if archivo.exists():
            reglas.append(f"@font-face {{ font-family: '{familia}'; src: url('{data_uri(archivo)}') format('woff2'); "
                          f"font-weight: 100 900; font-display: block; }}")
    return "\n".join(reglas)


@lru_cache(maxsize=256)
def icono(raiz: Path, nombre: str, grosor: float = 1.75) -> str:
    """SVG en línea de recursos/iconos/lucide. Hereda el color del texto (currentColor)."""
    if not re.fullmatch(r"[a-z0-9-]+", nombre or ""):
        raise KeyError(f"Nombre de icono no válido: «{nombre}».")
    ruta = raiz / "recursos" / "iconos" / "lucide" / f"{nombre}.svg"
    if not ruta.exists():
        disponibles = sorted(p.stem for p in ruta.parent.glob("*.svg"))
        raise KeyError(f"No existe el icono «{nombre}». Disponibles: {', '.join(disponibles)}")
    svg = re.sub(r"<!--.*?-->", "", ruta.read_text(encoding="utf-8"), flags=re.S).strip()
    svg = re.sub(r'\s(width|height)="24"', "", svg)
    return svg.replace('stroke-width="2"', f'stroke-width="{grosor}"').replace("<svg", '<svg class="icono-svg" aria-hidden="true"', 1)


def iconos_disponibles(raiz: Path) -> list[str]:
    return sorted(p.stem for p in (raiz / "recursos" / "iconos" / "lucide").glob("*.svg"))


def logo(raiz: Path, m: dict) -> str:
    ruta = raiz / m["logo"] if m.get("logo") else None
    return data_uri(ruta) if ruta and ruta.exists() else ""
