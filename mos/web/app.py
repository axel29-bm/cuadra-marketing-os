"""Panel web local del Marketing OS. Solo biblioteca estándar; escucha únicamente en 127.0.0.1.

Seguridad: rechaza peticiones cuyo Host no sea local (evita ataques de DNS rebinding) y exige un token
por proceso en cada formulario (una web ajena no puede enviar formularios a tu panel). Los contactos de
los leads se muestran enmascarados.
"""

from __future__ import annotations

import calendar
import html
import json
import mimetypes
import re
import secrets
import sqlite3
import traceback
import webbrowser
from datetime import date, timedelta
from importlib import resources
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from wsgiref.simple_server import WSGIRequestHandler, make_server

from .. import __version__, config, contenido, db, leads, metricas, radar, util
from ..agentes import motor
from ..agentes.contrato import ErrorContrato
from ..agentes.registro import AGENTES
from ..calidad import auditor as aud
from ..contexto import de_producto, producto_unico
from ..fabrica import plantillas as fab_plantillas

TOKEN = secrets.token_urlsafe(24)
HOSTS_LOCALES = {"127.0.0.1", "localhost"}
ERRORES_DE_NEGOCIO = (contenido.ErrorContenido, leads.ErrorLead, radar.ErrorRadar, metricas.ErrorMetrica,
                      motor.ErrorTarea, ErrorContrato, ValueError, KeyError)


# --------------------------------------------------------------------------------------------- utilidades

def e(valor) -> str:
    return html.escape("" if valor is None else str(valor))


def chip(texto: str | None, color: str | None = None) -> str:
    if not texto:
        return ""
    colores = {
        "APROBADO": "verde", "APROBADA": "verde", "COMPLETADA": "verde", "PUBLICADA": "verde", "VERIFICADA": "verde",
        "PERMITIDO": "verde", "IMPLEMENTADO_VERIFICADO": "verde", "ADOPTAR": "verde", "BETA": "verde", "GANADO": "verde",
        "CON_OBSERVACIONES": "ambar", "CON_MATICES": "ambar", "LISTA_PARA_APROBAR": "lima", "REQUIERE_APROBACION": "lima",
        "PREPARADA": "azul", "PROGRAMADA": "azul", "PAQUETE_LISTO": "azul", "EN_CURSO": "azul", "PROBAR": "azul",
        "SOLO_DEMO": "azul", "IMPLEMENTADO_PARCIAL": "ambar", "EN_REVISION": "azul", "CORRECCIONES": "ambar",
        "RECHAZADO": "rojo", "RECHAZADA": "rojo", "FALLIDA": "rojo", "NO_ANUNCIAR": "rojo", "DESCARTAR": "gris",
        "RUMOR": "rojo", "NO_CONTACTAR": "rojo", "PERDIDO": "gris", "EN_DESARROLLO": "ambar", "PLANIFICADO": "gris",
        "SIN_EVIDENCIA": "rojo", "SIN_VERIFICAR": "ambar", "RESERVAR": "ambar", "PRELANZAMIENTO": "lima",
    }
    return f'<span class="chip {color or colores.get(texto, "gris")}">{e(texto.lower().replace("_", " "))}</span>'


def soles(centimos: int) -> str:
    return f"S/ {centimos / 100:,.2f}"


def enmascarar_email(email: str | None) -> str:
    if not email:
        return ""
    usuario, _, dominio = email.partition("@")
    return f"{usuario[:1]}***@{dominio}"


def enmascarar_telefono(tel: str | None) -> str:
    return f"{tel[:4]}*****{tel[-3:]}" if tel and len(tel) > 7 else ""


def campo(nombre: str, etiqueta: str, valor: str = "", tipo: str = "text", requerido: bool = False,
          clase: str = "", extra: str = "") -> str:
    req = " required" if requerido else ""
    if tipo == "textarea":
        control = f'<textarea name="{nombre}"{req}{extra}>{e(valor)}</textarea>'
    else:
        control = f'<input type="{tipo}" name="{nombre}" value="{e(valor)}"{req}{extra}>'
    return f'<label class="{clase}">{e(etiqueta)}{control}</label>'


def selector(nombre: str, etiqueta: str, opciones, valor: str = "", vacio: str | None = None, clase: str = "") -> str:
    ops = [f'<option value="">{e(vacio)}</option>'] if vacio is not None else []
    for o in opciones:
        v, t = (o, o) if isinstance(o, str) else o
        sel = " selected" if str(v) == str(valor) else ""
        ops.append(f'<option value="{e(v)}"{sel}>{e(t)}</option>')
    return f'<label class="{clase}">{e(etiqueta)}<select name="{nombre}">{"".join(ops)}</select></label>'


def check(nombre: str, etiqueta: str, marcado: bool = False) -> str:
    return f'<label class="check"><input type="checkbox" name="{nombre}" value="1"{" checked" if marcado else ""}> {e(etiqueta)}</label>'


def formulario(accion: str, cuerpo: str, boton: str = "Guardar", clase: str = "bloque", volver: str = "",
               clase_boton: str = "") -> str:
    oculto = f'<input type="hidden" name="_token" value="{TOKEN}"><input type="hidden" name="volver" value="{e(volver)}">'
    btn = f'<button class="{clase_boton}">{e(boton)}</button>'
    if clase == "linea":
        return f'<form class="linea" method="post" action="{e(accion)}">{oculto}{cuerpo}{btn}</form>'
    return f'<form class="{clase}" method="post" action="{e(accion)}">{oculto}{cuerpo}<div class="acciones">{btn}</div></form>'


def boton(accion: str, texto: str, volver: str = "", clase: str = "sec", **ocultos) -> str:
    extra = "".join(f'<input type="hidden" name="{e(k)}" value="{e(v)}">' for k, v in ocultos.items())
    return formulario(accion, extra, texto, clase="linea", volver=volver, clase_boton=clase)


def tabla(cabeceras: list[str], filas: list[list[str]], vacio: str = "Nada por aquí todavía.") -> str:
    if not filas:
        return f'<p class="vacio">{e(vacio)}</p>'
    cab = "".join(f"<th>{e(c)}</th>" for c in cabeceras)
    cuerpo = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in f) + "</tr>" for f in filas)
    return f"<table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table>"


def lista_codigos(texto: str) -> list[str]:
    return [c.strip().upper() for c in re.split(r"[,\s]+", texto or "") if c.strip()]


# ------------------------------------------------------------------------------------------- petición

class Redirigir(Exception):
    def __init__(self, url: str):
        self.url = url


class Peticion:
    def __init__(self, environ: dict, cfg: config.Config, cx: sqlite3.Connection):
        self.cfg, self.cx = cfg, cx
        self.metodo = environ["REQUEST_METHOD"]
        self.ruta = environ.get("PATH_INFO", "/") or "/"
        self._query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        self._form: dict[str, list[str]] = {}
        if self.metodo == "POST":
            largo = int(environ.get("CONTENT_LENGTH") or 0)
            if largo > 2_000_000:
                raise ValueError("El formulario es demasiado grande.")
            cuerpo = environ["wsgi.input"].read(largo).decode("utf-8")
            self._form = parse_qs(cuerpo, keep_blank_values=True)

    def q(self, clave: str, defecto: str = "") -> str:
        return self._query.get(clave, [defecto])[0]

    def f(self, clave: str, defecto: str = "") -> str:
        return self._form.get(clave, [defecto])[0].strip()

    def fi(self, clave: str) -> int | None:
        v = self.f(clave)
        return int(v) if v.lstrip("-").isdigit() else None

    def marcado(self, clave: str) -> bool:
        return self.f(clave) in ("1", "on", "si", "true")

    @property
    def volver(self) -> str:
        v = self.f("volver") or "/"
        return v if v.startswith("/") and not v.startswith("//") else "/"


def ir(destino: str, ok: str = "", error: str = "") -> Redirigir:
    partes = urlsplit(destino)
    q = parse_qs(partes.query)
    q.pop("ok", None)
    q.pop("error", None)
    if ok:
        q["ok"] = [ok]
    if error:
        q["error"] = [error]
    return Redirigir(partes.path + ("?" + urlencode(q, doseq=True) if q else ""))


RUTAS: list[tuple[str, re.Pattern, Callable]] = []


def ruta(metodo: str, patron: str):
    def deco(fn):
        RUTAS.append((metodo, re.compile("^" + patron + "$"), fn))
        return fn
    return deco


NAV = [
    ("Trabajo", [("/", "Hoy"), ("/aprobaciones", "Aprobaciones"), ("/calendario", "Calendario"), ("/tareas", "Tareas de agentes")]),
    ("Contenido", [("/ideas", "Ideas"), ("/campanas", "Campañas"), ("/piezas", "Biblioteca"), ("/publicaciones", "Publicaciones")]),
    ("Personas y datos", [("/leads", "Leads"), ("/metricas", "Métricas"), ("/radar", "Radar")]),
    ("Sistema", [("/productos", "Productos"), ("/herramientas", "Herramientas"), ("/errores", "Errores")]),
]


def pagina(req: Peticion, titulo: str, cuerpo: str, sub: str = "") -> str:
    nav = []
    for grupo, enlaces in NAV:
        nav.append(f'<div class="grupo">{e(grupo)}</div>')
        for href, texto in enlaces:
            activo = req.ruta == href or (href != "/" and req.ruta.startswith(href))
            nav.append(f'<a href="{href}" class="{"activo" if activo else ""}">{e(texto)}</a>')
    avisos = ""
    if req.q("ok"):
        avisos += f'<div class="aviso ok">{e(req.q("ok"))}</div>'
    if req.q("error"):
        avisos += f'<div class="aviso error">{e(req.q("error"))}</div>'
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(titulo)} · Marketing OS</title>
<link rel="stylesheet" href="/estilo.css"><link rel="icon" href="/marcas/cuadra/logo.svg"></head>
<body><div class="marco"><nav class="lateral"><a class="logo" href="/"><img src="/marcas/cuadra/logo.svg" alt="">Marketing OS</a>
{''.join(nav)}<div class="pie">Versión {e(__version__)} · modo de IA {e(req.cfg.modo_ia.lower())}<br>Solo en tu PC</div></nav>
<main>{avisos}<h1>{e(titulo)}</h1>{f'<p class="sub">{sub}</p>' if sub else ''}{cuerpo}</main></div></body></html>"""


# --------------------------------------------------------------------------------------------------- Hoy

@ruta("GET", "/")
def hoy(req: Peticion) -> str:
    cx = req.cx
    vencidas = motor.revisar_vencidas(cx)
    hoy_ = util.hoy_lima().isoformat()
    productos = cx.execute("SELECT * FROM producto ORDER BY slug").fetchall()
    tarjetas = []
    for p in productos:
        caps = dict(cx.execute("SELECT uso, COUNT(*) FROM capacidad WHERE producto_id = ? GROUP BY uso", (p["id"],)).fetchall())
        tarjetas.append(f"""<div class="tarjeta destacada"><h3><a href="/productos/{e(p['slug'])}">{e(p['nombre_provisional'])}</a></h3>
          {chip(p['etapa_comercial'])} {chip('sin precio' if not p['precio_definido'] else 'precio definido', 'gris')}
          <p>{caps.get('PERMITIDO', 0)} capacidades se pueden afirmar, {caps.get('CON_MATICES', 0)} con matices y
          {caps.get('NO_ANUNCIAR', 0)} no se anuncian.</p></div>""")
    mes = hoy_[:7]
    gasto = cx.execute("SELECT COALESCE(SUM(importe_c), 0) FROM gasto WHERE substr(fecha, 1, 7) = ?", (mes,)).fetchone()[0]
    contar = lambda sql, *a: cx.execute(sql, a).fetchone()[0]
    cifras = [
        ("/aprobaciones", "Piezas para aprobar", contar("SELECT COUNT(*) FROM pieza WHERE estado = 'LISTA_PARA_APROBAR'")),
        ("/aprobaciones", "Tareas para revisar", contar("SELECT COUNT(*) FROM tarea WHERE estado = 'REQUIERE_APROBACION'")),
        ("/tareas?estado=PREPARADA", "Tareas esperando respuesta de la IA", contar("SELECT COUNT(*) FROM tarea WHERE estado = 'PREPARADA'")),
        ("/publicaciones", "Publicaciones para hoy o atrasadas", contar(
            "SELECT COUNT(*) FROM publicacion WHERE estado IN ('PAQUETE_LISTO','PROGRAMADA') AND fecha_prevista <= ?", hoy_)),
        ("/leads", "Seguimientos de leads", len(leads.seguimientos(cx, hoy_))),
        ("/radar", "Novedades por verificar", contar("SELECT COUNT(*) FROM radar_item WHERE estado_verificacion = 'SIN_VERIFICAR'")),
        ("/errores", "Errores sin resolver", contar("SELECT COUNT(*) FROM registro_error WHERE resuelto = 0")),
    ]
    tarjetas_cifras = "".join(f'<a class="tarjeta" href="{h}"><div class="cifra">{n}</div>{e(t)}</a>' for h, t, n in cifras)
    proximas = contenido.calendario(cx, hoy_, (util.hoy_lima() + timedelta(days=7)).isoformat())
    filas = [[e(p["fecha_prevista"]), f'<a href="/piezas/{e(p["codigo"])}">{e(p["codigo"])}</a>', e(p["canal"]),
              e(p["titulo"]), chip(p["estado"])] for p in proximas]
    ideas = contenido.ideas_priorizadas(cx, limite=5)
    filas_ideas = [[f"<b>{i['puntuacion']}</b>", e(i["idea_central"]), e(i["canal"]), chip(i["etapa_embudo"], "gris")] for i in ideas]
    aviso_vencidas = f'<div class="aviso info">Se cerraron por vencimiento: {e(", ".join(vencidas))}.</div>' if vencidas else ""
    cuerpo = f"""{aviso_vencidas}<div class="tarjetas">{''.join(tarjetas)}
      <div class="tarjeta destacada"><h3>Gasto del mes</h3><div class="cifra">{soles(gasto)}</div>
      Nada se paga sin tu autorización.</div></div>
      <h2>Lo que te espera</h2><div class="tarjetas">{tarjetas_cifras}</div>
      <h2>Próximos 7 días</h2>{tabla(["Fecha", "Pieza", "Canal", "Título", "Estado"], filas, "No hay piezas con fecha esta semana.")}
      <h2>Mejores ideas sin producir</h2>{tabla(["Puntos", "Idea", "Canal", "Etapa"], filas_ideas, "El banco de ideas está vacío.")}"""
    return pagina(req, "Hoy", cuerpo, f"{util.hoy_lima().strftime('%d/%m/%Y')} · todo lo que necesita tu atención, en un solo lugar.")


# ------------------------------------------------------------------------------------------ Aprobaciones

@ruta("GET", "/aprobaciones")
def aprobaciones(req: Peticion) -> str:
    cx = req.cx
    piezas = cx.execute("""SELECT pz.*, (SELECT resultado FROM revision r WHERE r.pieza_id = pz.id AND r.version = pz.version_actual
                                          ORDER BY r.id DESC LIMIT 1) AS auditoria
                           FROM pieza pz WHERE pz.estado = 'LISTA_PARA_APROBAR' ORDER BY pz.fecha_prevista""").fetchall()
    filas = [[f'<a href="/piezas/{e(p["codigo"])}">{e(p["codigo"])}</a>', e(p["titulo"]), e(p["canal"]), e(p["fecha_prevista"]),
              chip(p["auditoria"]),
              boton(f"/piezas/{p['codigo']}/decidir", "Aprobar", "/aprobaciones", "lima", decision="APROBADA") + " " +
              f'<a class="boton sec" href="/piezas/{e(p["codigo"])}">Revisar</a>'] for p in piezas]
    tareas = cx.execute("SELECT * FROM tarea WHERE estado = 'REQUIERE_APROBACION' ORDER BY id").fetchall()
    filas_t = [[f'<a href="/tareas/{e(t["codigo"])}">{e(t["codigo"])}</a>', e(AGENTES[t["agente"]].nombre), e(t["objetivo"]),
                f'<a class="boton sec" href="/tareas/{e(t["codigo"])}">Revisar y aprobar</a>'] for t in tareas]
    cuerpo = f"""<h2>Piezas que pasaron el auditor</h2>{tabla(["Pieza", "Título", "Canal", "Fecha", "Auditor", ""], filas, "No hay piezas esperando tu aprobación.")}
      <h2>Resultados de agentes que necesitan tu visto bueno</h2>{tabla(["Tarea", "Agente", "Objetivo", ""], filas_t, "No hay tareas esperando aprobación.")}"""
    return pagina(req, "Aprobaciones", cuerpo, "Una aprobación vale para la versión exacta que ves. Si el texto cambia, se aprueba de nuevo.")


# --------------------------------------------------------------------------------------------- Calendario

@ruta("GET", "/calendario")
def vista_calendario(req: Peticion) -> str:
    hoy_ = util.hoy_lima()
    try:
        anio, mes = (int(x) for x in (req.q("mes") or hoy_.strftime("%Y-%m")).split("-"))
        date(anio, mes, 1)
    except ValueError:
        anio, mes = hoy_.year, hoy_.month
    semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(anio, mes)
    piezas = contenido.calendario(req.cx, semanas[0][0].isoformat(), semanas[-1][-1].isoformat())
    por_dia: dict[str, list] = {}
    for p in piezas:
        por_dia.setdefault(p["fecha_prevista"], []).append(p)
    celdas = [f'<div class="cab">{d}</div>' for d in ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")]
    for semana in semanas:
        for d in semana:
            clases = "dia" + (" fuera" if d.month != mes else "") + (" hoy" if d == hoy_ else "")
            items = "".join(f'<a class="pz" href="/piezas/{e(p["codigo"])}" title="{e(p["estado"])}">'
                            f'{e(p["canal"])} · {e(p["titulo"][:40])}</a>' for p in por_dia.get(d.isoformat(), []))
            celdas.append(f'<div class="{clases}"><div class="num">{d.day}</div>{items}</div>')
    previo = (date(anio, mes, 1) - timedelta(days=1)).strftime("%Y-%m")
    siguiente = (date(anio, mes, 28) + timedelta(days=7)).strftime("%Y-%m")
    nombre_mes = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre", "octubre",
                  "noviembre", "diciembre"][mes - 1]
    cuerpo = f"""<div class="acciones"><a class="boton sec" href="/calendario?mes={previo}">← Mes anterior</a>
      <a class="boton sec" href="/calendario">Hoy</a><a class="boton sec" href="/calendario?mes={siguiente}">Mes siguiente →</a></div>
      <div class="cal">{''.join(celdas)}</div>"""
    return pagina(req, f"Calendario de {nombre_mes} de {anio}", cuerpo, f"{len(piezas)} piezas con fecha en esta vista.")


# ------------------------------------------------------------------------------------------------ Tareas

@ruta("GET", "/tareas")
def lista_tareas(req: Peticion) -> str:
    estado = req.q("estado")
    sql, params = "SELECT * FROM tarea", []
    if estado:
        sql += " WHERE estado = ?"
        params.append(estado)
    tareas = req.cx.execute(sql + " ORDER BY id DESC LIMIT 200", params).fetchall()
    filas = [[f'<a href="/tareas/{e(t["codigo"])}">{e(t["codigo"])}</a>', chip(t["estado"]), e(AGENTES[t["agente"]].nombre),
              e(t["objetivo"]), e(t["modo"].lower()), e(t["intentos"])] for t in tareas]
    agentes_ia = [(a.id, a.nombre) for a in AGENTES.values()]
    form = formulario("/tareas", f"""<div class="campos">{selector("agente", "Agente", agentes_ia)}
        {campo("objetivo", "Objetivo", requerido=True)}
        {campo("entradas", "Entradas (JSON según el contrato del agente)", "{}", "textarea", clase="ancho")}
        {campo("restricciones", "Restricciones (una por línea)", "", "textarea", clase="ancho")}</div>""",
                      "Crear tarea", volver="/tareas")
    estados = ["", "PENDIENTE", "PREPARADA", "EN_CURSO", "REQUIERE_APROBACION", "COMPLETADA", "FALLIDA", "CANCELADA"]
    filtro = " ".join(f'<a class="chip {"lima" if s == estado else "gris"}" href="/tareas{"?estado=" + s if s else ""}">'
                      f'{e(s.lower().replace("_", " ") or "todas")}</a>' for s in estados)
    cuerpo = f"""<p>{filtro}</p>{tabla(["Tarea", "Estado", "Agente", "Objetivo", "Modo", "Intentos"], filas, "No hay tareas.")}
      <h2>Encargar una tarea</h2><p>El contrato de cada agente (sus entradas y su salida) está en <code>docs/ARQUITECTURA-AGENTES.md</code>.</p>{form}"""
    return pagina(req, "Tareas de agentes", cuerpo,
                  "En modo asistido, el sistema prepara el prompt; tú lo resuelves con tu IA y pegas aquí la respuesta.")


@ruta("POST", "/tareas")
def crear_tarea(req: Peticion):
    try:
        entradas = json.loads(req.f("entradas") or "{}")
    except json.JSONDecodeError as ex:
        raise ValueError(f"Las entradas no son JSON válido: {ex}") from ex
    restricciones = [r.strip() for r in req.f("restricciones").splitlines() if r.strip()]
    codigo = motor.crear(req.cx, req.f("agente"), req.f("objetivo"), entradas, restricciones=restricciones,
                         modo=req.cfg.modo_ia)
    raise ir(f"/tareas/{codigo}", ok=f"Tarea {codigo} creada.")


def _contexto_tarea(req: Peticion, t) -> tuple[dict, str]:
    producto = util.de_json(t["entradas"], {}).get("producto") or producto_unico(req.cfg)
    return de_producto(req.cfg, producto)


@ruta("GET", r"/tareas/(?P<codigo>T-\d+)")
def ver_tarea(req: Peticion, codigo: str) -> str:
    t = motor.obtener(req.cx, codigo)
    a = AGENTES[t["agente"]]
    prompt_ruta = req.cfg.tareas / codigo / "PROMPT.md"
    prompt = prompt_ruta.read_text(encoding="utf-8") if prompt_ruta.exists() else ""
    eventos = req.cx.execute("SELECT en, tipo, detalle FROM tarea_evento WHERE tarea_id = ? ORDER BY id", (t["id"],)).fetchall()
    errores = util.de_json(t["errores"], [])
    acciones = []
    volver = f"/tareas/{codigo}"
    if t["estado"] in ("PENDIENTE", "PREPARADA", "EN_CURSO"):
        acciones.append(boton(f"/tareas/{codigo}/ejecutar", "Preparar prompt" if t["modo"] == "ASISTIDO" else "Ejecutar", volver, ""))
    if t["estado"] == "REQUIERE_APROBACION":
        acciones.append(boton(f"/tareas/{codigo}/aprobar", "Aprobar resultado", volver, "lima"))
    if t["estado"] in motor.ACTIVOS:
        acciones.append(boton(f"/tareas/{codigo}/cancelar", "Cancelar tarea", volver, "peligro"))
    bloque_resultado = ""
    if t["estado"] in ("PREPARADA", "EN_CURSO", "PENDIENTE") and a.modo != "DETERMINISTA":
        bloque_resultado = "<h2>Pegar la respuesta de la IA</h2>" + formulario(
            f"/tareas/{codigo}/completar", campo("resultado", "Respuesta (solo el JSON)", "", "textarea", True, "ancho",
                                                 ' style="min-height:220px"'), "Validar y guardar", volver=volver)
    filas_err = "".join(f'<div class="hallazgo BLOQUEANTE"><b>Intento {e(x.get("intento", ""))}</b><br>' +
                        "<br>".join(e(p) for p in x["problemas"]) + "</div>" for x in errores)
    cuerpo = f"""<div class="migas"><a href="/tareas">Tareas</a> / {e(codigo)}</div>
      <p>{chip(t['estado'])} {chip(t['modo'], 'gris')} · {e(a.nombre)} · intentos {t['intentos']} de {t['max_intentos']}
      {' · vence ' + e(t['vence_en']) if t['vence_en'] else ''}</p>
      <div class="acciones">{''.join(acciones)}</div>
      <div class="dos"><div><h2>Objetivo</h2><p>{e(t['objetivo'])}</p>
      <h2>Entradas</h2><pre>{e(json.dumps(util.de_json(t['entradas'], {}), ensure_ascii=False, indent=2))}</pre>
      {'<h2>Resultado validado</h2><pre>' + e(json.dumps(util.de_json(t['resultado']), ensure_ascii=False, indent=2)) + '</pre>' if t['resultado'] else ''}
      {bloque_resultado}</div>
      <div><h2>Salida esperada</h2><pre>{e(t['salida_esperada'])}</pre>
      {'<h2>Lo que hubo que corregir</h2>' + filas_err if errores else ''}
      <h2>Historial</h2>{tabla(["Cuándo", "Qué", "Detalle"], [[e(x["en"]), e(x["tipo"]), e(x["detalle"][:300])] for x in eventos])}</div></div>
      {'<h2>Prompt preparado</h2><p>Archivo: <code>' + e(prompt_ruta) + '</code></p><pre>' + e(prompt) + '</pre>' if prompt else ''}"""
    return pagina(req, f"Tarea {codigo}", cuerpo)


@ruta("POST", r"/tareas/(?P<codigo>T-\d+)/ejecutar")
def ejecutar_tarea(req: Peticion, codigo: str):
    t = motor.obtener(req.cx, codigo)
    ctx, texto = _contexto_tarea(req, t)
    estado = motor.ejecutar(req.cx, req.cfg, codigo, ctx, texto)
    raise ir(f"/tareas/{codigo}", ok=f"Tarea {estado.lower().replace('_', ' ')}.")


@ruta("POST", r"/tareas/(?P<codigo>T-\d+)/completar")
def completar_tarea(req: Peticion, codigo: str):
    from ..agentes.proveedores import ErrorProveedor, extraer_json
    t = motor.obtener(req.cx, codigo)
    try:
        resultado = extraer_json(req.f("resultado"))
    except ErrorProveedor as ex:
        raise ir(f"/tareas/{codigo}", error=str(ex))
    ctx, _ = _contexto_tarea(req, t)
    estado = motor.registrar_resultado(req.cx, codigo, resultado, ctx, evidencias=["pegado en el panel"])
    if estado in ("EN_CURSO", "FALLIDA"):
        raise ir(f"/tareas/{codigo}", error="La respuesta no pasó la validación. Mira «Lo que hubo que corregir».")
    raise ir(f"/tareas/{codigo}", ok=f"Respuesta validada: {estado.lower().replace('_', ' ')}.")


@ruta("POST", r"/tareas/(?P<codigo>T-\d+)/aprobar")
def aprobar_tarea(req: Peticion, codigo: str):
    motor.aprobar(req.cx, codigo, "Didi", req.f("comentario"))
    raise ir(req.volver, ok=f"Tarea {codigo} aprobada.")


@ruta("POST", r"/tareas/(?P<codigo>T-\d+)/cancelar")
def cancelar_tarea(req: Peticion, codigo: str):
    motor.cancelar(req.cx, codigo, "Cancelada desde el panel")
    raise ir(req.volver, ok=f"Tarea {codigo} cancelada.")


# ------------------------------------------------------------------------------------------------- Ideas

def _productos(cx) -> list[tuple[str, str]]:
    return [(p["slug"], p["nombre_provisional"]) for p in cx.execute("SELECT slug, nombre_provisional FROM producto ORDER BY slug")]


@ruta("GET", "/ideas")
def lista_ideas(req: Peticion) -> str:
    ideas = req.cx.execute("""SELECT i.*, p.slug AS producto FROM idea i JOIN producto p ON p.id = i.producto_id
                              ORDER BY CASE WHEN i.estado IN ('NUEVA','EVALUADA','SELECCIONADA') THEN 0 ELSE 1 END,
                                       i.puntuacion DESC LIMIT 300""").fetchall()
    filas = []
    for i in ideas:
        expl = util.de_json(i["puntuacion_detalle"], {}).get("explicacion", "")
        acciones = ""
        if i["estado"] in ("NUEVA", "EVALUADA"):
            acciones = (boton(f"/ideas/{i['codigo']}/estado", "Seleccionar", "/ideas", estado="SELECCIONADA") + " " +
                        boton(f"/ideas/{i['codigo']}/estado", "Descartar", "/ideas", "peligro", estado="DESCARTADA"))
        filas.append([f'<b title="{e(expl)}">{i["puntuacion"]}</b>', e(i["codigo"]), e(i["idea_central"]) +
                      f'<br><small class="vacio">{e(i["problema"])}</small>', e(i["formato"]), e(i["canal"]),
                      chip(i["etapa_embudo"], "gris"), chip(i["estado"]), acciones])
    etapas = contenido.ETAPAS_EMBUDO
    escala = [str(n) for n in range(1, 6)]
    form = formulario("/ideas", f"""<div class="campos">{selector("producto", "Producto", _productos(req.cx))}
        {campo("idea_central", "Idea central", requerido=True)}{campo("problema", "Problema que resuelve", requerido=True)}
        {campo("formato", "Formato (carrusel, vídeo corto, meme…)", requerido=True)}{campo("canal", "Canal", "facebook", requerido=True)}
        {selector("etapa_embudo", "Etapa del embudo", etapas)}{campo("objetivo", "Objetivo", "Lista de espera", requerido=True)}
        {selector("relevancia", "Relevancia para el público (1-5)", escala, "3")}{selector("atencion", "Capacidad de atención (1-5)", escala, "3")}
        {selector("valor_comercial", "Valor comercial (1-5)", escala, "3")}{selector("coste", "Coste (1 barato, 5 caro)", escala, "1")}
        {selector("esfuerzo", "Esfuerzo (1 poco, 5 mucho)", escala, "2")}{campo("fecha_oportunidad", "Fecha de oportunidad", tipo="date")}
        {campo("evidencia", "Evidencia o fuente", clase="ancho")}</div>""", "Guardar y puntuar", volver="/ideas")
    pesos = ", ".join(f"{k.replace('_', ' ')} {int(v * 100)} %" for k, v in contenido.PESOS_IDEA.items())
    cuerpo = f"""{tabla(["Puntos", "Código", "Idea", "Formato", "Canal", "Etapa", "Estado", ""], filas, "Todavía no hay ideas.")}
      <h2>Nueva idea</h2><p>La puntuación pesa: {e(pesos)}. Coste y esfuerzo restan. Una oportunidad en los próximos 14 días suma 5.</p>{form}"""
    return pagina(req, "Ideas", cuerpo, "Pasa el cursor sobre la puntuación para ver por qué tiene esos puntos.")


@ruta("POST", "/ideas")
def crear_idea(req: Peticion):
    codigo = contenido.crear_idea(
        req.cx, req.f("producto"), problema=req.f("problema"), idea_central=req.f("idea_central"), formato=req.f("formato"),
        canal=req.f("canal"), etapa_embudo=req.f("etapa_embudo"), objetivo=req.f("objetivo"),
        relevancia=req.fi("relevancia"), atencion=req.fi("atencion"), valor_comercial=req.fi("valor_comercial"),
        coste=req.fi("coste"), esfuerzo=req.fi("esfuerzo"), evidencia=req.f("evidencia"),
        fecha_oportunidad=req.f("fecha_oportunidad") or None)
    raise ir("/ideas", ok=f"Idea {codigo} guardada.")


@ruta("POST", r"/ideas/(?P<codigo>I-\d+)/estado")
def estado_idea(req: Peticion, codigo: str):
    contenido.cambiar_estado_idea(req.cx, codigo, req.f("estado"))
    raise ir(req.volver, ok=f"Idea {codigo}: {req.f('estado').lower()}.")


# ---------------------------------------------------------------------------------------------- Campañas

@ruta("GET", "/campanas")
def lista_campanas(req: Peticion) -> str:
    camps = req.cx.execute("""SELECT c.*, p.slug AS producto,
                                (SELECT COUNT(*) FROM pieza pz WHERE pz.campana_id = c.id) AS piezas,
                                (SELECT COUNT(*) FROM lead l WHERE l.campana_id = c.id) AS leads
                              FROM campana c JOIN producto p ON p.id = c.producto_id ORDER BY c.id DESC""").fetchall()
    filas = [[f"<b>{e(c['nombre'])}</b><br><small>{e(c['slug'])}</small>", e(c["objetivo"]), e(c["oferta"]), e(c["cta"]),
              e(c["metrica_exito"]) + (f" (meta {c['meta_valor']})" if c["meta_valor"] else ""), e(c["piezas"]), e(c["leads"]),
              chip(c["estado"])] for c in camps]
    form = formulario("/campanas", f"""<div class="campos">{selector("producto", "Producto", _productos(req.cx))}
        {campo("nombre", "Nombre", requerido=True)}{campo("slug", "Identificador corto (sin espacios)", requerido=True)}
        {campo("objetivo", "Objetivo", requerido=True)}{campo("hipotesis", "Hipótesis", requerido=True, clase="ancho")}
        {campo("oferta", "Oferta (sin precios en prelanzamiento)", requerido=True)}{campo("cta", "Llamado a la acción", requerido=True)}
        {campo("metrica_exito", "Métrica de éxito", "inscripciones en la lista de espera", requerido=True)}
        {campo("meta_valor", "Meta (número)", tipo="number")}{campo("inicio", "Inicio", tipo="date")}{campo("fin", "Fin", tipo="date")}</div>""",
                      "Guardar campaña", volver="/campanas")
    cuerpo = tabla(["Campaña", "Objetivo", "Oferta", "Llamado", "Métrica", "Piezas", "Leads", "Estado"], filas,
                   "Todavía no hay campañas.") + "<h2>Nueva campaña</h2>" + form
    return pagina(req, "Campañas", cuerpo)


@ruta("POST", "/campanas")
def crear_campana(req: Peticion):
    politica = aud.Politica.desde_carpeta(req.cfg.raiz / "productos" / req.f("producto"))
    informe = aud.auditar(aud.PiezaParaAuditar(tipo_afirmacion="CAPTACION", canal="plan",
                                               textos={"oferta": req.f("oferta"), "cta": req.f("cta")}, cta=req.f("cta")), politica)
    if informe.bloqueantes:
        raise ir("/campanas", error="La oferta o el llamado no pasan el auditor: " + " ".join(h.mensaje for h in informe.bloqueantes))
    contenido.crear_campana(req.cx, req.f("producto"), slug=util.slug(req.f("slug")), nombre=req.f("nombre"),
                            objetivo=req.f("objetivo"), hipotesis=req.f("hipotesis"), oferta=req.f("oferta"), cta=req.f("cta"),
                            metrica_exito=req.f("metrica_exito"), meta_valor=req.fi("meta_valor"),
                            inicio=req.f("inicio") or None, fin=req.f("fin") or None)
    raise ir("/campanas", ok="Campaña guardada.")


# ------------------------------------------------------------------------------------------------ Piezas

TIPOS = aud.TIPOS_AFIRMACION


@ruta("GET", "/piezas")
def lista_piezas(req: Peticion) -> str:
    estado, canal = req.q("estado"), req.q("canal")
    sql = "SELECT pz.*, c.slug AS campana FROM pieza pz LEFT JOIN campana c ON c.id = pz.campana_id WHERE 1 = 1"
    params = []
    if estado:
        sql += " AND pz.estado = ?"
        params.append(estado)
    if canal:
        sql += " AND pz.canal = ?"
        params.append(canal)
    piezas = req.cx.execute(sql + " ORDER BY COALESCE(pz.fecha_prevista, '9999'), pz.id LIMIT 500", params).fetchall()
    filas = [[f'<a href="/piezas/{e(p["codigo"])}">{e(p["codigo"])}</a>', e(p["fecha_prevista"] or "—"), e(p["titulo"]),
              e(p["formato"]), e(p["canal"]), chip(p["tipo_afirmacion"], "gris"), e(p["campana"] or ""), chip(p["estado"]),
              f"v{p['version_actual']}"] for p in piezas]
    camps = [(c["slug"], c["nombre"]) for c in req.cx.execute("SELECT slug, nombre FROM campana ORDER BY nombre")]
    plantillas_ = sorted(de_producto(req.cfg, None)[0]["plantillas"])
    form = formulario("/piezas", f"""<div class="campos">{selector("producto", "Producto", _productos(req.cx))}
        {campo("titulo", "Título interno", requerido=True)}{campo("formato", "Formato", "post", requerido=True)}
        {campo("canal", "Canal", "facebook", requerido=True)}{selector("tipo", "Tipo de afirmación", TIPOS, "CAPTACION")}
        {campo("fecha", "Fecha prevista", tipo="date")}{selector("campana", "Campaña", camps, vacio="(ninguna)")}
        {campo("idea", "Idea (código, opcional)")}{selector("plantilla", "Plantilla", plantillas_, vacio="(ninguna)")}</div>""",
                      "Crear pieza", volver="/piezas")
    estados = ["", "BORRADOR", "CORRECCIONES", "LISTA_PARA_APROBAR", "APROBADA", "PROGRAMADA", "PUBLICADA", "RECHAZADA", "ARCHIVADA"]
    filtro = " ".join(f'<a class="chip {"lima" if s == estado else "gris"}" href="/piezas{"?estado=" + s if s else ""}">'
                      f'{e(s.lower().replace("_", " ") or "todas")}</a>' for s in estados)
    cuerpo = f"<p>{filtro}</p>" + tabla(["Pieza", "Fecha", "Título", "Formato", "Canal", "Tipo", "Campaña", "Estado", "Versión"],
                                        filas, "Todavía no hay piezas.") + "<h2>Nueva pieza</h2>" + form
    return pagina(req, "Biblioteca de contenidos", cuerpo, "Cada pieza guarda todas sus versiones, revisiones, aprobaciones y archivos.")


@ruta("POST", "/piezas")
def crear_pieza(req: Peticion):
    codigo = contenido.crear_pieza(req.cx, req.f("producto"), formato=req.f("formato"), canal=req.f("canal"),
                                   titulo=req.f("titulo"), tipo_afirmacion=req.f("tipo"), campana=req.f("campana") or None,
                                   idea=req.f("idea") or None, fecha_prevista=req.f("fecha") or None,
                                   plantilla=req.f("plantilla") or None)
    raise ir(f"/piezas/{codigo}", ok=f"Pieza {codigo} creada. Ahora escribe su contenido.")


@ruta("GET", r"/piezas/(?P<codigo>P-\d+)")
def ver_pieza(req: Peticion, codigo: str) -> str:
    cx = req.cx
    p = contenido.obtener_pieza(cx, codigo)
    v = contenido.version_actual(cx, p)
    datos = util.de_json(v["contenido"], {}) if v else {}
    caps = util.de_json(v["capacidades"], []) if v else []
    fuentes = util.de_json(v["fuentes"], []) if v else []
    politica = aud.Politica.desde_carpeta(req.cfg.raiz / "productos" / p["producto"])
    filas_caps = []
    for c in caps:
        cap = politica.capacidades.get(c)
        filas_caps.append([e(c), e(cap.nombre if cap else "no existe en la matriz"), chip(cap.uso if cap else "RECHAZADO"),
                           e(cap.matiz if cap else "")])
    textos = contenido.textos_de(datos)
    rev = cx.execute("SELECT * FROM revision WHERE pieza_id = ? ORDER BY id DESC LIMIT 1", (p["id"],)).fetchone()
    hallazgos = ""
    if rev:
        items = sorted(util.de_json(rev["hallazgos"], []), key=lambda h: h.get("severidad") != aud.BLOQUEANTE)
        hallazgos = (f"<p>Versión {rev['version']} · {chip(rev['resultado'])} · {e(rev['creado_en'])}</p>" +
                     "".join(f'<div class="hallazgo {e(h.get("severidad"))}"><b>{e(h.get("severidad", "").lower())}</b> · '
                             f'{e(h.get("mensaje"))}{" <i>" + e(h.get("sugerencia")) + "</i>" if h.get("sugerencia") else ""}</div>'
                             for h in items) or "<p>Sin hallazgos.</p>")
    aprob = cx.execute("SELECT * FROM aprobacion WHERE pieza_id = ? ORDER BY id DESC", (p["id"],)).fetchall()
    filas_ap = [[e(a["decidido_en"]), f"v{a['version']}", chip(a["decision"]), e(a["decidido_por"]), e(a["comentario"])] for a in aprob]
    activos = cx.execute("SELECT * FROM activo WHERE pieza_id = ? AND version = ? ORDER BY ruta",
                         (p["id"], p["version_actual"])).fetchall()
    previas = "".join(_vista_activo(a) for a in activos)
    anteriores = cx.execute("SELECT COUNT(*) FROM activo WHERE pieza_id = ? AND version <> ?",
                            (p["id"], p["version_actual"])).fetchone()[0]
    pubs = cx.execute("SELECT * FROM publicacion WHERE pieza_id = ? ORDER BY id DESC", (p["id"],)).fetchall()
    filas_pub = [[f"#{x['id']}", e(x["canal"]), chip(x["estado"]), e(x["fecha_prevista"]),
                  f'<a href="{e(x["url"])}">{e(x["url"])}</a>' if x["url"] else ""] for x in pubs]
    versiones = cx.execute("SELECT numero, autor, creado_en, nota FROM pieza_version WHERE pieza_id = ? ORDER BY numero DESC",
                           (p["id"],)).fetchall()
    volver = f"/piezas/{codigo}"
    acciones = []
    if v and p["estado"] not in ("PUBLICADA", "ARCHIVADA"):
        acciones.append(boton(f"/piezas/{codigo}/auditar", "Pasar por el auditor", volver, ""))
    if v and p["plantilla"]:
        acciones.append(boton(f"/piezas/{codigo}/render", "Generar imágenes y vídeo", volver, "sec"))
    if p["estado"] == "LISTA_PARA_APROBAR":
        acciones += [boton(f"/piezas/{codigo}/decidir", "Aprobar esta versión", volver, "lima", decision="APROBADA"),
                     boton(f"/piezas/{codigo}/decidir", "Pedir correcciones", volver, "sec", decision="CORRECCIONES"),
                     boton(f"/piezas/{codigo}/decidir", "Rechazar", volver, "peligro", decision="RECHAZADA")]
    form_pub = ""
    if p["estado"] == "APROBADA":
        form_pub = "<h2>Preparar la publicación</h2>" + formulario(f"/piezas/{codigo}/publicacion", f"""<div class="campos">
            {campo("canal", "Canal", p["canal"])}{campo("fecha", "Fecha prevista", p["fecha_prevista"] or "", "date")}
            {campo("copy", "Texto que acompaña la publicación", datos.get("copy", ""), "textarea", clase="ancho")}</div>""",
                                                                   "Dejar listo el paquete", volver=volver)
    extra = {k: val for k, val in datos.items() if k not in ("gancho", "copy", "cta", "fecha_publicacion_fuente",
                                                             "revisado_por_contador", "es_demostracion_guiada")}
    ayuda_plantilla = ""
    if p["plantilla"]:
        try:
            ficha = fab_plantillas.ficha(req.cfg.raiz, p["plantilla"])
        except KeyError:
            ficha = None
        if ficha:
            if not extra:
                extra = {k: val for k, val in ficha.get("ejemplo", {}).items() if k != "cta"}
            filas_campos = [[f"<code>{e(k)}</code>", e(r.get("tipo", "texto")), "sí" if r.get("requerido") else "",
                             e(r.get("max", r.get("max_items", "")))] for k, r in ficha.get("campos", {}).items()]
            ayuda_plantilla = (f"<details><summary>Campos de la plantilla «{e(ficha['titulo'])}»</summary>"
                               f"<p>{e(ficha['descripcion'])} Formatos: {e(', '.join(ficha['formatos']))}. "
                               "Escribe <code>*palabra*</code> para resaltarla.</p>"
                               + tabla(["Campo", "Tipo", "Obligatorio", "Máximo"], filas_campos) + "</details>")
    form_version = formulario(f"/piezas/{codigo}/version", f"""<div class="campos">
        {campo("gancho", "Gancho (primera línea)", datos.get("gancho", ""), clase="ancho")}
        {campo("copy", "Copy", datos.get("copy", ""), "textarea", clase="ancho")}
        {campo("cta", "Llamado a la acción", datos.get("cta", ""))}
        {campo("capacidades", "Capacidades que afirma (códigos separados por coma)", ", ".join(caps))}
        {campo("fuentes", "Fuentes (una URL por línea)", chr(10).join(str(f) for f in fuentes), "textarea", clase="ancho")}
        {campo("fecha_publicacion_fuente", "Fecha de publicación de la fuente (noticias)", datos.get("fecha_publicacion_fuente", ""), "date")}
        {check("revisado_por_contador", "Un contador revisó el contenido normativo", bool(datos.get("revisado_por_contador")))}
        {check("es_demostracion_guiada", "Es una demostración guiada en vivo", bool(datos.get("es_demostracion_guiada")))}
        {campo("extra", "Textos de la plantilla y otros campos (JSON, opcional)", json.dumps(extra, ensure_ascii=False, indent=2) if extra else "", "textarea", clase="ancho")}
        {campo("nota", "Nota de esta versión", clase="ancho")}</div>""", "Guardar como versión nueva", volver=volver)
    cuerpo = f"""<div class="migas"><a href="/piezas">Biblioteca</a> / {e(codigo)}</div>
      <p>{chip(p['estado'])} {chip(p['tipo_afirmacion'], 'gris')} · {e(p['formato'])} para {e(p['canal'])} ·
      fecha {e(p['fecha_prevista'] or 'sin fecha')} · versión {p['version_actual']}{' · plantilla ' + e(p['plantilla']) if p['plantilla'] else ''}</p>
      <div class="acciones">{''.join(acciones)}</div>
      <div class="dos"><div><h2>Contenido actual</h2>
      {tabla(["Campo", "Texto"], [[e(k), e(t).replace(chr(10), '<br>')] for k, t in textos.items()], "Todavía no tiene contenido.")}
      <h2>Capacidades que afirma</h2>{tabla(["Código", "Capacidad", "Uso", "Matiz"], filas_caps, "No cita capacidades.")}
      {'<h2>Fuentes</h2>' + '<br>'.join(f'<a href="{e(f)}">{e(f)}</a>' for f in fuentes) if fuentes else ''}
      {'<h2>Archivos de esta versión</h2><div class="previa">' + previas + '</div>' if activos else ''}
      {f'<p class="vacio">{anteriores} archivos de versiones anteriores siguen en la carpeta de salidas.</p>' if anteriores else ''}</div>
      <div><h2>Auditor</h2>{hallazgos or '<p class="vacio">Todavía no pasó por el auditor.</p>'}
      <h2>Decisiones</h2>{tabla(["Cuándo", "Versión", "Decisión", "Quién", "Comentario"], filas_ap, "Sin decisiones.")}
      <h2>Publicaciones</h2>{tabla(["#", "Canal", "Estado", "Fecha", "Enlace"], filas_pub, "Sin publicaciones.")}
      <h2>Versiones</h2>{tabla(["N.°", "Autor", "Cuándo", "Nota"], [[e(x["numero"]), e(x["autor"]), e(x["creado_en"]), e(x["nota"])] for x in versiones])}</div></div>
      {form_pub}<h2>Escribir una versión nueva</h2>{ayuda_plantilla}{form_version}"""
    return pagina(req, p["titulo"], cuerpo)


@ruta("POST", r"/piezas/(?P<codigo>P-\d+)/version")
def nueva_version(req: Peticion, codigo: str):
    datos: dict = {}
    if req.f("extra"):
        try:
            datos = json.loads(req.f("extra"))
        except json.JSONDecodeError as ex:
            raise ir(f"/piezas/{codigo}", error=f"Los textos de la plantilla no son JSON válido: {ex}")
        if not isinstance(datos, dict):
            raise ir(f"/piezas/{codigo}", error="Los textos de la plantilla deben ser un objeto JSON.")
    for k in ("gancho", "copy", "cta", "fecha_publicacion_fuente"):
        if req.f(k):
            datos[k] = req.f(k)
    if req.marcado("revisado_por_contador"):
        datos["revisado_por_contador"] = True
    if req.marcado("es_demostracion_guiada"):
        datos["es_demostracion_guiada"] = True
    fuentes = [x.strip() for x in req.f("fuentes").splitlines() if x.strip()]
    n = contenido.nueva_version(req.cx, codigo, datos, capacidades=lista_codigos(req.f("capacidades")), fuentes=fuentes,
                                autor="Didi", nota=req.f("nota"))
    informe = contenido.auditar_pieza(req.cx, req.cfg.raiz, codigo)
    texto = f"Versión {n} guardada. Auditor: {informe.resultado.lower().replace('_', ' ')}."
    if informe.resultado == "RECHAZADO":
        raise ir(f"/piezas/{codigo}", error=texto + " Corrige los bloqueos antes de aprobar.")
    raise ir(f"/piezas/{codigo}", ok=texto)


@ruta("POST", r"/piezas/(?P<codigo>P-\d+)/render")
def render_pieza(req: Peticion, codigo: str):
    from ..fabrica import render
    res = render.exportar_pieza(req.cx, req.cfg, codigo)
    avisos = (" Avisos: " + "; ".join(res.avisos)) if any("no cabe" in a for a in res.avisos) else ""
    raise ir(req.volver, ok=f"{len(res.archivos)} archivos generados.{avisos}")


def _vista_activo(a) -> str:
    url = "/archivos/" + quote(a["ruta"])
    nombre = e(a["ruta"].rsplit("/", 1)[-1])
    if a["tipo"] == "imagen":
        return f'<figure><a href="{url}"><img src="{url}" alt=""></a><figcaption><small>{nombre}</small></figcaption></figure>'
    if a["tipo"] == "video":
        return f'<figure><video src="{url}" controls preload="metadata"></video><figcaption><small>{nombre}</small></figcaption></figure>'
    return f'<p><a href="{url}">{nombre}</a></p>'


@ruta("POST", r"/piezas/(?P<codigo>P-\d+)/auditar")
def auditar_pieza(req: Peticion, codigo: str):
    informe = contenido.auditar_pieza(req.cx, req.cfg.raiz, codigo)
    raise ir(req.volver, ok=f"Auditor: {informe.resultado.lower().replace('_', ' ')}.")


@ruta("POST", r"/piezas/(?P<codigo>P-\d+)/decidir")
def decidir_pieza(req: Peticion, codigo: str):
    contenido.decidir(req.cx, codigo, req.f("decision"), "Didi", req.f("comentario"))
    raise ir(req.volver, ok=f"{codigo}: {req.f('decision').lower()}.")


@ruta("POST", r"/piezas/(?P<codigo>P-\d+)/publicacion")
def preparar_publicacion(req: Peticion, codigo: str):
    pub = contenido.preparar_publicacion(req.cx, codigo, canal=req.f("canal") or None, copy=req.f("copy") or None,
                                         fecha_prevista=req.f("fecha") or None)
    raise ir("/publicaciones", ok=f"Paquete #{pub} listo. Publícalo o prográmalo en la red, y vuelve a confirmar con el enlace.")


# ----------------------------------------------------------------------------------------- Publicaciones

@ruta("GET", "/publicaciones")
def lista_publicaciones(req: Peticion) -> str:
    pubs = req.cx.execute("""SELECT pb.*, pz.codigo, pz.titulo FROM publicacion pb JOIN pieza pz ON pz.id = pb.pieza_id
                             ORDER BY CASE pb.estado WHEN 'PAQUETE_LISTO' THEN 0 WHEN 'PROGRAMADA' THEN 1 WHEN 'FALLIDA' THEN 2 ELSE 3 END,
                                      pb.fecha_prevista, pb.id DESC LIMIT 300""").fetchall()
    filas = []
    for x in pubs:
        acciones = ""
        if x["estado"] in ("PAQUETE_LISTO", "PROGRAMADA", "FALLIDA"):
            acciones = (formulario(f"/publicaciones/{x['id']}/confirmar", '<input name="url" placeholder="https://… enlace publicado" required>',
                                   "Ya está publicada", clase="linea", volver="/publicaciones", clase_boton="lima") +
                        formulario(f"/publicaciones/{x['id']}/programar", f'<input type="date" name="fecha" value="{e(x["fecha_prevista"] or "")}">',
                                   "Programada", clase="linea", volver="/publicaciones", clase_boton="sec") +
                        formulario(f"/publicaciones/{x['id']}/fallo", '<input name="error" placeholder="qué falló" required>',
                                   "Falló", clase="linea", volver="/publicaciones", clase_boton="peligro"))
        filas.append([f"#{x['id']}", f'<a href="/piezas/{e(x["codigo"])}">{e(x["codigo"])}</a> {e(x["titulo"])}', e(x["canal"]),
                      e(x["fecha_prevista"]), chip(x["estado"]),
                      (f'<a href="{e(x["url"])}">ver publicación</a>' if x["url"] else e(x["error"] or "")),
                      f'<details><summary>copy</summary><pre>{e(x["copy"])}</pre></details>', acciones])
    cuerpo = tabla(["#", "Pieza", "Canal", "Fecha", "Estado", "Enlace o error", "Texto", "Registrar"], filas,
                   "No hay paquetes de publicación. Se preparan desde una pieza aprobada.")
    return pagina(req, "Publicaciones", cuerpo,
                  "El sistema no publica nada. Tú publicas o programas en cada red, y aquí registras el enlace como prueba.")


@ruta("POST", r"/publicaciones/(?P<pid>\d+)/(?P<accion>confirmar|programar|fallo)")
def accion_publicacion(req: Peticion, pid: str, accion: str):
    if accion == "confirmar":
        contenido.confirmar_publicacion(req.cx, int(pid), url=req.f("url"))
    elif accion == "programar":
        if not req.f("fecha"):
            raise ir("/publicaciones", error="Indica la fecha programada.")
        contenido.marcar_programada(req.cx, int(pid), req.f("fecha"))
    else:
        contenido.registrar_fallo(req.cx, int(pid), req.f("error"))
    raise ir("/publicaciones", ok=f"Publicación #{pid} actualizada.")


# ------------------------------------------------------------------------------------------------- Leads

@ruta("GET", "/leads")
def lista_leads(req: Peticion) -> str:
    embudo = leads.embudo(req.cx)
    tarjetas = "".join(f'<div class="tarjeta"><div class="cifra">{n}</div>{e(s.lower().replace("_", " "))}</div>'
                       for s, n in embudo.items() if n or s in ("NUEVO", "BETA"))
    filas = []
    for l in req.cx.execute("""SELECT l.*, p.slug AS producto FROM lead l JOIN producto p ON p.id = l.producto_id
                               ORDER BY COALESCE(l.seguimiento_en, '9999'), l.ingreso_en DESC LIMIT 500"""):
        contacto = " ".join(x for x in (enmascarar_email(l["email"]), enmascarar_telefono(l["telefono"])) if x)
        consent = ("sí" if l["consentimiento"] else "no") + (" + publicidad" if l["consentimiento_publicidad"] else "")
        form = formulario(f"/leads/{l['uid']}", selector("estado", "", leads.ESTADOS, l["estado"]) +
                          f'<input name="proxima" placeholder="próxima acción" value="{e(l["proxima_accion"])}">'
                          f'<input type="date" name="fecha" value="{e(l["seguimiento_en"] or "")}">', "Guardar",
                          clase="linea", volver="/leads", clase_boton="sec")
        filas.append([e(l["ingreso_en"][:10]), e(l["nombre"] or "(sin nombre)") + f"<br><small>{e(contacto)}</small>",
                      e(l["fuente"]), e(l["empresas_que_lleva"] if l["empresas_que_lleva"] is not None else ""),
                      e(l["problema_principal"]), e(consent), chip(l["estado"]), form])
    form_nuevo = formulario("/leads", f"""<div class="campos">{selector("producto", "Producto", _productos(req.cx))}
        {campo("nombre", "Nombre")}{campo("email", "Correo", tipo="email")}{campo("telefono", "Teléfono")}
        {campo("fuente", "Fuente", "whatsapp", requerido=True)}{campo("empresas", "Empresas que lleva", tipo="number")}
        {campo("problema", "Problema principal", clase="ancho")}
        {check("consentimiento", "Aceptó el aviso de privacidad para que le respondamos")}
        {check("publicidad", "Aceptó, aparte, recibir novedades comerciales")}
        {campo("finalidad", "Finalidad aceptada", "Responder su consulta y avisarle de la beta privada")}
        {campo("version_aviso", "Versión del aviso aceptado", "aviso-privacidad-v1")}</div>""", "Registrar lead", volver="/leads")
    form_derechos = formulario("/leads/derechos", f"""<div class="campos">{campo("contacto", "Correo o teléfono de la persona", requerido=True)}
        {selector("accion", "Qué pidió", [("baja", "No recibir más mensajes (baja)"), ("acceso", "Ver sus datos (acceso)"),
                                         ("suprimir", "Borrar sus datos (supresión)")])}
        {check("confirmo", "Confirmo que la persona lo pidió")}</div>""", "Aplicar", volver="/leads")
    cuerpo = f"""<div class="tarjetas">{tarjetas}</div>
      <h2>Leads</h2>{tabla(["Ingreso", "Persona", "Fuente", "Empresas", "Problema", "Consentimiento", "Estado", "Seguimiento"], filas,
                         "Todavía no hay leads.")}
      <div class="dos"><div><h2>Registrar un lead</h2><p>Solo si la persona te escribió o llenó el formulario. Sin consentimiento,
      solo se le responde lo que pidió.</p>{form_nuevo}</div>
      <div><h2>Derechos de la persona</h2><p>Plazos: acceso 20 días hábiles; baja, rectificación y supresión 10.</p>{form_derechos}
      <h2>Exportar</h2><p>El archivo tiene datos personales: queda solo en tu PC.</p>
      {formulario("/leads/exportar", "", "Exportar a CSV", clase="linea", volver="/leads", clase_boton="sec")}</div></div>"""
    return pagina(req, "Leads", cuerpo, "Los contactos se muestran enmascarados. El archivo completo se exporta solo a tu PC.")


@ruta("POST", "/leads")
def registrar_lead(req: Peticion):
    uid, nuevo = leads.registrar(
        req.cx, req.f("producto"), fuente=req.f("fuente"), email=req.f("email") or None, telefono=req.f("telefono") or None,
        nombre=req.f("nombre"), problema_principal=req.f("problema"), empresas_que_lleva=req.fi("empresas"),
        consentimiento=req.marcado("consentimiento"), consentimiento_publicidad=req.marcado("publicidad"),
        finalidad=req.f("finalidad") if req.marcado("consentimiento") else "",
        consentimiento_version=req.f("version_aviso") or None, consentimiento_medio="panel")
    raise ir("/leads", ok="Lead registrado." if nuevo else "Ya existía: se actualizó sin duplicarlo.")


@ruta("POST", r"/leads/(?P<uid>[0-9a-f]{32})")
def actualizar_lead(req: Peticion, uid: str):
    leads.actualizar(req.cx, uid, estado=req.f("estado") or None, proxima_accion=req.f("proxima"),
                     seguimiento_en=req.f("fecha") or None)
    raise ir("/leads", ok="Lead actualizado.")


@ruta("POST", "/leads/derechos")
def derechos_lead(req: Peticion):
    if not req.marcado("confirmo"):
        raise ir("/leads", error="Marca la casilla de confirmación.")
    contacto, accion = req.f("contacto"), req.f("accion")
    if accion == "baja":
        n = leads.dar_de_baja(req.cx, contacto)
        raise ir("/leads", ok=f"Baja registrada ({n} registros). No volverá a recibir publicidad.")
    if accion == "acceso":
        datos = leads.exportar_titular(req.cx, contacto)
        ruta_ = req.cfg.salidas / f"acceso-{util.ahora_utc()[:10]}-{util.uid()[:6]}.json"
        ruta_.parent.mkdir(parents=True, exist_ok=True)
        ruta_.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        raise ir("/leads", ok=f"{len(datos['registros'])} registros en {ruta_}. Entrégaselo y luego borra el archivo.")
    n = leads.suprimir(req.cx, contacto)
    raise ir("/leads", ok=f"Datos suprimidos ({n} registros). Solo queda el hash para no volver a escribirle.")


@ruta("POST", "/leads/exportar")
def exportar_leads(req: Peticion):
    ruta_ = req.cfg.salidas / f"leads-{util.ahora_utc()[:10]}.csv"
    n = leads.exportar_csv(req.cx, ruta_)
    raise ir("/leads", ok=f"{n} leads exportados a {ruta_}.")


# ---------------------------------------------------------------------------------------------- Métricas

@ruta("GET", "/metricas")
def vista_metricas(req: Peticion) -> str:
    hasta = req.q("hasta") or util.hoy_lima().isoformat()
    desde = req.q("desde") or (date.fromisoformat(hasta) - timedelta(days=28)).isoformat()
    r = metricas.resumen(req.cx, desde, hasta)
    bloques = []
    for naturaleza, titulo in (("medido", "Medido"), ("estimado", "Estimado (no es dato real)")):
        filas = [[e(c), e(n), f"<b>{v:,}</b>"] for c, valores in r[naturaleza].items() for n, v in valores.items()]
        bloques.append(f"<h2>{titulo}</h2>" + tabla(["Canal", "Métrica", "Valor"], filas, "Sin datos."))
    recs = metricas.recomendaciones(req.cx, desde, hasta)
    filas_r = [[chip(x["decision"], "azul"), e(x.get("pieza", "")), e(x["motivo"])] for x in recs]
    pubs = [(x["id"], f"#{x['id']} {x['canal']} {x['codigo']}") for x in req.cx.execute(
        """SELECT pb.id, pb.canal, pz.codigo FROM publicacion pb JOIN pieza pz ON pz.id = pb.pieza_id
           WHERE pb.estado = 'PUBLICADA' ORDER BY pb.id DESC LIMIT 200""")]
    form = formulario("/metricas", f"""<div class="campos">{selector("publicacion", "Publicación", pubs)}
        {selector("nombre", "Métrica", metricas.NOMBRES)}{campo("valor", "Valor", tipo="number", requerido=True)}
        {campo("fecha", "Fecha del dato", util.hoy_lima().isoformat(), "date")}
        {selector("naturaleza", "Naturaleza", [("MEDIDA", "Medida (la vi en la red)"), ("ESTIMADA", "Estimada")])}
        {campo("nota", "Nota")}</div>""", "Registrar métrica", volver="/metricas")
    recic = metricas.reciclables(req.cx, hasta)
    filas_rec = [[e(x["codigo"]), e(x["titulo"]), e(x["canal"]), e(x["interesados"]), e(x["guardados"])] for x in recic]
    cuerpo = f"""<form method="get" class="acciones"><input type="date" name="desde" value="{e(desde)}" style="width:auto">
      <input type="date" name="hasta" value="{e(hasta)}" style="width:auto"><button class="sec">Ver</button></form>
      <p>{r['publicaciones']} publicaciones confirmadas en el periodo.</p>{''.join(bloques)}
      <h2>Recomendaciones</h2>{tabla(["Decisión", "Pieza", "Motivo"], filas_r)}
      <h2>Para reciclar</h2>{tabla(["Pieza", "Título", "Canal", "Interesados", "Guardados y compartidos"], filas_rec,
                                  "Nada para reciclar todavía (se sugiere a los 60 días de publicada).")}
      <h2>Registrar una métrica</h2>{form if pubs else '<p class="vacio">Primero confirma una publicación con su enlace.</p>'}"""
    return pagina(req, "Métricas", cuerpo, "Lo medido y lo estimado nunca se suman. Ninguna venta se atribuye a un post sin prueba.")


@ruta("POST", "/metricas")
def registrar_metrica(req: Peticion):
    metricas.registrar(req.cx, req.f("nombre"), req.fi("valor") if req.fi("valor") is not None else -1, req.f("fecha"),
                       naturaleza=req.f("naturaleza"), publicacion_id=req.fi("publicacion"), nota=req.f("nota"))
    raise ir("/metricas", ok="Métrica registrada.")


# ------------------------------------------------------------------------------------------------- Radar

@ruta("GET", "/radar")
def vista_radar(req: Peticion) -> str:
    items = req.cx.execute("""SELECT r.*, f.titulo AS fuente FROM radar_item r LEFT JOIN fuente f ON f.id = r.fuente_id
                              ORDER BY CASE r.estado_verificacion WHEN 'SIN_VERIFICAR' THEN 0 ELSE 1 END, r.detectado_en DESC
                              LIMIT 200""").fetchall()
    filas = []
    for r in items:
        acciones = ""
        if r["estado_verificacion"] == "SIN_VERIFICAR":
            acciones = (boton(f"/radar/{r['id']}/verificar", "Leí la fuente oficial", "/radar", "lima") + " " +
                        boton(f"/radar/{r['id']}/descartar", "Descartar", "/radar", "sec") + " " +
                        boton(f"/radar/{r['id']}/rumor", "Es rumor", "/radar", "peligro"))
        filas.append([f'<a href="{e(r["url"])}">{e(r["titulo"])}</a><br><small>{e(r["fuente"] or "")}</small>',
                      e(r["fecha_publicacion"]), e(r["afecta_a"]), e(r["que_cambia"]),
                      "oficial" if r["es_fuente_primaria"] else "no oficial", chip(r["estado_verificacion"]), acciones])
    fuentes = req.cx.execute("SELECT * FROM fuente ORDER BY tipo, organismo, titulo").fetchall()
    filas_f = [[f'<a href="{e(f["url"])}">{e(f["titulo"])}</a>', e(f["organismo"]), chip(f["tipo"], "gris"), e(f["metodo"].lower()),
                f"cada {f['frecuencia_horas']} h", "sí" if f["activa"] else "no", e(f["notas"])] for f in fuentes]
    form = formulario("/radar", f"""<div class="campos">{campo("titulo", "Título", requerido=True)}
        {campo("url", "Enlace (https)", requerido=True)}{campo("fecha_publicacion", "Fecha de publicación", tipo="date")}
        {campo("fecha_vigencia", "Vigencia desde", tipo="date")}{campo("afecta_a", "A quién afecta")}
        {campo("que_cambia", "Qué cambia", clase="ancho")}</div>""", "Agregar novedad", volver="/radar")
    cuerpo = f"""{tabla(["Novedad", "Publicada", "Afecta a", "Qué cambia", "Fuente", "Estado", ""], filas,
                       "No hay novedades registradas. Agrega una o espera al radar automático (Fase 4).")}
      <h2>Agregar una novedad</h2>{form}<h2>Fuentes vigiladas</h2>{tabla(["Fuente", "Organismo", "Tipo", "Método", "Frecuencia", "Activa", "Notas"], filas_f)}"""
    return pagina(req, "Radar normativo", cuerpo,
                  "Una novedad solo se usa en una pieza cuando alguien leyó la fuente oficial. Interpretarla requiere un contador.")


@ruta("POST", "/radar")
def agregar_radar(req: Peticion):
    _, nuevo = radar.agregar(req.cx, titulo=req.f("titulo"), url=req.f("url"), fecha_publicacion=req.f("fecha_publicacion") or None,
                             fecha_vigencia=req.f("fecha_vigencia") or None, afecta_a=req.f("afecta_a"), que_cambia=req.f("que_cambia"))
    raise ir("/radar", ok="Novedad agregada." if nuevo else "Esa novedad ya estaba registrada.")


@ruta("POST", r"/radar/(?P<rid>\d+)/(?P<accion>verificar|descartar|rumor)")
def accion_radar(req: Peticion, rid: str, accion: str):
    if accion == "verificar":
        radar.verificar(req.cx, int(rid), "Didi")
    else:
        radar.descartar(req.cx, int(rid), "Didi", rumor=accion == "rumor")
    raise ir("/radar", ok="Radar actualizado.")


# --------------------------------------------------------------------------------------------- Productos

@ruta("GET", "/productos")
def lista_productos(req: Peticion) -> str:
    filas = [[f'<a href="/productos/{e(p["slug"])}">{e(p["nombre_provisional"])}</a>', e(p["sector"]), chip(p["etapa_comercial"]),
              "sí" if p["disponible_al_publico"] else "no", e(p["precio"] or "sin definir"), e(p["commit_auditado"] or ""),
              e(p["fecha_auditoria"] or "")] for p in req.cx.execute("SELECT * FROM producto ORDER BY slug")]
    cuerpo = tabla(["Producto", "Sector", "Etapa", "Disponible", "Precio", "Commit auditado", "Auditado el"], filas) + \
        "<p>Para agregar un producto, crea su carpeta en <code>productos/</code> y ejecuta <code>python -m mos iniciar</code>.</p>"
    return pagina(req, "Productos", cuerpo)


@ruta("GET", r"/productos/(?P<slug>[a-z0-9-]+)")
def ver_producto(req: Peticion, slug: str) -> str:
    p = req.cx.execute("SELECT * FROM producto WHERE slug = ?", (slug,)).fetchone()
    if p is None:
        raise KeyError(f"No existe el producto «{slug}».")
    uso = req.q("uso")
    sql, params = "SELECT * FROM capacidad WHERE producto_id = ?", [p["id"]]
    if uso:
        sql += " AND uso = ?"
        params.append(uso)
    caps = req.cx.execute(sql + " ORDER BY codigo", params).fetchall()
    filas = [[f"<code>{e(c['codigo'])}</code>", e(c["nombre"]), chip(c["estado"]), chip(c["uso"]), e(c["frase"] or ""),
              e(c["matiz"] or ""), f"<small>{e(c['evidencia'])}</small>"] for c in caps]
    filtro = " ".join(f'<a class="chip {"lima" if u == uso else "gris"}" href="/productos/{e(slug)}{"?uso=" + u if u else ""}">'
                      f'{e(u.lower().replace("_", " ") or "todas")}</a>' for u in ("", "PERMITIDO", "CON_MATICES", "SOLO_DEMO", "NO_ANUNCIAR"))
    prohib = [[e(x["patron"]), e(x["motivo"])] for x in req.cx.execute("SELECT * FROM prohibicion WHERE producto_id = ?", (p["id"],))]
    auds = [[e(a["nombre"]), chip(a["naturaleza"], "ambar"), e(a["descripcion"])]
            for a in req.cx.execute("SELECT * FROM audiencia WHERE producto_id = ?", (p["id"],))]
    problemas = "".join(f"<li>{e(x)}</li>" for x in util.de_json(p["problemas"], []))
    cuerpo = f"""<p>{chip(p['etapa_comercial'])} · {e(p['sector'])} · auditado en el commit <code>{e(p['commit_auditado'])}</code>
      el {e(p['fecha_auditoria'])}</p><div class="dos"><div><h2>Propuesta de valor</h2><p>{e(p['propuesta_valor'])}</p>
      <h2>Problemas que resuelve</h2><ul>{problemas}</ul></div><div><h2>Audiencias</h2>{tabla(["Audiencia", "Naturaleza", "Descripción"], auds)}</div></div>
      <h2>Matriz de capacidades</h2><p>{filtro}</p>{tabla(["Código", "Capacidad", "Estado", "Uso", "Frase", "Matiz", "Evidencia"], filas)}
      <h2>Prohibiciones globales</h2>{tabla(["Patrón", "Motivo"], prohib)}"""
    return pagina(req, p["nombre_provisional"], cuerpo, "La matriz se edita en el archivo capacidades.toml, con evidencia y fecha.")


# ------------------------------------------------------------------------------------------ Herramientas

@ruta("GET", "/herramientas")
def lista_herramientas(req: Peticion) -> str:
    decision = req.q("decision")
    sql, params = "SELECT * FROM herramienta", []
    if decision:
        sql += " WHERE decision = ?"
        params.append(decision)
    hs = req.cx.execute(sql + " ORDER BY categoria, decision, nombre", params).fetchall()
    filas = [[f'<a href="{e(h["url"])}">{e(h["nombre"])}</a>' + ("<br>" + chip("requiere autorización", "rojo") if h["requiere_autorizacion"] else ""),
              e(h["categoria"]), e(h["funcion"]), e(h["coste"]), e(h["licencia"]), f"<small>{e(h['limites'])}</small>",
              chip(h["decision"]), f"<small>{e(h['verificacion'])} · {e(h['verificado_en'])}</small>"] for h in hs]
    filtro = " ".join(f'<a class="chip {"lima" if d == decision else "gris"}" href="/herramientas{"?decision=" + d if d else ""}">'
                      f'{e(d.lower() or "todas")}</a>' for d in ("", "ADOPTAR", "PROBAR", "RESERVAR", "DESCARTAR"))
    cuerpo = f"<p>{filtro}</p>" + tabla(["Herramienta", "Categoría", "Función", "Coste", "Licencia", "Límites", "Decisión", "Verificación"],
                                        filas, "El registro de herramientas está vacío. Ejecuta python -m mos iniciar.")
    return pagina(req, "Herramientas", cuerpo, "Detalle completo en docs/REGISTRO-HERRAMIENTAS-Y-COSTES.md.")


# ----------------------------------------------------------------------------------------------- Errores

@ruta("GET", "/errores")
def lista_errores(req: Peticion) -> str:
    errs = req.cx.execute("SELECT * FROM registro_error WHERE resuelto = 0 ORDER BY id DESC LIMIT 200").fetchall()
    filas = [[e(x["en"]), e(x["modulo"]), e(x["codigo"]), e(x["mensaje"]), f"<small>{e(x['detalle'][:400])}</small>",
              boton(f"/errores/{x['id']}/resolver", "Resuelto", "/errores")] for x in errs]
    return pagina(req, "Errores sin resolver", tabla(["Cuándo", "Módulo", "Código", "Mensaje", "Detalle", ""], filas,
                                                     "No hay errores sin resolver."))


@ruta("POST", r"/errores/(?P<eid>\d+)/resolver")
def resolver_error(req: Peticion, eid: str):
    with db.transaccion(req.cx):
        req.cx.execute("UPDATE registro_error SET resuelto = 1 WHERE id = ?", (int(eid),))
        db.auditar(req.cx, "Didi", "registro_error", int(eid), "RESOLVER")
    raise ir("/errores", ok="Marcado como resuelto.")


# --------------------------------------------------------------------------------------- archivos y WSGI

def _estatico(cfg: config.Config, ruta_: str) -> tuple[bytes, str] | None:
    if ruta_ == "/estilo.css":
        return resources.files("mos.web").joinpath("estilo.css").read_bytes(), "text/css; charset=utf-8"
    bases = {"/recursos/": cfg.raiz / "recursos", "/marcas/": cfg.raiz / "marcas", "/archivos/": cfg.espacio}
    for prefijo, base in bases.items():
        if ruta_.startswith(prefijo):
            relativo = ruta_[len(prefijo):]
            destino = (base / relativo).resolve()
            if not destino.is_relative_to(base.resolve()) or not destino.is_file():
                return None
            if prefijo == "/archivos/" and destino.suffix.lower() in (".db", ".db-wal", ".db-shm", ".csv", ".json"):
                return None   # la base y los archivos con datos personales no se sirven por web
            tipo = mimetypes.guess_type(destino.name)[0] or "application/octet-stream"
            return destino.read_bytes(), tipo
    return None


def crear_app(cfg: config.Config):
    cfg.espacio.mkdir(parents=True, exist_ok=True)
    cx0 = db.conectar(cfg.base)
    db.migrar(cx0)
    cx0.close()

    def app(environ, start_response):
        host = (environ.get("HTTP_HOST") or "").rsplit(":", 1)[0].strip("[]")
        if host not in HOSTS_LOCALES:
            start_response("403 Forbidden", [("Content-Type", "text/plain; charset=utf-8")])
            return ["Solo se atiende desde esta PC (127.0.0.1).".encode("utf-8")]
        ruta_ = environ.get("PATH_INFO", "/")
        cabeceras_seguras = [("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"),
                             ("Referrer-Policy", "no-referrer"), ("Cache-Control", "no-store")]
        if environ["REQUEST_METHOD"] == "GET":
            estatico = _estatico(cfg, ruta_)
            if estatico:
                cuerpo, tipo = estatico
                start_response("200 OK", [("Content-Type", tipo), ("X-Content-Type-Options", "nosniff")])
                return [cuerpo]
        cx = db.conectar(cfg.base)
        req = None
        try:
            req = Peticion(environ, cfg, cx)
            if req.metodo == "POST" and not secrets.compare_digest(req.f("_token"), TOKEN):
                start_response("403 Forbidden", [("Content-Type", "text/plain; charset=utf-8")])
                return ["Formulario vencido: recarga la página e inténtalo otra vez.".encode("utf-8")]
            for metodo, patron, fn in RUTAS:
                m = patron.match(req.ruta)
                if m and metodo == req.metodo:
                    try:
                        html_ = fn(req, **m.groupdict())
                    except ERRORES_DE_NEGOCIO as ex:
                        if req.metodo == "POST":
                            raise ir(req.volver, error=str(ex).strip("'\""))
                        html_ = pagina(req, "No se pudo mostrar", f'<div class="aviso error">{e(str(ex))}</div>'
                                                                   '<p><a href="/">Volver a Hoy</a></p>')
                    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), *cabeceras_seguras])
                    return [html_.encode("utf-8")]
            start_response("404 Not Found", [("Content-Type", "text/html; charset=utf-8"), *cabeceras_seguras])
            return [pagina(req, "No encontrado", '<p>Esa página no existe. <a href="/">Volver a Hoy</a></p>').encode("utf-8")]
        except Redirigir as r:
            start_response("303 See Other", [("Location", r.url), *cabeceras_seguras])
            return [b""]
        except Exception as ex:  # error inesperado: mensaje humano y rastro en la base
            try:
                db.registrar_error(cx, "web", type(ex).__name__, str(ex), traceback.format_exc())
            except Exception:
                pass
            start_response("500 Internal Server Error", [("Content-Type", "text/html; charset=utf-8"), *cabeceras_seguras])
            cuerpo = (f'<div class="aviso error">Algo falló: {e(ex)}</div><p>Quedó registrado en '
                      f'<a href="/errores">Errores</a>. <a href="/">Volver a Hoy</a></p>')
            return [(pagina(req, "Error", cuerpo) if req else e(ex)).encode("utf-8")]
        finally:
            cx.close()

    return app


class _Silencioso(WSGIRequestHandler):
    def log_message(self, formato, *args):  # sin registro de cada petición en la consola
        pass


def servir(cfg: config.Config, abrir: bool = True) -> None:
    app = crear_app(cfg)
    with make_server("127.0.0.1", cfg.puerto_web, app, handler_class=_Silencioso) as servidor:
        url = f"http://127.0.0.1:{cfg.puerto_web}/"
        print(f"Panel en {url} (solo en esta PC). Ctrl+C para cerrar.")
        if abrir:
            webbrowser.open(url)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nPanel cerrado.")
