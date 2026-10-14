"""Rutinas: lo que se repite cada día y cada semana, en un comando que se puede programar en Windows.

Cada paso corre aunque otro falle; los fallos quedan en el informe y en la tabla de errores. Cada pasada queda
registrada en la tabla `rutina`, así el panel puede avisar si la tarea programada dejó de correr. Nada aquí
publica, envía mensajes ni usa IA externa: los informes salen de los datos de la base.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from . import contenido, db, leads, metricas, util
from .config import Config

DIAS_ALERTA = {"DIARIA": 2, "SEMANAL": 8}   # pasado esto sin una rutina terminada, el panel avisa


@dataclass
class Informe:
    tipo: str
    fecha: str
    ruta: Path
    estado: str
    pasos: dict[str, str] = field(default_factory=dict)


def _empezar(cx: sqlite3.Connection, tipo: str, fecha: str) -> int:
    with db.transaccion(cx):
        return cx.execute("INSERT INTO rutina (tipo, fecha, iniciada_en) VALUES (?,?,?)",
                          (tipo, fecha, util.ahora_utc())).lastrowid


def _terminar(cx: sqlite3.Connection, rid: int, estado: str, informe: str, pasos: dict) -> None:
    with db.transaccion(cx):
        cx.execute("UPDATE rutina SET terminada_en = ?, estado = ?, informe = ?, detalle = ? WHERE id = ?",
                   (util.ahora_utc(), estado, informe, util.a_json(pasos), rid))


def _paso(cx: sqlite3.Connection, pasos: dict, nombre: str, funcion: Callable[[], str]) -> str:
    """Corre un paso; si falla, lo anota y sigue con los demás."""
    try:
        pasos[nombre] = "OK"
        return funcion()
    except Exception as e:  # noqa: BLE001 · un paso roto no puede tumbar la rutina entera
        pasos[nombre] = f"FALLO: {type(e).__name__}: {e}"
        db.registrar_error(cx, "rutina", "PASO_" + nombre.upper(), f"{type(e).__name__}: {e}")
        return f"**No se pudo completar:** {type(e).__name__}: {e}\n"


def _tabla(columnas: list[str], filas: list[list]) -> str:
    if not filas:
        return ""
    lineas = ["| " + " | ".join(columnas) + " |", "|" + " --- |" * len(columnas)]
    for f in filas:
        lineas.append("| " + " | ".join(str(c if c not in (None, "") else "—").replace("|", "/").replace("\n", " ")
                                        for c in f) + " |")
    return "\n".join(lineas) + "\n"


def _nombre_corto(nombre: str, uid: str) -> str:
    """Nombre de pila e inicial: el informe es un archivo y no lleva datos de contacto."""
    partes = nombre.split()
    if not partes:
        return f"(sin nombre) · {uid[:8]}"
    corto = partes[0] + (f" {partes[1][0]}." if len(partes) > 1 else "")
    return f"{corto} · {uid[:8]}"


# ---------------------------------------------------------------------------------------------- diaria

def pendientes_del_dia(cx: sqlite3.Connection, hoy: str) -> str:
    """Lo mismo que muestra la página «Hoy» del panel, en texto."""
    contar = lambda sql, *a: cx.execute(sql, a).fetchone()[0]  # noqa: E731
    cifras = [
        ("Piezas para aprobar", contar("SELECT COUNT(*) FROM pieza WHERE estado = 'LISTA_PARA_APROBAR'")),
        ("Piezas frenadas por el auditor", contar("SELECT COUNT(*) FROM pieza WHERE estado = 'CORRECCIONES'")),
        ("Tareas de agentes para revisar", contar("SELECT COUNT(*) FROM tarea WHERE estado = 'REQUIERE_APROBACION'")),
        ("Publicaciones para hoy o atrasadas", contar(
            "SELECT COUNT(*) FROM publicacion WHERE estado IN ('PAQUETE_LISTO','PROGRAMADA') AND fecha_prevista <= ?", hoy)),
        ("Publicaciones fallidas", contar("SELECT COUNT(*) FROM publicacion WHERE estado = 'FALLIDA'")),
        ("Seguimientos de interesados", len(leads.seguimientos(cx, hoy))),
        ("Novedades del radar por verificar", contar("SELECT COUNT(*) FROM radar_item WHERE estado_verificacion = 'SIN_VERIFICAR'")),
        ("Errores sin resolver", contar("SELECT COUNT(*) FROM registro_error WHERE resuelto = 0")),
    ]
    texto = _tabla(["Qué", "Cuántos"], [[t, n] for t, n in cifras])
    manana = (date.fromisoformat(hoy) + timedelta(days=2)).isoformat()
    proximas = contenido.calendario(cx, hoy, manana)
    if proximas:
        texto += "\n**Piezas de hoy a pasado mañana**\n\n" + _tabla(
            ["Fecha", "Pieza", "Canal", "Título", "Estado"],
            [[p["fecha_prevista"], p["codigo"], p["canal"], p["titulo"], p["estado"].lower().replace("_", " ")] for p in proximas])
    segs = leads.seguimientos(cx, hoy)
    if segs:
        texto += "\n**Seguimientos** (los datos de contacto, en el panel)\n\n" + _tabla(
            ["Para", "Quién", "Etapa", "Próxima acción"],
            [[s["seguimiento_en"], _nombre_corto(s["nombre"], s["uid"]), s["estado"].lower(), s["proxima_accion"]] for s in segs])
    return texto


def diaria(cx: sqlite3.Connection, cfg: Config, *, leer_radar: bool = True, lector: Callable | None = None) -> Informe:
    """Respaldo verificado, lectura del radar y lo pendiente del día, en un informe Markdown."""
    hoy = util.hoy_lima().isoformat()
    rid = _empezar(cx, "DIARIA", hoy)
    pasos: dict[str, str] = {}
    secciones = []

    def respaldo() -> str:
        ruta = db.respaldar(cx, cfg.respaldos)
        return f"Copia verificada: `{ruta.relative_to(cfg.espacio)}`. Se conservan las 14 más recientes.\n"

    def leer() -> str:
        from . import radar_lector
        resultados = (lector or radar_lector.leer_fuentes)(cx)
        filas = [[r.fuente, radar_lector.ESTADOS_TEXTO.get(r.estado, r.estado), r.nuevas or "", r.detalle]
                 for r in resultados]
        nuevas = sum(r.nuevas for r in resultados)
        errores = [r for r in resultados if r.estado == "ERROR"]
        if errores:
            pasos["radar"] = f"CON_FALLOS: {len(errores)} fuente(s) con error"
        cabeza = (f"{nuevas} novedad(es) nueva(s), sin verificar: revísalas en el panel, sección Radar.\n\n" if nuevas
                  else "Sin novedades nuevas.\n\n")
        return cabeza + (_tabla(["Fuente", "Resultado", "Nuevas", "Detalle"], filas) or "No hay fuentes automáticas activas.\n")

    secciones.append(("Copia de seguridad", _paso(cx, pasos, "respaldo", respaldo)))
    if leer_radar:
        secciones.append(("Radar de fuentes oficiales", _paso(cx, pasos, "radar", leer)))
    else:
        pasos["radar"] = "OMITIDO"
    secciones.append(("Lo que espera por ti", _paso(cx, pasos, "pendientes", lambda: pendientes_del_dia(cx, hoy))))
    return _cerrar(cx, cfg, rid, "DIARIA", hoy, "Rutina diaria", secciones, pasos)


def _cerrar(cx, cfg, rid, tipo, fecha, titulo, secciones, pasos) -> Informe:
    estado = "OK" if all(v in ("OK", "OMITIDO") for v in pasos.values()) else "CON_FALLOS"
    carpeta = cfg.salidas / "rutinas"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{tipo.lower()}-{fecha}.md"
    cuerpo = [f"# {titulo} · {fecha}", "",
              f"Generado el {util.ahora_utc()} (UTC) en tu PC. "
              + ("Todo terminó bien." if estado == "OK" else "Algún paso falló: está marcado abajo y en la lista de errores."), ""]
    for nombre, texto in secciones:
        cuerpo += [f"## {nombre}", "", texto.rstrip(), ""]
    ruta.write_text("\n".join(cuerpo), encoding="utf-8")
    _terminar(cx, rid, estado, str(ruta.relative_to(cfg.espacio)), pasos)
    return Informe(tipo, fecha, ruta, estado, pasos)


# --------------------------------------------------------------------------------------------- semanal

def semanal(cx: sqlite3.Connection, cfg: Config, *, hasta: date | None = None) -> Informe:
    """Resumen del director: qué pasó en los últimos 7 días y qué toca la semana que viene. Sin IA."""
    hasta = hasta or util.hoy_lima()
    desde = hasta - timedelta(days=6)
    d, h = desde.isoformat(), hasta.isoformat()
    rid = _empezar(cx, "SEMANAL", h)
    pasos: dict[str, str] = {}
    secciones = [
        ("Publicaciones", _paso(cx, pasos, "publicaciones", lambda: _publicaciones(cx, d, h))),
        ("Métricas", _paso(cx, pasos, "metricas", lambda: _metricas(cx, d, h))),
        ("Interesados", _paso(cx, pasos, "leads", lambda: _leads(cx, d, h))),
        ("Producción y aprobaciones", _paso(cx, pasos, "piezas", lambda: _piezas(cx, d, h))),
        ("Radar", _paso(cx, pasos, "radar", lambda: _radar(cx, d, h))),
        ("Rutinas y errores", _paso(cx, pasos, "salud", lambda: _salud(cx, d, h))),
        ("La semana que viene", _paso(cx, pasos, "proxima", lambda: _proxima(cx, hasta))),
    ]
    return _cerrar(cx, cfg, rid, "SEMANAL", h, f"Resumen semanal del {desde:%d/%m} al {hasta:%d/%m/%Y}", secciones, pasos)


def _publicaciones(cx: sqlite3.Connection, d: str, h: str) -> str:
    filas = cx.execute("""SELECT canal, COUNT(*) AS n FROM publicacion WHERE estado = 'PUBLICADA'
                          AND substr(publicada_en, 1, 10) BETWEEN ? AND ? GROUP BY canal ORDER BY canal""", (d, h)).fetchall()
    fallidas = cx.execute("SELECT COUNT(*) FROM publicacion WHERE estado = 'FALLIDA' AND substr(actualizado_en, 1, 10) BETWEEN ? AND ?",
                          (d, h)).fetchone()[0]
    sin_confirmar = cx.execute("""SELECT COUNT(*) FROM publicacion WHERE estado IN ('PAQUETE_LISTO','PROGRAMADA')
                                  AND fecha_prevista < ?""", (h,)).fetchone()[0]
    texto = (_tabla(["Canal", "Publicadas con prueba"], [[f["canal"], f["n"]] for f in filas])
             or "Ninguna publicación confirmada con su enlace esta semana.\n")
    if sin_confirmar:
        texto += f"\n{sin_confirmar} publicación(es) con fecha pasada siguen sin confirmar: si salieron, registra su enlace.\n"
    if fallidas:
        texto += f"\n{fallidas} publicación(es) fallaron esta semana.\n"
    return texto


def _metricas(cx: sqlite3.Connection, d: str, h: str) -> str:
    r = metricas.resumen(cx, d, h)
    if r["sin_datos"]:
        return "Sin métricas registradas esta semana. Anota las de cada publicación (ver `docs/OPERACION-DIARIA.md`).\n"
    texto = ""
    for clave, titulo in (("medido", "Medido (lo que dice cada red)"), ("estimado", "Estimado (no es un dato medido)")):
        filas = [[canal, nombre, valor] for canal, valores in sorted(r[clave].items()) for nombre, valor in sorted(valores.items())]
        if filas:
            texto += f"**{titulo}**\n\n" + _tabla(["Canal", "Métrica", "Total"], filas) + "\n"
    recs = metricas.recomendaciones(cx, d, h)
    texto += "**Qué hacer con esto**\n\n" + "\n".join(
        f"- {x['decision'].lower()}{' ' + x['pieza'] if x.get('pieza') else ''}: {x['motivo']}" for x in recs) + "\n"
    return texto


def _leads(cx: sqlite3.Connection, d: str, h: str) -> str:
    nuevos = cx.execute("""SELECT fuente, COUNT(*) AS n, SUM(consentimiento_publicidad) AS pub FROM lead
                           WHERE substr(ingreso_en, 1, 10) BETWEEN ? AND ? GROUP BY fuente ORDER BY n DESC""", (d, h)).fetchall()
    texto = (_tabla(["Por dónde llegaron", "Nuevos", "Aceptaron novedades"], [[f["fuente"], f["n"], f["pub"] or 0] for f in nuevos])
             or "Ningún interesado nuevo esta semana.\n")
    embudo = {e: n for e, n in leads.embudo(cx).items() if n}
    if embudo:
        texto += "\n**Embudo completo hoy**\n\n" + _tabla(["Etapa", "Personas"], [[e.lower().replace("_", " "), n] for e, n in embudo.items()])
    derechos = cx.execute("""SELECT accion, COUNT(*) FROM auditoria WHERE entidad = 'lead' AND accion IN ('BAJA','SUPRIMIR','ACCESO')
                             AND substr(en, 1, 10) BETWEEN ? AND ? GROUP BY accion""", (d, h)).fetchall()
    if derechos:
        texto += "\n**Derechos atendidos:** " + ", ".join(f"{a.lower()} {n}" for a, n in derechos) + ".\n"
    return texto


def _piezas(cx: sqlite3.Connection, d: str, h: str) -> str:
    decisiones = dict(cx.execute("""SELECT decision, COUNT(*) FROM aprobacion WHERE substr(decidido_en, 1, 10) BETWEEN ? AND ?
                                     GROUP BY decision""", (d, h)).fetchall())
    estados = dict(cx.execute("SELECT estado, COUNT(*) FROM pieza GROUP BY estado").fetchall())
    filas = [["Aprobadas esta semana", decisiones.get("APROBADA", 0)],
             ["Devueltas con correcciones esta semana", decisiones.get("CORRECCIONES", 0) + decisiones.get("RECHAZADA", 0)],
             ["Esperan tu aprobación", estados.get("LISTA_PARA_APROBAR", 0)],
             ["Frenadas por el auditor", estados.get("CORRECCIONES", 0)]]
    return _tabla(["Piezas", "Cuántas"], filas)


def _radar(cx: sqlite3.Connection, d: str, h: str) -> str:
    detectadas = cx.execute("SELECT COUNT(*) FROM radar_item WHERE substr(detectado_en, 1, 10) BETWEEN ? AND ?", (d, h)).fetchone()[0]
    verificadas = cx.execute("SELECT COUNT(*) FROM radar_item WHERE substr(verificado_en, 1, 10) BETWEEN ? AND ?", (d, h)).fetchone()[0]
    pendientes = cx.execute("SELECT COUNT(*) FROM radar_item WHERE estado_verificacion = 'SIN_VERIFICAR'").fetchone()[0]
    caidas = cx.execute("SELECT slug, ultimo_error FROM fuente WHERE activa = 1 AND ultimo_error IS NOT NULL ORDER BY slug").fetchall()
    texto = f"{detectadas} detectada(s) y {verificadas} verificada(s) esta semana; {pendientes} esperan que alguien lea la fuente.\n"
    if caidas:
        texto += "\n**Fuentes con problemas**\n\n" + _tabla(["Fuente", "Último error"], [[f["slug"], f["ultimo_error"]] for f in caidas])
    return texto


def _salud(cx: sqlite3.Connection, d: str, h: str) -> str:
    rutinas = cx.execute("""SELECT estado, COUNT(*) FROM rutina WHERE tipo = 'DIARIA' AND fecha BETWEEN ? AND ?
                            GROUP BY estado""", (d, h)).fetchall()
    conteo = dict(rutinas)
    dias = cx.execute("SELECT COUNT(DISTINCT fecha) FROM rutina WHERE tipo = 'DIARIA' AND estado <> 'EN_CURSO' AND fecha BETWEEN ? AND ?",
                      (d, h)).fetchone()[0]
    errores = cx.execute("SELECT modulo, COUNT(*) FROM registro_error WHERE resuelto = 0 GROUP BY modulo ORDER BY 2 DESC").fetchall()
    texto = (f"La rutina diaria corrió {dias} de 7 días ({conteo.get('OK', 0)} sin fallos, {conteo.get('CON_FALLOS', 0)} con fallos).\n")
    if dias < 7:
        texto += "Si la programaste y faltan días, revisa el Programador de tareas de Windows (`python -m mos rutina programar`).\n"
    texto += ("\n**Errores sin resolver por módulo**\n\n" + _tabla(["Módulo", "Errores"], [list(e) for e in errores])
              if errores else "\nNo hay errores sin resolver.\n")
    return texto


def _proxima(cx: sqlite3.Connection, hasta: date) -> str:
    d = (hasta + timedelta(days=1)).isoformat()
    h = (hasta + timedelta(days=7)).isoformat()
    piezas = contenido.calendario(cx, d, h)
    if not piezas:
        return "No hay piezas con fecha para la semana que viene.\n"
    sin_aprobar = [p for p in piezas if p["estado"] not in ("APROBADA", "PROGRAMADA", "PUBLICADA")]
    texto = _tabla(["Fecha", "Pieza", "Canal", "Título", "Estado"],
                   [[p["fecha_prevista"], p["codigo"], p["canal"], p["titulo"], p["estado"].lower().replace("_", " ")] for p in piezas])
    if sin_aprobar:
        texto += f"\n{len(sin_aprobar)} de {len(piezas)} todavía no están aprobadas.\n"
    return texto


# ----------------------------------------------------------------------------------------------- salud

def ultimas(cx: sqlite3.Connection) -> dict[str, sqlite3.Row | None]:
    return {t: cx.execute("""SELECT * FROM rutina WHERE tipo = ? AND estado <> 'EN_CURSO'
                             ORDER BY iniciada_en DESC LIMIT 1""", (t,)).fetchone() for t in DIAS_ALERTA}


def alertas(cx: sqlite3.Connection, hoy: date | None = None) -> list[str]:
    """Avisos para el panel: una rutina que se usó y dejó de correr, o que terminó con fallos."""
    hoy = hoy or util.hoy_lima()
    salida = []
    nombres = {"DIARIA": "diaria", "SEMANAL": "semanal"}
    for tipo, fila in ultimas(cx).items():
        if fila is None:
            continue
        dias = (hoy - date.fromisoformat(fila["fecha"])).days
        if dias > DIAS_ALERTA[tipo]:
            salida.append(f"La rutina {nombres[tipo]} no corre desde hace {dias} días (última: {fila['fecha']}).")
        elif fila["estado"] == "CON_FALLOS":
            fallos = [k for k, v in json.loads(fila["detalle"] or "{}").items() if v not in ("OK", "OMITIDO")]
            salida.append(f"La última rutina {nombres[tipo]} ({fila['fecha']}) tuvo fallos en: {', '.join(fallos)}.")
    return salida


def preparar_programacion(cfg: Config) -> list[str]:
    """Escribe un .cmd por rutina en el espacio y devuelve los comandos de schtasks para crearlas y quitarlas.

    No crea las tareas: los comandos los copia Didi en su consola si quiere. Un .cmd evita el anidado de comillas
    de schtasks y deja escrito qué se ejecuta exactamente.
    """
    lineas = []
    for tipo, cuando in (("diaria", "/SC DAILY /ST 08:00"), ("semanal", "/SC WEEKLY /D SUN /ST 18:00")):
        script = cfg.espacio / f"rutina-{tipo}.cmd"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("\r\n".join([
            "@echo off",
            "chcp 65001 >nul",
            f"rem Marketing OS: rutina {tipo}. Creado por: python -m mos rutina programar",
            f'cd /d "{cfg.raiz}"',
            f'set "MOS_ESPACIO={cfg.espacio}"',
            f'"{sys.executable}" -m mos rutina {tipo} >> "{cfg.espacio / "rutinas.log"}" 2>&1',
            ""]), encoding="utf-8")
        nombre = f"Marketing OS {tipo}"
        lineas.append(f'schtasks /Create /TN "{nombre}" {cuando} /F /TR "\\"{script}\\""')
    lineas += ['schtasks /Delete /TN "Marketing OS diaria" /F', 'schtasks /Delete /TN "Marketing OS semanal" /F']
    return lineas
