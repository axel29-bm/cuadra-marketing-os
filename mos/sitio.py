"""La landing de la lista de espera: se construye desde sitio/sitio.toml, se audita y se prueba en esta PC.

`construir` arma una carpeta de HTML estático (página, aviso de privacidad, trivia interactiva, script del formulario,
fuentes y logo) después de pasar cada texto por el auditor; las capacidades se citan por código y su frase sale de la
matriz del producto. `pendientes_para_publicar` dice qué falta para ponerla en Internet y, con `publicable=True`, la
construcción se niega si falta algo. `servir` la muestra en http://127.0.0.1:8766 con un receptor local que valida
igual que el de Cloudflare (sitio/receptor/worker.js) y guarda cada inscripción en la base con su consentimiento.
`importar_remoto` trae las inscripciones del receptor publicado a la base local y las borra del servidor.
"""

from __future__ import annotations

import copy
import csv
import glob
import io
import json
import re
import shutil
import sqlite3
import tomllib
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from wsgiref.simple_server import WSGIRequestHandler, make_server

from . import campanas, leads, util
from .calidad import auditor as aud
from .config import Config

PUERTO_LOCAL = 8766
RE_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
MAX_CUERPO = 10_000

# Textos del formulario por código de respuesta (el receptor devuelve códigos; la página los traduce).
TEXTOS_FORMULARIO = {
    "GRACIAS": "", "DATOS_INCOMPLETOS": "Escribe tu nombre y un correo válido.",
    "CORREO_INVALIDO": "Revisa tu correo: parece que le falta algo.",
    "SIN_CONSENTIMIENTO": "Para anotarte necesitamos que marques la casilla del aviso de privacidad.",
    "DEMASIADOS_ENVIOS": "Recibimos varios envíos desde tu conexión. Intenta de nuevo en una hora.",
    "ERROR": "No se pudo enviar. Intenta otra vez o escríbenos «BETA» por mensaje.",
}


class ErrorSitio(ValueError):
    pass


@dataclass
class Resultado:
    archivos: list[Path] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    pendientes: list[str] = field(default_factory=list)


def leer(raiz: Path) -> dict:
    ruta = raiz / "sitio" / "sitio.toml"
    if not ruta.exists():
        raise ErrorSitio(f"No encuentro {ruta}.")
    return tomllib.loads(ruta.read_text(encoding="utf-8"))


def _capacidades(raiz: Path, producto: str) -> dict[str, dict]:
    matriz = tomllib.loads((raiz / "productos" / producto / "capacidades.toml").read_text(encoding="utf-8"))
    return {c["codigo"]: c for c in matriz["capacidad"]}


def _resolver(datos: dict, caps: dict[str, dict]) -> dict:
    """Pone la frase de la matriz en cada capacidad citada. Solo entran las que se pueden afirmar."""
    d = copy.deepcopy(datos)
    for seccion in ("ya_hace", "matices"):
        for c in d[seccion]["capacidades"]:
            cap = caps.get(c["codigo"])
            if cap is None:
                raise ErrorSitio(f"La capacidad {c['codigo']} de «{seccion}» no existe en la matriz.")
            if cap["uso"] not in ("PERMITIDO", "CON_MATICES"):
                raise ErrorSitio(f"{c['codigo']} ({cap['nombre']}) no se puede anunciar: su uso es {cap['uso']}.")
            if seccion == "ya_hace" and cap["uso"] != "PERMITIDO":
                raise ErrorSitio(f"{c['codigo']} tiene matices: va en la sección «matices», con su nota.")
            c["frase"] = cap["frase"]
    return d


def revisar(raiz: Path, datos: dict) -> list[tuple[str, aud.Informe]]:
    """Audita la landing por secciones, cada una con su tipo de afirmación y las capacidades que cita."""
    d = _resolver(datos, _capacidades(raiz, datos["producto"]))
    politica = aud.Politica.desde_carpeta(raiz / "productos" / datos["producto"])
    p, cta = d["pagina"], d["pagina"]["cta"]
    codigos = lambda lista: [c["codigo"] if isinstance(c, dict) else c for c in lista]
    secciones = [
        ("pagina", "CAPTACION", {k: p[k] for k in ("titulo", "descripcion", "antetitulo", "titular", "subtitulo",
                                                    "cta_mensaje", "estado")}, p.get("capacidades", [])),
        ("ya_hace", "CAPTACION", {"titulo": d["ya_hace"]["titulo"]} | {f"capacidad[{i}]": c["frase"] for i, c in
                                                                        enumerate(d["ya_hace"]["capacidades"])},
         codigos(d["ya_hace"]["capacidades"])),
        ("matices", "CAPTACION", {"titulo": d["matices"]["titulo"], "texto": d["matices"]["texto"]}
         | {f"capacidad[{i}]": f"{c['frase']} {c['nota']}" for i, c in enumerate(d["matices"]["capacidades"])},
         codigos(d["matices"]["capacidades"])),
        ("todavia_no", "DESARROLLO", {"titulo": d["todavia_no"]["titulo"], "texto": d["todavia_no"]["texto"]},
         d["todavia_no"].get("capacidades", [])),
        ("beta", "CAPTACION", {"titulo": d["beta"]["titulo"]} | {f"punto[{i}]": t for i, t in enumerate(d["beta"]["puntos"])},
         d["beta"].get("capacidades", [])),
        ("demo", "CAPTACION", {k: d["demo"][k] for k in ("titulo", "texto", "cta")}, d["demo"].get("capacidades", [])),
        ("trivia", "EDUCATIVA", {k: d["trivia"][k] for k in ("titulo", "texto", "boton")}, []),
        ("formulario", "CAPTACION", {k: d["formulario"][k] for k in ("titulo", "texto", "consentimiento", "publicidad",
                                                                       "quiere_demo", "boton", "gracias", "sin_formulario")}, []),
        ("faq", "CAPTACION", {f"faq[{i}]": f"{f['pregunta']} {f['respuesta']}" for i, f in enumerate(d.get("faq", []))},
         sorted({c for f in d.get("faq", []) for c in f.get("capacidades", [])})),
    ]
    informes = []
    for nombre, tipo, textos, caps in secciones:
        pieza = aud.PiezaParaAuditar(tipo_afirmacion=tipo, canal="web", textos=textos, capacidades=list(caps),
                                     cta=cta if tipo == "CAPTACION" else "")
        informes.append((nombre, aud.auditar(pieza, politica)))
    return informes


def pendientes_para_publicar(datos: dict) -> list[str]:
    """Lo que falta antes de que la landing pueda estar en Internet. Vacío = se puede publicar (con tu autorización)."""
    pub, r = datos["publicacion"], datos["responsable"]
    faltan = []
    completar = sorted({k for k, v in r.items() if isinstance(v, str) and "[COMPLETAR" in v})
    if completar:
        faltan.append("Completa los datos del responsable en sitio.toml: " + ", ".join(completar))
    if not r.get("flujo_comunicado"):
        faltan.append("Comunica e inscribe el flujo transfronterizo de datos (Cloudflare) y marca flujo_comunicado = true")
    if not pub.get("aviso_validado"):
        faltan.append("Que un abogado revise el aviso de privacidad y las casillas, y marca aviso_validado = true")
    if "borrador" in pub.get("aviso_version", "") or not pub.get("aviso_version"):
        faltan.append("Pon una versión definitiva al aviso de privacidad (aviso_version sin «borrador»)")
    if not pub.get("url", "").startswith("https://"):
        faltan.append("Indica la dirección https donde vivirá la landing (publicacion.url)")
    if not pub.get("receptor", "").startswith("https://"):
        faltan.append("Despliega el receptor del formulario y pon su dirección https (publicacion.receptor)")
    return faltan


def _origen(url: str) -> str:
    partes = urlsplit(url)
    if partes.scheme in ("https", "http") and re.fullmatch(r"[A-Za-z0-9.-]+(:\d+)?", partes.netloc or ""):
        return f"{partes.scheme}://{partes.netloc}"
    return ""


def _trivia(raiz: Path, datos: dict) -> dict | None:
    carpeta = raiz / "campanas" / datos.get("campana", "")
    if not (carpeta / "campana.toml").exists():
        return None
    return next((p["contenido"] for p in campanas.leer(carpeta)["pieza"] if p.get("plantilla") == "trivia"), None)


def construir(raiz: Path, destino: Path | None = None, *, publicable: bool = False, receptor: str | None = None) -> Resultado:
    from .fabrica import marca as marcas
    from .fabrica import render

    datos = leer(raiz)
    res = Resultado(pendientes=pendientes_para_publicar(datos))
    if publicable and res.pendientes:
        raise ErrorSitio("Todavía no se puede publicar:\n- " + "\n- ".join(res.pendientes))
    bloqueos = []
    for seccion, informe in revisar(raiz, datos):
        for h in informe.hallazgos:
            (bloqueos if h.severidad == aud.BLOQUEANTE else res.avisos).append(f"{seccion}: {h.mensaje}")
    if bloqueos:
        raise ErrorSitio("El auditor frenó la landing:\n- " + "\n- ".join(bloqueos))

    d = _resolver(datos, _capacidades(raiz, datos["producto"]))
    pub, contacto = d["publicacion"], d.get("contacto", {})
    receptor = pub.get("receptor", "") if receptor is None else receptor
    if receptor and not (receptor.startswith("/") and not receptor.startswith("//")) and not _origen(receptor).startswith("https://"):
        raise ErrorSitio(f"El receptor debe ser una dirección https (o /api/lista en la prueba local): «{receptor}».")
    m = marcas.cargar(raiz, d.get("marca", "base"))
    env, Markup = render._entorno(raiz, raiz / "sitio" / "plantillas")
    env.filters["pendiente"] = lambda v: Markup(f'<span class="pendiente">{Markup.escape(v)}</span>') if "[COMPLETAR" in str(v) else v
    grosor = m["forma"].get("grosor_icono", 1.75)

    externos_script = ["https://static.cloudflareinsights.com"] if pub.get("analitica_token") else []
    externos_conexion = [o for o in [_origen(receptor)] if o] + (["https://cloudflareinsights.com"] if externos_script else [])
    csp = "; ".join([
        "default-src 'self'", "script-src " + " ".join(["'self'"] + externos_script),
        "style-src 'self' 'unsafe-inline'", "img-src 'self' data:", "font-src 'self' data:",
        "connect-src " + " ".join(["'self'"] + externos_conexion), "base-uri 'self'",
        "form-action " + " ".join(["'self'"] + [o for o in [_origen(receptor)] if o]),
    ])
    redes = [(n, contacto[k]) for k, n in (("facebook", "Facebook"), ("instagram", "Instagram"), ("linkedin", "LinkedIn"),
                                            ("tiktok", "TikTok")) if contacto.get(k, "").startswith("https://")]
    contexto = {
        **d, "p": d["pagina"], "r": d["responsable"], "url": pub.get("url", "").rstrip("/"), "receptor": receptor,
        "aviso_version": pub.get("aviso_version", ""), "analitica_token": pub.get("analitica_token", ""),
        "whatsapp": re.sub(r"\D", "", contacto.get("whatsapp", "")), "redes": redes, "csp": Markup(csp),
        "borrador": bool(res.pendientes), "motivo_borrador": f"faltan {len(res.pendientes)} cosas para publicarla "
                                                             "(python -m mos sitio pendientes).",
        "nombre_marca": m.get("nombre", ""), "logo": bool(m.get("logo")), "variables_css": Markup(marcas.variables_css(m)),
        "icono": lambda n: Markup(marcas.icono(raiz, n, grosor)),
        "textos": TEXTOS_FORMULARIO | {"GRACIAS": d["formulario"]["gracias"]},
    }
    destino = destino or raiz / "sitio" / "dist"
    if destino.exists():
        shutil.rmtree(destino)
    (destino / "fuentes").mkdir(parents=True)

    def escribir(nombre: str, texto: str) -> None:
        (destino / nombre).write_text(texto, encoding="utf-8")
        res.archivos.append(destino / nombre)

    escribir("index.html", env.get_template("index.html.j2").render(**contexto))
    escribir("privacidad.html", env.get_template("privacidad.html.j2").render(**contexto))
    if receptor:
        escribir("lista.js", env.get_template("lista.js.j2").render(**contexto))
    trivia = _trivia(raiz, d)
    if trivia:
        escribir("trivia.html", render.componer_interactivo(raiz, "trivia", trivia, marca=d.get("marca", "base")))
    # Sin publicar, que ningún buscador la indexe. Encabezados de seguridad para Cloudflare Pages.
    escribir("robots.txt", "User-agent: *\nDisallow: /\n" if res.pendientes else "User-agent: *\nAllow: /\n")
    escribir("_headers", "/*\n  X-Content-Type-Options: nosniff\n  X-Frame-Options: DENY\n  Referrer-Policy: strict-origin-when-cross-origin\n"
                         "  Permissions-Policy: camera=(), microphone=(), geolocation=()\n"
                         f"  Content-Security-Policy: {csp}; frame-ancestors 'none'\n")
    t = m["tipografia"]
    for clave in ("archivo_titulos", "archivo_mono"):
        origen = raiz / t[clave]
        shutil.copy2(origen, destino / "fuentes" / origen.name)
        res.archivos.append(destino / "fuentes" / origen.name)
    if m.get("logo"):
        shutil.copy2(raiz / m["logo"], destino / "logo.svg")
        res.archivos.append(destino / "logo.svg")
    imagen = sorted(glob.glob(str(raiz / d["pagina"].get("imagen_compartir", "")))) if d["pagina"].get("imagen_compartir") else []
    if imagen:
        shutil.copy2(imagen[-1], destino / "compartir.png")
        res.archivos.append(destino / "compartir.png")
    return res


# ------------------------------------------------------------------------------------------- inscripciones

def validar_envio(cuerpo) -> tuple[str | None, dict]:
    """Mismas reglas que sitio/receptor/worker.js. Devuelve (código de error o None, datos limpios).

    El código «TRAMPA» es un robot que llenó el campo oculto: se le responde como si todo estuviera bien.
    """
    if not isinstance(cuerpo, dict):
        return "DATOS_INCOMPLETOS", {}
    if str(cuerpo.get("sitio_web") or "").strip():
        return "TRAMPA", {}
    texto = lambda k, n: str(cuerpo.get(k) or "").strip()[:n]
    nombre, email = texto("nombre", 80), texto("email", 120).lower()
    if not nombre or not email:
        return "DATOS_INCOMPLETOS", {}
    if not RE_EMAIL.match(email):
        return "CORREO_INVALIDO", {}
    if cuerpo.get("consentimiento") is not True:
        return "SIN_CONSENTIMIENTO", {}
    version = texto("aviso_version", 40)
    if not version:
        return "DATOS_INCOMPLETOS", {}
    empresas = texto("empresas", 6)
    empresas_n = int(empresas) if empresas.isdigit() and 1 <= int(empresas) <= 5000 else None
    origen = cuerpo.get("origen") if isinstance(cuerpo.get("origen"), dict) else {}
    origen = {str(k)[:30]: str(v)[:200] for k, v in list(origen.items())[:6]}
    return None, {"nombre": nombre, "email": email, "empresas": empresas_n, "problema": texto("problema", 500),
                  "demo": cuerpo.get("demo") is True, "publicidad": cuerpo.get("publicidad") is True,
                  "aviso_version": version, "origen": origen}


def guardar_inscripcion(cx: sqlite3.Connection, datos_sitio: dict, ins: dict, *, fuente: str, medio: str,
                        fecha: str | None = None) -> tuple[str, bool]:
    """Registra una inscripción válida como lead con la prueba de su consentimiento. No duplica."""
    origen = " · ".join(f"{k}={v}" for k, v in ins.get("origen", {}).items())
    uid, nuevo = leads.registrar(
        cx, datos_sitio["producto"], fuente=fuente, email=ins["email"], nombre=ins["nombre"],
        problema_principal=ins.get("problema", ""), empresas_que_lleva=ins.get("empresas"), campana=datos_sitio.get("campana"),
        consentimiento=True, consentimiento_publicidad=ins.get("publicidad", False),
        finalidad=datos_sitio["formulario"]["finalidad"], consentimiento_version=ins["aviso_version"],
        consentimiento_medio=medio + (f" ({origen})" if origen else ""), consentimiento_en=fecha)
    if ins.get("demo"):
        leads.actualizar(cx, uid, proxima_accion="Pidió una demostración: escribirle para coordinar el día",
                         seguimiento_en=util.hoy_lima().isoformat(), por="landing")
    return uid, nuevo


def app_local(cfg: Config, carpeta: Path):
    """Sirve la landing construida y recibe el formulario en /api/lista, guardando en la base local."""
    from . import db
    datos_sitio = leer(cfg.raiz)

    def responder(start, estado: str, cuerpo: bytes, tipo: str):
        start(estado, [("Content-Type", tipo), ("Content-Length", str(len(cuerpo))), ("Cache-Control", "no-store"),
                       ("X-Content-Type-Options", "nosniff")])
        return [cuerpo]

    def app(environ, start):
        host = environ.get("HTTP_HOST", "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            return responder(start, "403 Forbidden", b"Solo en esta PC.", "text/plain; charset=utf-8")
        ruta = environ.get("PATH_INFO", "/")
        if ruta == "/api/lista":
            if environ["REQUEST_METHOD"] != "POST":
                return responder(start, "405 Method Not Allowed", b"{}", "application/json")
            largo = int(environ.get("CONTENT_LENGTH") or 0)
            if largo > MAX_CUERPO:
                return responder(start, "413 Payload Too Large", b'{"ok": false, "codigo": "ERROR"}', "application/json")
            try:
                cuerpo = json.loads(environ["wsgi.input"].read(largo) or b"{}")
            except ValueError:
                cuerpo = None
            codigo, ins = validar_envio(cuerpo)
            if codigo == "TRAMPA":
                return responder(start, "200 OK", b'{"ok": true}', "application/json")
            if codigo:
                return responder(start, "400 Bad Request", json.dumps({"ok": False, "codigo": codigo}).encode(), "application/json")
            cx = db.conectar(cfg.base)
            try:
                guardar_inscripcion(cx, datos_sitio, ins, fuente="landing-local", medio="formulario web (prueba local)")
            except leads.ErrorLead:
                return responder(start, "400 Bad Request", b'{"ok": false, "codigo": "DATOS_INCOMPLETOS"}', "application/json")
            finally:
                cx.close()
            return responder(start, "200 OK", b'{"ok": true}', "application/json")
        archivo = (carpeta / (ruta.lstrip("/") or "index.html")).resolve()
        if carpeta.resolve() not in archivo.parents or not archivo.is_file():
            return responder(start, "404 Not Found", b"No existe.", "text/plain; charset=utf-8")
        tipos = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
                 ".woff2": "font/woff2", ".png": "image/png", ".txt": "text/plain; charset=utf-8"}
        return responder(start, "200 OK", archivo.read_bytes(), tipos.get(archivo.suffix, "application/octet-stream"))

    return app


class _Silencioso(WSGIRequestHandler):
    def log_message(self, *args) -> None:
        pass


def servir(cfg: Config, puerto: int = PUERTO_LOCAL, abrir: bool = True) -> None:
    from . import db
    cx = db.conectar(cfg.base)
    db.migrar(cx)
    cx.close()
    carpeta = cfg.espacio / "sitio-local"
    res = construir(cfg.raiz, carpeta, receptor="/api/lista")
    url = f"http://127.0.0.1:{puerto}/"
    print(f"Landing de prueba en {url} · lo que envíes queda en tu base local (pantalla Leads del panel).")
    for aviso in res.avisos:
        print("Aviso: " + aviso)
    with make_server("127.0.0.1", puerto, app_local(cfg, carpeta), handler_class=_Silencioso) as servidor:
        if abrir:
            webbrowser.open(url)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nLanding detenida.")


# ------------------------------------------------------------------------------------------- receptor publicado

def _pedir(url: str, clave: str, cuerpo: dict | None = None) -> bytes:
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
        raise ErrorSitio("El receptor debe usar https.")
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(url, data=datos, method="POST" if datos else "GET",
                                      headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=30) as r:
        return r.read()


def importar_remoto(cx: sqlite3.Connection, cfg: Config, receptor: str, clave: str, *, borrar: bool = True) -> dict[str, int]:
    """Trae las inscripciones del receptor publicado a la base local y, si todas entraron bien, las borra del servidor.

    La clave se lee de una variable de entorno (MOS_CLAVE_LISTA); nunca se guarda en archivos.
    """
    if not clave:
        raise ErrorSitio("Falta la clave del receptor: define la variable de entorno MOS_CLAVE_LISTA.")
    datos_sitio = leer(cfg.raiz)
    base = receptor.rstrip("/")
    texto = _pedir(base + "/exportar", clave).decode("utf-8-sig")
    conteo = {"nuevos": 0, "actualizados": 0, "invalidos": 0, "borrados": 0}
    correos = []
    for fila in csv.DictReader(io.StringIO(texto)):
        try:
            origen = json.loads(fila.get("origen") or "{}")
        except ValueError:
            origen = {}
        codigo, ins = validar_envio({**fila, "consentimiento": fila.get("consentimiento") == "1", "origen": origen,
                                     "publicidad": fila.get("publicidad") == "1", "demo": fila.get("demo") == "1",
                                     "sitio_web": ""})
        if codigo:
            conteo["invalidos"] += 1
            continue
        try:
            _, nuevo = guardar_inscripcion(cx, datos_sitio, ins, fuente="landing", medio="formulario web",
                                           fecha=fila.get("creado_en") or None)
        except leads.ErrorLead:
            conteo["invalidos"] += 1
            continue
        conteo["nuevos" if nuevo else "actualizados"] += 1
        correos.append(ins["email"])
    if borrar and correos and not conteo["invalidos"]:
        respuesta = json.loads(_pedir(base + "/borrar", clave, {"emails": correos}) or b"{}")
        conteo["borrados"] = int(respuesta.get("borrados", 0))
    return conteo
