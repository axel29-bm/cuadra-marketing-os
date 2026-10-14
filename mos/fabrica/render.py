"""Fábrica de piezas: plantilla HTML/CSS + textos de la pieza → PNG, PDF, MP4 y paquete de guion.

El flujo es siempre el mismo y no depende de servicios externos:
1. `validar` revisa los campos contra plantilla.toml (obligatorios, largo máximo, número de láminas).
2. `componer` arma el HTML con la identidad de la marca incrustada (fuentes, iconos y logo en línea).
3. `Navegador` lo abre en Chromium o Edge con Playwright, espera a que el texto quepa y guarda la imagen,
   el PDF o los fotogramas que FFmpeg convierte en vídeo.
4. `exportar_pieza` hace todo lo anterior para una pieza y registra cada archivo en la tabla `activo`.
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .. import contenido, db, util
from ..config import Config
from . import marca as marcas
from . import plantillas

FORMATOS = {
    "cuadrado": (1080, 1080),     # feed de Facebook, Instagram y LinkedIn
    "vertical": (1080, 1350),     # feed 4:5, el que más pantalla ocupa en el celular
    "historia": (1080, 1920),     # historias, reels, TikTok y shorts
    "horizontal": (1920, 1080),   # YouTube y vídeo en LinkedIn
    "enlace": (1200, 627),        # vista previa de enlaces y portada de documento en LinkedIn
}


class ErrorFabrica(ValueError):
    pass


# ------------------------------------------------------------------------------------------- validación

def _sin_marcas(texto: str) -> str:
    return texto.replace("*", "")


def _validar_campos(campos: dict, datos: dict, raiz: Path, prefijo: str = "") -> list[str]:
    problemas = []
    for nombre, regla in campos.items():
        etiqueta = f"{prefijo}{nombre}"
        valor = datos.get(nombre)
        vacio = valor is None or valor == "" or valor == []
        if vacio:
            if regla.get("requerido"):
                problemas.append(f"{etiqueta}: falta y es obligatorio")
            continue
        tipo = regla.get("tipo", "texto")
        if tipo in ("texto", "texto_largo"):
            if not isinstance(valor, str):
                problemas.append(f"{etiqueta}: debe ser texto")
            elif "max" in regla and len(_sin_marcas(valor)) > regla["max"]:
                problemas.append(f"{etiqueta}: tiene {len(_sin_marcas(valor))} caracteres y el máximo es {regla['max']}")
        elif tipo == "lista":
            if not isinstance(valor, list) or not all(isinstance(x, str) for x in valor):
                problemas.append(f"{etiqueta}: debe ser una lista de textos")
                continue
            if len(valor) < regla.get("min", 0) or len(valor) > regla.get("max_items", 99):
                problemas.append(f"{etiqueta}: lleva {len(valor)} elementos; se permiten de {regla.get('min', 0)} a {regla.get('max_items', 99)}")
            for i, x in enumerate(valor, 1):
                if "max" in regla and len(_sin_marcas(x)) > regla["max"]:
                    problemas.append(f"{etiqueta}[{i}]: tiene {len(_sin_marcas(x))} caracteres y el máximo es {regla['max']}")
        elif tipo == "opcion":
            if valor not in regla.get("valores", []):
                problemas.append(f"{etiqueta}: «{valor}» no es válido; usa {', '.join(regla.get('valores', []))}")
        elif tipo == "entero":
            if not isinstance(valor, int) or not regla.get("min", -10**9) <= valor <= regla.get("max", 10**9):
                problemas.append(f"{etiqueta}: debe ser un número entero entre {regla.get('min')} y {regla.get('max')}")
        elif tipo == "icono":
            try:
                marcas.icono(raiz, valor)
            except KeyError as ex:
                problemas.append(f"{etiqueta}: {ex.args[0]}")
        elif tipo == "captura":
            if not isinstance(valor, str) or not _ruta_captura(raiz, valor):
                problemas.append(f"{etiqueta}: no encuentro la captura «{valor}». Guárdala en espacio/capturas o recursos/capturas.")
        elif tipo == "objetos":
            if not isinstance(valor, list) or not all(isinstance(x, dict) for x in valor):
                problemas.append(f"{etiqueta}: debe ser una lista de objetos")
                continue
            if len(valor) < regla.get("min", 0) or len(valor) > regla.get("max_items", 99):
                problemas.append(f"{etiqueta}: lleva {len(valor)} elementos; se permiten de {regla.get('min', 0)} a {regla.get('max_items', 99)}")
            for i, item in enumerate(valor, 1):
                problemas += _validar_campos(regla.get("campos", {}), item, raiz, f"{etiqueta}[{i}].")
    return problemas


def validar(raiz: Path, nombre: str, datos: dict) -> list[str]:
    ficha = plantillas.ficha(raiz, nombre)
    return _validar_campos(ficha.get("campos", {}), datos, raiz)


_ESPACIO_CAPTURAS: list[Path] = []


def _ruta_captura(raiz: Path, valor: str) -> Path | None:
    for base in (*_ESPACIO_CAPTURAS, raiz / "recursos" / "capturas"):
        ruta = (base / valor).resolve()
        if ruta.is_relative_to(base.resolve()) and ruta.is_file():
            return ruta
    return None


def paginas(raiz: Path, nombre: str, datos: dict) -> int:
    ficha = plantillas.ficha(raiz, nombre)
    pag = ficha.get("paginas", 1)
    return len(datos.get(pag) or []) if isinstance(pag, str) else int(pag)


# ------------------------------------------------------------------------------------------- HTML

def _entorno(raiz: Path):
    try:
        import jinja2
    except ImportError as ex:
        raise ErrorFabrica("Falta la fábrica de contenidos. Instálala con: python -m pip install -r requirements.txt") from ex
    from markupsafe import Markup, escape

    def resaltar(texto) -> Markup:
        """Escapa el texto y convierte *palabras* en resaltado de marca."""
        seguro = str(escape(texto or ""))
        seguro = re.sub(r"\*(.+?)\*", r"<mark>\1</mark>", seguro)
        return Markup(seguro.replace("\n", "<br>"))

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(raiz / "plantillas")), autoescape=True,
                             trim_blocks=True, lstrip_blocks=True)
    env.filters["resaltar"] = resaltar
    env.filters["sin_marcas"] = lambda t: _sin_marcas(t or "")
    return env, Markup


def componer(raiz: Path, nombre: str, datos: dict, *, formato: str, marca: str = "base", pagina: int = 0,
             vista_previa: bool = False) -> str:
    ficha = plantillas.ficha(raiz, nombre)
    if formato not in ficha.get("formatos", []):
        raise ErrorFabrica(f"La plantilla «{nombre}» no tiene el formato «{formato}». Tiene: {', '.join(ficha.get('formatos', []))}")
    ancho, alto = FORMATOS[formato]
    m = marcas.cargar(raiz, marca)
    env, Markup = _entorno(raiz)
    grosor = m["forma"].get("grosor_icono", 1.75)

    def icono(nombre_icono: str) -> Markup:
        return Markup(marcas.icono(raiz, nombre_icono, grosor))

    def captura(valor: str) -> str:
        ruta = _ruta_captura(raiz, valor)
        return marcas.data_uri(ruta) if ruta else ""

    total = paginas(raiz, nombre, datos)
    contexto = {
        **datos, "d": datos, "ficha": ficha, "formato": formato, "ancho": ancho, "alto": alto,
        "u": round(min(ancho, alto) / 1080 * (1.2 if alto / ancho > 1.6 else 1), 4), "horizontal": ancho > alto, "pagina": pagina, "paginas": total,
        "marca": m, "nombre_marca": m.get("nombre", ""), "logo": marcas.logo(raiz, m),
        "fuentes_css": Markup(marcas.fuentes_css(raiz, marca)), "variables_css": Markup(marcas.variables_css(m)),
        "icono": icono, "captura": captura, "vista_previa": vista_previa,
    }
    return env.get_template(f"{nombre}/plantilla.html.j2").render(**contexto)


def componer_interactivo(raiz: Path, nombre: str, datos: dict, *, marca: str = "base") -> str:
    """Versión HTML interactiva (por ejemplo, la trivia que se responde con un clic en la landing)."""
    m = marcas.cargar(raiz, marca)
    env, Markup = _entorno(raiz)
    return env.get_template(f"{nombre}/interactivo.html.j2").render(
        **datos, d=datos, marca=m, nombre_marca=m.get("nombre", ""), logo=marcas.logo(raiz, m),
        fuentes_css=Markup(marcas.fuentes_css(raiz, marca)), variables_css=Markup(marcas.variables_css(m)),
        icono=lambda n: Markup(marcas.icono(raiz, n, m["forma"].get("grosor_icono", 1.75))))


# ------------------------------------------------------------------------------------------- navegador

def ffmpeg() -> str:
    ruta = os.environ.get("MOS_FFMPEG") or shutil.which("ffmpeg")
    if not ruta:
        raise ErrorFabrica("No encuentro FFmpeg. En Windows: winget install Gyan.FFmpeg (y abre una consola nueva).")
    return ruta


class Navegador:
    """Chromium o Edge sin ventana, controlado por Playwright. Se abre una vez y renderiza muchas piezas."""

    def __enter__(self) -> "Navegador":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as ex:
            raise ErrorFabrica("Falta Playwright. Instálalo con: python -m pip install -r requirements.txt") from ex
        self._pw = sync_playwright().start()
        ejecutable = os.environ.get("MOS_NAVEGADOR")
        intentos = [{"executable_path": ejecutable}] if ejecutable else []
        if os.name == "nt":
            intentos.append({"channel": "msedge"})
        intentos.append({})
        ultimo = None
        for opciones in intentos:
            try:
                self.navegador = self._pw.chromium.launch(**opciones)
                return self
            except Exception as ex:  # se prueba la siguiente opción
                ultimo = ex
        self._pw.stop()
        raise ErrorFabrica("No se pudo abrir un navegador para renderizar. En Windows se usa Microsoft Edge; si no lo "
                           "tienes, ejecuta: python -m playwright install chromium. Detalle: " + str(ultimo).splitlines()[0])

    def __exit__(self, *exc) -> None:
        self.navegador.close()
        self._pw.stop()

    def _abrir(self, html: str, ancho: int, alto: int):
        pagina = self.navegador.new_page(viewport={"width": ancho, "height": alto}, device_scale_factor=1)
        pagina.set_content(html, wait_until="load")
        pagina.wait_for_function("window.__listo === true", timeout=20000)
        return pagina

    def imagen(self, html: str, ancho: int, alto: int, destino: Path) -> dict:
        pagina = self._abrir(html, ancho, alto)
        try:
            cabe = pagina.evaluate("window.__cabe !== false")
            destino.parent.mkdir(parents=True, exist_ok=True)
            pagina.screenshot(path=str(destino), type="png", clip={"x": 0, "y": 0, "width": ancho, "height": alto})
            return {"cabe": cabe}
        finally:
            pagina.close()

    def pdf(self, imagenes: list[Path], ancho: int, alto: int, destino: Path) -> None:
        """Une láminas ya renderizadas en un PDF de una página por lámina (carrusel de documento en LinkedIn)."""
        cuerpo = "".join(f'<img src="{marcas.data_uri(p)}">' for p in imagenes)
        html = (f"<!doctype html><html><head><style>@page {{ size: {ancho}px {alto}px; margin: 0 }} html, body {{ margin: 0 }}"
                f"img {{ display: block; width: {ancho}px; height: {alto}px; page-break-after: always }}"
                f"img:last-child {{ page-break-after: auto }}</style></head><body>{cuerpo}"
                "<script>window.__listo = true</script></body></html>")
        pagina = self._abrir(html, ancho, alto)
        try:
            pagina.pdf(path=str(destino), width=f"{ancho}px", height=f"{alto}px", print_background=True,
                       margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        finally:
            pagina.close()

    def video(self, html: str, ancho: int, alto: int, destino: Path, fps: int = 30, audio: Path | None = None) -> dict:
        """Recorre la línea de tiempo de la plantilla fotograma a fotograma y la codifica en MP4 (H.264)."""
        pagina = self._abrir(html, ancho, alto)
        try:
            duracion = float(pagina.evaluate("window.duracion"))
            if not 0 < duracion <= 180:
                raise ErrorFabrica(f"La duración del vídeo ({duracion} s) debe estar entre 0 y 180 segundos.")
            destino.parent.mkdir(parents=True, exist_ok=True)
            orden = [ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", str(fps),
                     "-i", "-"]
            if audio:
                orden += ["-i", str(audio)]
            orden += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20", "-r", str(fps)]
            if audio:
                orden += ["-c:a", "aac", "-b:a", "160k", "-shortest"]
            orden += ["-movflags", "+faststart", str(destino)]
            proceso = subprocess.Popen(orden, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            cuadros = int(round(duracion * fps))
            try:
                for i in range(cuadros):
                    pagina.evaluate("t => window.escena(t)", i / fps)
                    proceso.stdin.write(pagina.screenshot(type="jpeg", quality=92,
                                                          clip={"x": 0, "y": 0, "width": ancho, "height": alto}))
            finally:
                proceso.stdin.close()
                error = proceso.stderr.read().decode("utf-8", "replace")
                proceso.stderr.close()
                proceso.wait()
            if proceso.returncode != 0:
                raise ErrorFabrica(f"FFmpeg no pudo crear el vídeo: {error.strip()[:400]}")
            return {"duracion_ms": int(duracion * 1000), "cuadros": cuadros}
        finally:
            pagina.close()


# ------------------------------------------------------------------------------------------- guion

def _tiempo_srt(segundos: float) -> str:
    ms = int(round(segundos * 1000))
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def paquete_guion(datos: dict, titulo: str) -> dict[str, str]:
    """Del guion por escenas saca: texto para leer en voz alta, subtítulos SRT y un teleprompter HTML."""
    escenas = datos.get("escenas") or []
    md = [f"# Guion · {titulo}", "", "Lee a ritmo de conversación. Las pausas marcan cambio de escena.", ""]
    srt, inicio = [], 0.0
    for i, esc in enumerate(escenas, 1):
        seg = float(esc.get("segundos", 3))
        locucion = (esc.get("locucion") or "").strip()
        palabras = len(locucion.split())
        ritmo = f" · {palabras} palabras, unas {round(palabras / seg * 60) if seg else 0} por minuto" if locucion else ""
        md += [f"## Escena {i} · {seg:g} s{ritmo}", "", f"**En pantalla:** {_sin_marcas(esc.get('pantalla', ''))}", "",
               f"**Voz:** {locucion or '(sin voz, solo música o silencio)'}", ""]
        if locucion:
            srt += [str(len(srt) // 4 + 1), f"{_tiempo_srt(inicio)} --> {_tiempo_srt(inicio + seg)}", locucion, ""]
        inicio += seg
    md += [f"Duración total: {inicio:g} segundos. Más de 160 palabras por minuto suele sonar apurado."]
    lineas = "".join(f"<p>{_escape(e.get('locucion') or '')}</p><hr>" for e in escenas if e.get("locucion"))
    tele = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Teleprompter · {_escape(titulo)}</title>
<style>body{{margin:0;background:#0B1626;color:#F2F6EE;font:600 56px/1.45 'Segoe UI',system-ui,sans-serif}}
#t{{padding:40vh 8vw;transform:scaleX(var(--espejo,1))}}hr{{border:0;border-top:2px solid #D4FF3F;opacity:.5;margin:1.2em 0}}
#c{{position:fixed;top:0;left:0;right:0;padding:8px 16px;font:14px system-ui;background:#000a}}</style></head><body>
<div id="c">Espacio: iniciar o pausar · flechas: velocidad · E: espejo · Inicio: volver arriba</div><div id="t">{lineas}</div>
<script>let v=0,on=false,last=null;function f(ts){{if(on&&last!==null)scrollBy(0,v*(ts-last)/16);last=ts;requestAnimationFrame(f)}}
v=1.2;requestAnimationFrame(f);addEventListener('keydown',e=>{{if(e.code==='Space'){{on=!on;e.preventDefault()}}
if(e.key==='ArrowUp')v+=.2;if(e.key==='ArrowDown')v=Math.max(.2,v-.2);if(e.key==='Home')scrollTo(0,0);
if(e.key==='e'||e.key==='E')document.body.style.setProperty('--espejo',getComputedStyle(document.body).getPropertyValue('--espejo')==='-1'?'1':'-1')}})</script>
</body></html>"""
    return {"guion.md": "\n".join(md) + "\n", "subtitulos.srt": "\n".join(srt), "teleprompter.html": tele}


def _escape(texto: str) -> str:
    from html import escape
    return escape(_sin_marcas(texto))


# ------------------------------------------------------------------------------------------- piezas

@dataclass
class Resultado:
    archivos: list[Path] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    duraciones_ms: dict[str, int] = field(default_factory=dict)


def _marca_del_producto(raiz: Path, producto: str) -> str:
    ruta = raiz / "productos" / producto / "producto.toml"
    if ruta.exists():
        return tomllib.loads(ruta.read_text(encoding="utf-8")).get("marca") or "base"
    return "base"


def _registrar_activo(cx: sqlite3.Connection, cfg: Config, pieza_id: int | None, version: int | None, ruta: Path,
                      tipo: str, ancho: int | None = None, alto: int | None = None, duracion_ms: int | None = None,
                      formato: str = "", origen: str = "RENDER") -> None:
    relativa = ruta.resolve().relative_to(cfg.espacio.resolve()).as_posix()
    cx.execute("""INSERT OR IGNORE INTO activo (pieza_id, version, ruta, tipo, formato, sha256, bytes, ancho, alto,
                    duracion_ms, origen, creado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
               (pieza_id, version, relativa, tipo, formato, util.sha256_archivo(ruta), ruta.stat().st_size, ancho, alto,
                duracion_ms, origen, util.ahora_utc()))


def exportar(raiz: Path, nombre: str, datos: dict, destino: Path, base_nombre: str, *, formatos: list[str] | None = None,
             marca: str = "base", vista_previa: bool = False, audio: Path | None = None,
             navegador: Navegador | None = None, titulo: str = "") -> Resultado:
    """Renderiza una plantilla con sus datos en todos los formatos pedidos. Devuelve los archivos creados."""
    problemas = validar(raiz, nombre, datos)
    if problemas:
        raise ErrorFabrica("Los textos no encajan en la plantilla: " + "; ".join(problemas))
    ficha = plantillas.ficha(raiz, nombre)
    formatos = formatos or ficha["formatos"][:1]
    res = Resultado()
    propio = navegador is None
    nav = Navegador().__enter__() if propio else navegador
    try:
        for formato in formatos:
            ancho, alto = FORMATOS[formato]
            sufijo = f"{base_nombre}-{formato}"
            if ficha.get("video"):
                ruta = destino / f"{sufijo}.mp4"
                html = componer(raiz, nombre, datos, formato=formato, marca=marca, vista_previa=vista_previa)
                info = nav.video(html, ancho, alto, ruta, fps=int(ficha.get("fps", 30)), audio=audio)
                res.archivos.append(ruta)
                res.duraciones_ms[ruta.name] = info["duracion_ms"]
                portada = destino / f"{sufijo}-portada.png"
                nav.imagen(html.replace("window.__portada = false", "window.__portada = true"), ancho, alto, portada)
                res.archivos.append(portada)
                res.avisos.append(f"{ruta.name}: {info['duracion_ms'] / 1000:g} s, {info['cuadros']} cuadros")
                continue
            total = paginas(raiz, nombre, datos)
            imagenes = []
            for pagina in range(total):
                ruta = destino / (f"{sufijo}-{pagina + 1:02d}.png" if total > 1 else f"{sufijo}.png")
                html = componer(raiz, nombre, datos, formato=formato, marca=marca, pagina=pagina, vista_previa=vista_previa)
                info = nav.imagen(html, ancho, alto, ruta)
                if not info["cabe"]:
                    res.avisos.append(f"{ruta.name}: el texto no cabe ni con la letra más pequeña permitida; acórtalo")
                imagenes.append(ruta)
            res.archivos += imagenes
            if total > 1 and ficha.get("pdf", False):
                ruta_pdf = destino / f"{sufijo}.pdf"
                nav.pdf(imagenes, ancho, alto, ruta_pdf)
                res.archivos.append(ruta_pdf)
        if ficha.get("interactivo"):
            ruta = destino / f"{base_nombre}-interactivo.html"
            ruta.write_text(componer_interactivo(raiz, nombre, datos, marca=marca), encoding="utf-8")
            res.archivos.append(ruta)
        if datos.get("escenas") and any(e.get("locucion") for e in datos["escenas"]):
            for archivo, texto in paquete_guion(datos, titulo or base_nombre).items():
                ruta = destino / f"{base_nombre}-{archivo}"
                ruta.write_text(texto, encoding="utf-8")
                res.archivos.append(ruta)
    finally:
        if propio:
            nav.__exit__(None, None, None)
    return res


def exportar_pieza(cx: sqlite3.Connection, cfg: Config, codigo: str, *, formatos: list[str] | None = None,
                   audio: Path | None = None, navegador: Navegador | None = None) -> Resultado:
    """Renderiza la versión actual de una pieza con su plantilla y registra los archivos como activos."""
    p = contenido.obtener_pieza(cx, codigo)
    if not p["plantilla"]:
        raise ErrorFabrica(f"La pieza {codigo} no tiene plantilla. Asígnale una al crearla.")
    v = contenido.version_actual(cx, p)
    if v is None:
        raise ErrorFabrica(f"La pieza {codigo} todavía no tiene contenido.")
    datos = util.de_json(v["contenido"], {})
    _ESPACIO_CAPTURAS[:] = [cfg.espacio / "capturas"]
    destino = cfg.salidas / codigo / f"v{v['numero']}"
    res = exportar(cfg.raiz, p["plantilla"], datos, destino, f"{codigo}-v{v['numero']}", formatos=formatos,
                   marca=_marca_del_producto(cfg.raiz, p["producto"]), audio=audio, navegador=navegador, titulo=p["titulo"])
    tipos = {".png": "imagen", ".pdf": "pdf", ".mp4": "video", ".html": "html", ".srt": "srt", ".md": "guion"}
    with db.transaccion(cx):
        for ruta in res.archivos:
            formato = next((f for f in FORMATOS if f"-{f}" in ruta.name), "")
            ancho, alto = FORMATOS.get(formato, (None, None))
            duracion = res.duraciones_ms.get(ruta.name)
            _registrar_activo(cx, cfg, p["id"], v["numero"], ruta, tipos.get(ruta.suffix, "otro"), ancho, alto, duracion,
                              f"{ancho}x{alto}" if ancho else "")
        db.auditar(cx, "fabrica", "pieza", p["id"], "RENDER", {"version": v["numero"], "archivos": len(res.archivos)})
    return res
