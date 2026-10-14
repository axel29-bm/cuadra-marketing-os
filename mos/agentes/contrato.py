"""Contrato común de los agentes: qué reciben, qué entregan y cómo se comprueba que lo hicieron bien.

Un agente no es un proceso que corre solo: es una responsabilidad con un contrato. Lo puede ejecutar
código determinista, la IA que Didi tiene abierta (modo asistido), un modelo local o, si se autoriza,
un proveedor externo. El contrato es el mismo en los cuatro casos, y ninguna tarea se da por
completada sin pasar la validación de su salida y sus criterios de éxito.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# Un criterio recibe (entradas, resultado, contexto) y devuelve la lista de problemas encontrados.
Criterio = Callable[[dict, Any, dict], list[str]]


@dataclass(frozen=True)
class Agente:
    id: str
    nombre: str
    responsabilidad: str
    modo: str                       # DETERMINISTA o IA
    entradas: dict                  # esquema de entradas (ver validar_esquema)
    salida: Any                     # esquema de salida
    criterios: tuple[tuple[str, Criterio], ...] = ()
    requiere_aprobacion: bool = False
    prompt: str | None = None       # ruta relativa a prompts/
    max_intentos: int = 3
    max_subtareas: int = 10
    no_hace: tuple[str, ...] = ()   # límites explícitos del rol
    ejecutor: Callable[..., Any] | None = field(default=None, compare=False)


class ErrorContrato(ValueError):
    """La entrada o la salida no cumple el contrato del agente."""

    def __init__(self, problemas: list[str]):
        super().__init__("; ".join(problemas))
        self.problemas = problemas


_TIPOS = {str: "texto", int: "entero", bool: "sí/no", float: "número", dict: "objeto", list: "lista"}


def validar_esquema(valor: Any, esquema: Any, ruta: str = "$") -> list[str]:
    """Valida contra un esquema escrito con tipos de Python.

    - Un tipo (str, int, bool, dict, list) exige ese tipo. int no acepta bool.
    - Una lista con un elemento [x] exige una lista no vacía cuyos elementos cumplen x.
    - Un dict exige esas claves; una clave terminada en «?» es opcional.
    - Una tupla de cadenas exige uno de esos valores (enumeración).
    """
    problemas: list[str] = []
    if isinstance(esquema, tuple):
        if valor not in esquema:
            problemas.append(f"{ruta}: «{valor}» no es uno de {', '.join(map(str, esquema))}")
        return problemas
    if isinstance(esquema, type):
        if esquema is int and isinstance(valor, bool) or not isinstance(valor, esquema):
            problemas.append(f"{ruta}: se esperaba {_TIPOS.get(esquema, esquema.__name__)}")
        elif esquema is str and not valor.strip():
            problemas.append(f"{ruta}: está vacío")
        return problemas
    if isinstance(esquema, list):
        if not isinstance(valor, list):
            return [f"{ruta}: se esperaba una lista"]
        if not valor:
            return [f"{ruta}: la lista está vacía"]
        for i, elemento in enumerate(valor):
            problemas += validar_esquema(elemento, esquema[0], f"{ruta}[{i}]")
        return problemas
    if isinstance(esquema, dict):
        if not isinstance(valor, dict):
            return [f"{ruta}: se esperaba un objeto"]
        for clave, sub in esquema.items():
            opcional = clave.endswith("?")
            nombre = clave.rstrip("?")
            if nombre not in valor or valor[nombre] in (None, ""):
                if not opcional:
                    problemas.append(f"{ruta}.{nombre}: falta")
                continue
            problemas += validar_esquema(valor[nombre], sub, f"{ruta}.{nombre}")
        return problemas
    raise TypeError(f"Esquema no reconocido en {ruta}: {esquema!r}")


def describir_esquema(esquema: Any, sangria: int = 0) -> str:
    """Texto legible del esquema para incluirlo en los prompts."""
    pad = "  " * sangria
    if isinstance(esquema, tuple):
        return " | ".join(f'"{v}"' for v in esquema)
    if isinstance(esquema, type):
        return _TIPOS.get(esquema, esquema.__name__)
    if isinstance(esquema, list):
        return "lista de:\n" + pad + "  " + describir_esquema(esquema[0], sangria + 1)
    if isinstance(esquema, dict):
        lineas = ["{"]
        for clave, sub in esquema.items():
            opcional = " (opcional)" if clave.endswith("?") else ""
            lineas.append(f"{pad}  \"{clave.rstrip('?')}\": {describir_esquema(sub, sangria + 1)}{opcional}")
        lineas.append(pad + "}")
        return "\n".join(lineas)
    return repr(esquema)
