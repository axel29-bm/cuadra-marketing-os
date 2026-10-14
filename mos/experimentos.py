"""Experimentos: se escriben en campanas/<slug>/experimentos.toml y se calculan solo con métricas medidas.

Un experimento compara dos grupos de piezas con una tasa (suma de numeradores ÷ suma del denominador) y un umbral.
El sistema dice qué grupo quedó por encima y con cuántos casos; la decisión (CONTINUAR, MODIFICAR, DETENER o
INVESTIGAR) la toma Didi al cerrarlo. Con pocos casos todo resultado es un indicio y así se informa.
"""

from __future__ import annotations

import sqlite3
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import campanas, db, metricas, util

DECISIONES = ("CONTINUAR", "MODIFICAR", "DETENER", "INVESTIGAR")
CASOS_FIRMES = 30          # por debajo, el resultado es provisional


class ErrorExperimento(ValueError):
    pass


@dataclass
class Grupo:
    nombre: str
    piezas: list[str]
    publicaciones: int = 0
    numerador: int = 0
    denominador: int = 0
    faltan: list[str] = field(default_factory=list)      # piezas sin publicación confirmada o sin el denominador

    @property
    def tasa_bp(self) -> int | None:
        return round(10000 * self.numerador / self.denominador) if self.denominador else None


@dataclass
class Resultado:
    codigo: str
    grupos: dict[str, Grupo]
    razon: float | None
    lectura: str
    provisional: bool


def leer(carpeta: Path) -> list[dict]:
    ruta = carpeta / "experimentos.toml"
    if not ruta.exists():
        return []
    try:
        datos = tomllib.loads(ruta.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ErrorExperimento(f"{ruta} tiene un error de escritura: {e}") from None
    salida = []
    for x in datos.get("experimento", []):
        for campo in ("codigo", "hipotesis", "cambio", "variable"):
            if not x.get(campo):
                raise ErrorExperimento(f"Al experimento {x.get('codigo', '?')} le falta «{campo}».")
        if x.get("tipo", "MANUAL") == "PIEZAS":
            m = x.get("metrica") or {}
            if not m.get("numerador") or not m.get("denominador"):
                raise ErrorExperimento(f"{x['codigo']}: un experimento de piezas necesita metrica.numerador y metrica.denominador.")
            for n in [*m["numerador"], m["denominador"]]:
                if n not in metricas.NOMBRES:
                    raise ErrorExperimento(f"{x['codigo']}: «{n}» no es una métrica del sistema.")
            if set((x.get("grupos") or {}).keys()) != {"A", "B"}:
                raise ErrorExperimento(f"{x['codigo']}: hacen falta exactamente dos grupos, A y B.")
        salida.append(x)
    return salida


def cargar(cx: sqlite3.Connection, carpeta: Path, por: str = "Didi") -> tuple[int, int]:
    """Crea los experimentos nuevos y actualiza la definición de los existentes. Nunca toca estado, resultado ni decisión."""
    slug = campanas.leer(carpeta)["campana"]["slug"]
    fila = cx.execute("SELECT id FROM campana WHERE slug = ?", (slug,)).fetchone()
    if fila is None:
        raise ErrorExperimento(f"La campaña «{slug}» no está en la base. Cárgala primero: python -m mos campana cargar {carpeta}")
    nuevos = actualizados = 0
    with db.transaccion(cx):
        for x in leer(carpeta):
            definicion = {k: x[k] for k in ("titulo", "tipo", "metrica", "grupos", "nombres", "umbral", "condicion") if k in x}
            definicion["campana"] = slug
            existe = cx.execute("SELECT id FROM experimento WHERE codigo = ?", (x["codigo"],)).fetchone()
            valores = (fila["id"], x["hipotesis"], x["cambio"], x["variable"], _texto_metrica(x), x.get("inicio"), x.get("fin"),
                       util.a_json(definicion))
            if existe:
                cx.execute("""UPDATE experimento SET campana_id = ?, hipotesis = ?, cambio = ?, variable = ?, metrica = ?,
                                inicio = ?, fin = ?, definicion = ? WHERE id = ?""", (*valores, existe["id"]))
                actualizados += 1
            else:
                cur = cx.execute("""INSERT INTO experimento (campana_id, hipotesis, cambio, variable, metrica, inicio, fin,
                                      definicion, codigo, limitaciones) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                 (*valores, x["codigo"], x.get("limitaciones", "")))
                db.auditar(cx, por, "experimento", cur.lastrowid, "CREAR", {"codigo": x["codigo"]})
                nuevos += 1
    return nuevos, actualizados


def _texto_metrica(x: dict) -> str:
    m = x.get("metrica")
    if not m:
        return "Se mide fuera de las publicaciones (ver la definición)"
    return f"({' + '.join(m['numerador'])}) ÷ {m['denominador']}, solo medido"


def obtener(cx: sqlite3.Connection, codigo: str) -> sqlite3.Row:
    fila = cx.execute("SELECT * FROM experimento WHERE codigo = ?", (codigo,)).fetchone()
    if fila is None:
        raise ErrorExperimento(f"No existe el experimento {codigo}.")
    return fila


def listar(cx: sqlite3.Connection) -> list[sqlite3.Row]:
    return cx.execute("SELECT * FROM experimento ORDER BY codigo").fetchall()


def _ultimas_medidas(cx: sqlite3.Connection, pieza_id: int) -> list[dict[str, int]]:
    """Por cada publicación confirmada de la pieza, el último valor medido de cada métrica."""
    pubs = cx.execute("SELECT id FROM publicacion WHERE pieza_id = ? AND estado = 'PUBLICADA'", (pieza_id,)).fetchall()
    salida = []
    for p in pubs:
        valores = {}
        for f in cx.execute("""SELECT nombre, valor FROM metrica WHERE publicacion_id = ? AND naturaleza = 'MEDIDA'
                               ORDER BY fecha, id""", (p["id"],)):
            valores[f["nombre"]] = f["valor"]    # el último por fecha queda
        salida.append(valores)
    return salida


def calcular(cx: sqlite3.Connection, codigo: str) -> Resultado:
    exp = obtener(cx, codigo)
    d = util.de_json(exp["definicion"], {})
    if d.get("tipo") != "PIEZAS":
        return Resultado(codigo, {}, None, "Se mide fuera de las publicaciones: el resultado se anota al cerrarlo.", True)
    piezas = campanas.piezas_de(cx, d["campana"])
    num, den = d["metrica"]["numerador"], d["metrica"]["denominador"]
    grupos = {}
    for clave_grupo in ("A", "B"):
        g = Grupo(d.get("nombres", {}).get(clave_grupo, clave_grupo), list(d["grupos"][clave_grupo]))
        for clave in g.piezas:
            fila = piezas.get(clave)
            medidas = _ultimas_medidas(cx, fila["id"]) if fila else []
            con_dato = [m for m in medidas if m.get(den)]
            if not con_dato:
                g.faltan.append(clave)
            for m in con_dato:
                g.publicaciones += 1
                g.denominador += m[den]
                g.numerador += sum(m.get(n, 0) for n in num)
        grupos[clave_grupo] = g
    a, b = grupos["A"], grupos["B"]
    provisional = min(a.publicaciones, b.publicaciones) < CASOS_FIRMES
    umbral = float(d.get("umbral", 1.5))
    if not a.publicaciones or not b.publicaciones:
        vacio = [g.nombre for g in (a, b) if not g.publicaciones]
        return Resultado(codigo, grupos, None, f"Sin datos medidos todavía en: {', '.join(vacio)}.", True)
    if not b.numerador:
        razon = None
        lectura = (f"«{b.nombre}» no tiene ningún caso en el numerador; «{a.nombre}» sí."
                   if a.numerador else "Ningún grupo tiene casos en el numerador todavía.")
    else:
        razon = (a.numerador / a.denominador) / (b.numerador / b.denominador)
        if razon >= umbral:
            lectura = f"«{a.nombre}» queda {razon:.2f} veces por encima de «{b.nombre}» (umbral {umbral:g})."
        elif razon <= 1 / umbral:
            lectura = f"«{b.nombre}» queda {1 / razon:.2f} veces por encima de «{a.nombre}» (umbral {umbral:g})."
        else:
            lectura = f"La diferencia ({razon:.2f} veces) no llega al umbral de {umbral:g}: no hay ganador."
    if provisional:
        lectura += f" Provisional: menos de {CASOS_FIRMES} publicaciones por grupo, es un indicio."
    return Resultado(codigo, grupos, razon, lectura, provisional)


def _cambiar_estado(cx: sqlite3.Connection, codigo: str, estado: str, desde: tuple[str, ...], por: str, **campos) -> None:
    with db.transaccion(cx):
        exp = obtener(cx, codigo)
        if exp["estado"] not in desde:
            raise ErrorExperimento(f"{codigo} está {exp['estado'].lower().replace('_', ' ')}: no se puede pasar a {estado.lower()}.")
        asignar = ", ".join(f"{k} = ?" for k in campos)
        cx.execute(f"UPDATE experimento SET estado = ?{', ' + asignar if asignar else ''} WHERE id = ?",
                   (estado, *campos.values(), exp["id"]))
        db.auditar(cx, por, "experimento", exp["id"], estado, {k: v for k, v in campos.items() if k != "definicion"})


def empezar(cx: sqlite3.Connection, codigo: str, por: str = "Didi") -> None:
    _cambiar_estado(cx, codigo, "EN_CURSO", ("PLANIFICADO",), por)


def cerrar(cx: sqlite3.Connection, codigo: str, decision: str, resultado: str, por: str = "Didi",
           limitaciones: str | None = None) -> None:
    if decision not in DECISIONES:
        raise ErrorExperimento(f"Decisión no válida: {decision}. Usa una de: {', '.join(DECISIONES)}.")
    if not resultado.strip():
        raise ErrorExperimento("Al cerrar un experimento hay que escribir el resultado (solo lo medido).")
    campos = {"decision": decision, "resultado": resultado.strip(), "decidido_en": util.ahora_utc()}
    if limitaciones:
        campos["limitaciones"] = limitaciones
    _cambiar_estado(cx, codigo, "TERMINADO", ("PLANIFICADO", "EN_CURSO"), por, **campos)


def cancelar(cx: sqlite3.Connection, codigo: str, motivo: str, por: str = "Didi") -> None:
    if not motivo.strip():
        raise ErrorExperimento("Al cancelar un experimento hay que decir por qué.")
    _cambiar_estado(cx, codigo, "CANCELADO", ("PLANIFICADO", "EN_CURSO"), por,
                    resultado=f"Cancelado: {motivo.strip()}", decidido_en=util.ahora_utc())
