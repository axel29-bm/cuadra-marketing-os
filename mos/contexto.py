"""Contexto verificado de un producto para las tareas de los agentes (política del auditor y texto del prompt)."""

from __future__ import annotations

from .calidad.auditor import Politica
from .config import Config
from .fabrica import plantillas


def producto_unico(cfg: Config) -> str | None:
    """Si hay un solo producto configurado, es el producto por defecto."""
    carpetas = [p.name for p in (cfg.raiz / "productos").iterdir() if (p / "producto.toml").exists()]
    return carpetas[0] if len(carpetas) == 1 else None


def de_producto(cfg: Config, slug: str | None) -> tuple[dict, str]:
    """Devuelve (contexto para los criterios, texto para el prompt)."""
    if not slug:
        return {"plantillas": plantillas.disponibles(cfg.raiz)}, ""
    carpeta = cfg.raiz / "productos" / slug
    if not (carpeta / "producto.toml").exists():
        return {"plantillas": plantillas.disponibles(cfg.raiz)}, ""
    pol = Politica.desde_carpeta(carpeta)
    lineas = [f"Producto: {pol.nombre_marca}. Etapa comercial: {pol.etapa_comercial}. "
              f"Disponible al público: {'sí' if pol.disponible_al_publico else 'no'}. "
              f"Precio definido: {'sí' if pol.precio_definido else 'no'}.",
              "Solo puedes afirmar capacidades con uso PERMITIDO o CON_MATICES (con su matiz). Cita sus códigos.", ""]
    for c in pol.capacidades.values():
        if c.uso in ("PERMITIDO", "CON_MATICES"):
            extra = f" Matiz obligatorio: {c.matiz}" if c.uso == "CON_MATICES" and c.matiz else ""
            lineas.append(f"- {c.codigo} · {c.nombre}. Frase de referencia: {c.frase}{extra}")
    solo_demo = [f"{c.nombre} ({c.codigo})" for c in pol.capacidades.values() if c.uso == "SOLO_DEMO"]
    if solo_demo:
        lineas.append("\nSolo se muestra en una demostración guiada, no se promete en una pieza: " + "; ".join(solo_demo))
    lineas.append("\nNo menciones como disponible: " + "; ".join(
        f"{c.nombre} ({c.codigo})" for c in pol.capacidades.values() if c.uso == "NO_ANUNCIAR"))
    disponibles = plantillas.disponibles(cfg.raiz)
    if disponibles:
        lineas.append("\nPlantillas visuales disponibles: " + ", ".join(sorted(disponibles)))
    return {"politica": pol, "plantillas": disponibles}, "\n".join(lineas)
