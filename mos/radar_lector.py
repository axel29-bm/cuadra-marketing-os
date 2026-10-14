"""Lector del radar: revisa las fuentes configuradas y deja lo nuevo en el radar, sin verificar.

Reglas de cortesía (semillas/fuentes.toml): respeta robots.txt, se identifica, una petición por recurso y
pasada, al menos 5 s entre peticiones al mismo dominio, solo https y nunca sistemas con clave. Una fuente
MANUAL nunca se descarga. Lo que el lector encuentra entra como SIN_VERIFICAR: solo una persona que leyó la
fuente oficial lo verifica, y una pieza normativa necesita además la revisión de un contador.

La primera lectura de una página guarda lo que hay como punto de partida y no crea novedades: así no se
llena el radar de enlaces viejos.
"""

from __future__ import annotations

import gzip
import hashlib
import http.client
import io
import re
import sqlite3
import time
import unicodedata
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urldefrag, urljoin, urlsplit

from . import db, util
from .calidad.auditor import _es_oficial

AGENTE = "CuadraMarketingOS/0.1 (lector de radar local; respeta robots.txt)"
MAX_BYTES = 10 * 1024 * 1024
MAX_NUEVAS = 25            # por fuente y pasada: más que eso es ruido o un cambio de estructura
MAX_TITULOS = 30           # páginas que se abren para leer su título (sitemaps con direcciones opacas)
MAX_VISTOS = 3000
DIAS_SITEMAP = 7           # en un sitemap solo cuenta lo modificado en la última semana
AUTOMATICOS = ("SITEMAP", "RSS", "HTML")

Descargar = Callable[[str], bytes]


class ErrorLectura(RuntimeError):
    pass


class NoEncontrado(ErrorLectura):
    pass


@dataclass
class Lectura:
    fuente: str
    estado: str            # NUEVAS · SIN_NOVEDADES · PUNTO_DE_PARTIDA · NO_TOCA · BLOQUEADA · ERROR
    nuevas: int = 0
    detalle: str = ""


# ----------------------------------------------------------------------------------------------- descarga

def descargar(url: str) -> bytes:
    """Una petición GET identificada, solo https y con tope de tamaño."""
    if not url.startswith("https://"):
        raise ErrorLectura(f"Solo se leen direcciones https: {url}")
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(pedido, timeout=30) as r:
            if not r.geturl().startswith("https://"):
                raise ErrorLectura(f"La fuente redirigió fuera de https: {r.geturl()}")
            datos = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            raise NoEncontrado(f"{url} respondió {e.code}") from None
        raise ErrorLectura(f"{url} respondió {e.code}") from None
    except urllib.error.URLError as e:
        raise ErrorLectura(f"No se pudo conectar con {url}: {e.reason}") from None
    except (OSError, http.client.HTTPException) as e:
        raise ErrorLectura(f"Se cortó la lectura de {url}: {e}") from None
    if len(datos) > MAX_BYTES:
        raise ErrorLectura(f"{url} pesa más de {MAX_BYTES // 1024 // 1024} MB")
    return datos


def _descomprimir(datos: bytes) -> bytes:
    if datos[:2] != b"\x1f\x8b":
        return datos
    with gzip.GzipFile(fileobj=io.BytesIO(datos)) as g:
        salida = g.read(MAX_BYTES * 5 + 1)
    if len(salida) > MAX_BYTES * 5:
        raise ErrorLectura("El archivo comprimido se expande demasiado")
    return salida


def _texto(datos: bytes) -> str:
    """Las páginas de SUNAT suelen venir en ISO-8859-1; se prueba UTF-8 primero."""
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError:
        return datos.decode("cp1252", errors="replace")


def _normal(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


class _Cortesia:
    """Robots.txt por dominio y una pausa mínima entre peticiones al mismo dominio."""

    def __init__(self, bajar: Descargar, pausa: float, dormir: Callable[[float], None]):
        self.bajar, self.pausa, self.dormir = bajar, pausa, dormir
        self.robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.ultima: dict[str, float] = {}

    def _esperar(self, host: str, minimo: float) -> None:
        if host in self.ultima:
            falta = minimo - (time.monotonic() - self.ultima[host])
            if falta > 0:
                self.dormir(falta)
        self.ultima[host] = time.monotonic()

    def _robots(self, url: str) -> urllib.robotparser.RobotFileParser:
        partes = urlsplit(url)
        if partes.netloc not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            self._esperar(partes.netloc, self.pausa)
            try:
                rp.parse(_texto(self.bajar(f"https://{partes.netloc}/robots.txt")).splitlines())
            except NoEncontrado:
                rp.allow_all = True          # sin robots.txt no hay restricciones declaradas
            except ErrorLectura as e:
                raise ErrorLectura(f"No se pudo leer robots.txt de {partes.netloc}: {e}") from None
            self.robots[partes.netloc] = rp
        return self.robots[partes.netloc]

    def permitido(self, url: str) -> bool:
        return self._robots(url).can_fetch(AGENTE, url)

    def pedir(self, url: str) -> bytes:
        rp = self._robots(url)
        if not rp.can_fetch(AGENTE, url):
            raise PermissionError(url)
        self._esperar(urlsplit(url).netloc, max(self.pausa, float(rp.crawl_delay(AGENTE) or 0)))
        return self.bajar(url)


# ------------------------------------------------------------------------------------------------ análisis

class _Enlaces(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.enlaces: list[tuple[str, str]] = []
        self.texto: list[str] = []
        self.titulo: list[str] = []
        self.og_titulo = ""
        self._href: str | None = None
        self._ancla: list[str] = []
        self._omitir = 0
        self._en_titulo = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self._omitir += 1
        elif tag == "a" and a.get("href"):
            self._href, self._ancla = a["href"], []
        elif tag == "title":
            self._en_titulo = True
        elif tag == "meta" and (a.get("property") or a.get("name") or "").lower() == "og:title":
            self.og_titulo = a.get("content") or ""

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._omitir:
            self._omitir -= 1
        elif tag == "a" and self._href is not None:
            self.enlaces.append((self._href, " ".join(self._ancla)))
            self._href = None
        elif tag == "title":
            self._en_titulo = False

    def handle_data(self, data):
        if self._omitir:
            return
        self.texto.append(data)
        if self._href is not None:
            self._ancla.append(data)
        if self._en_titulo:
            self.titulo.append(data)


def _analizar_html(base: str, html: str) -> tuple[list[tuple[str, str]], str, str]:
    """Enlaces https del mismo dominio (url, texto), huella del texto visible y título de la página."""
    p = _Enlaces()
    p.feed(html)
    host = urlsplit(base).netloc
    vistos, enlaces = set(), []
    for href, ancla in p.enlaces:
        url = urldefrag(urljoin(base, href.strip()))[0]
        if not url.startswith("https://") or urlsplit(url).netloc != host or url in vistos or url == base:
            continue
        vistos.add(url)
        enlaces.append((url, re.sub(r"\s+", " ", ancla).strip()))
    visible = re.sub(r"\s+", " ", " ".join(p.texto)).strip()
    titulo = re.sub(r"\s+", " ", p.og_titulo or " ".join(p.titulo)).strip()
    return enlaces, hashlib.sha256(visible.encode()).hexdigest(), titulo


_NS = re.compile(r"^\{[^}]+\}")


def _analizar_sitemap(xml: bytes) -> tuple[str, list[tuple[str, str]]]:
    """('urlset' o 'sitemapindex', [(loc, lastmod)]). ElementTree no resuelve entidades externas."""
    try:
        raiz = ET.fromstring(_descomprimir(xml))
    except ET.ParseError as e:
        raise ErrorLectura(f"El sitemap no es XML válido: {e}") from None
    tipo = _NS.sub("", raiz.tag)
    if tipo not in ("urlset", "sitemapindex"):
        raise ErrorLectura(f"No parece un sitemap: <{tipo}>")
    filas = []
    for nodo in raiz:
        datos = {_NS.sub("", h.tag): (h.text or "").strip() for h in nodo}
        if datos.get("loc"):
            filas.append((datos["loc"], datos.get("lastmod", "")))
    return tipo, filas


def _titulo_de_url(url: str) -> str:
    """El último tramo con palabras de la dirección, legible."""
    for tramo in reversed([t for t in urlsplit(url).path.split("/") if t]):
        palabras = re.findall(r"[a-záéíóúñ]{3,}", tramo.lower())
        if len(palabras) >= 2:
            texto = re.sub(r"[-_]+", " ", re.sub(r"\.\w{2,5}$", "", tramo)).strip()
            return texto[:1].upper() + texto[1:]
    return url


def _dice_algo(url: str) -> bool:
    return _titulo_de_url(url) != url


def _pasa(filtro: list[str], *textos: str) -> bool:
    if not filtro:
        return True
    junto = _normal(" ".join(textos))
    return any(_normal(f) in junto for f in filtro)


def _reciente(lastmod: str, ahora: datetime) -> bool:
    if not lastmod:
        return True
    try:
        fecha = datetime.fromisoformat(lastmod.replace("Z", "+00:00"))
    except ValueError:
        return True
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha >= ahora - timedelta(days=DIAS_SITEMAP)


# ------------------------------------------------------------------------------------------------ lectura

def _estado(cx: sqlite3.Connection, fuente_id: int) -> dict:
    fila = cx.execute("SELECT * FROM fuente_estado WHERE fuente_id = ?", (fuente_id,)).fetchone()
    if fila is None:
        return {"enlaces": [], "huella": None, "lecturas": 0}
    return {"enlaces": util.de_json(fila["enlaces"], []), "huella": fila["huella"], "lecturas": fila["lecturas"]}


def _guardar_estado(cx: sqlite3.Connection, fuente_id: int, enlaces: list[str], huella: str | None, lecturas: int) -> None:
    cx.execute("""INSERT INTO fuente_estado (fuente_id, enlaces, huella, lecturas, actualizado_en) VALUES (?,?,?,?,?)
                  ON CONFLICT(fuente_id) DO UPDATE SET enlaces = excluded.enlaces, huella = excluded.huella,
                    lecturas = excluded.lecturas, actualizado_en = excluded.actualizado_en""",
               (fuente_id, util.a_json(enlaces[-MAX_VISTOS:]), huella, lecturas, util.ahora_utc()))


def _leer_html(f: sqlite3.Row, previo: dict, red: _Cortesia) -> tuple[list[dict], list[str], str]:
    url = f["url"]
    enlaces, huella, _ = _analizar_html(url, _texto(red.pedir(url)))
    vistos = set(previo["enlaces"])
    filtro = util.de_json(f["filtro"], [])
    nuevas = [{"url": u, "titulo": t or _titulo_de_url(u)} for u, t in enlaces
              if u not in vistos and _pasa(filtro, t, u)]
    if previo["lecturas"] and not nuevas and previo["huella"] and huella != previo["huella"] and not filtro:
        # La página cambió sin enlaces nuevos (un cronograma, el valor de la UIT): alguien tiene que mirarla.
        nuevas = [{"url": f"{url}#cambio-{util.hoy_lima().isoformat()}", "titulo": f"Cambió la página: {f['titulo']}",
                   "resumen": "El texto de la página es distinto al de la lectura anterior. Revisa qué cambió."}]
    return nuevas, previo["enlaces"] + [u for u, _ in enlaces if u not in vistos], huella


def _leer_sitemap(f: sqlite3.Row, previo: dict, red: _Cortesia, ahora: datetime) -> tuple[list[dict], list[str], str]:
    url = f["rss_url"] or f["url"]
    datos = red.pedir(url)
    tipo, filas = _analizar_sitemap(datos)
    if tipo == "sitemapindex":
        # Los sitemaps hijos más recientes, del mismo dominio.
        hijos = [h for h in filas if urlsplit(h[0]).netloc == urlsplit(url).netloc and h[0].startswith("https://")]
        hijos = sorted(hijos, key=lambda h: h[1], reverse=True)[:2] if any(h[1] for h in hijos) else hijos[-2:]
        filas = []
        for loc, _ in hijos:
            _, sub = _analizar_sitemap(red.pedir(loc))
            filas.extend(sub)
    huella = hashlib.sha256(datos).hexdigest()
    vistos = set(previo["enlaces"])
    filtro = util.de_json(f["filtro"], [])
    primera = not previo["lecturas"]
    # En la primera lectura solo cuenta lo que tiene fecha de los últimos días; lo demás queda como visto.
    candidatas = [(loc, mod) for loc, mod in filas
                  if loc.startswith("https://") and loc not in vistos and (mod or not primera) and _reciente(mod, ahora)]
    candidatas.sort(key=lambda c: c[1], reverse=True)
    nuevas, abiertas = [], 0
    for loc, mod in candidatas:
        if len(nuevas) >= MAX_NUEVAS:
            break
        titulo = _titulo_de_url(loc)
        if not _dice_algo(loc) and abiertas < MAX_TITULOS and red.permitido(loc):
            # La dirección no dice de qué trata: se abre la página una vez para leer su título.
            abiertas += 1
            try:
                titulo = _analizar_html(loc, _texto(red.pedir(loc)))[2] or titulo
            except (ErrorLectura, PermissionError):
                pass
        if _pasa(filtro, titulo, loc):
            nuevas.append({"url": loc, "titulo": titulo, "fecha": mod[:10] or None})
    return nuevas, previo["enlaces"] + [loc for loc, _ in filas if loc not in vistos], huella


def leer_fuentes(cx: sqlite3.Connection, *, ahora: datetime | None = None, bajar: Descargar = descargar,
                 pausa: float = 5.0, dormir: Callable[[float], None] = time.sleep, forzar: bool = False,
                 solo: list[str] | None = None) -> list[Lectura]:
    """Lee las fuentes automáticas que toca revisar y devuelve qué pasó con cada una. Nunca lanza por una fuente."""
    ahora = ahora or datetime.now(timezone.utc)
    red = _Cortesia(bajar, pausa, dormir)
    sql = "SELECT * FROM fuente WHERE activa = 1 AND metodo IN ('SITEMAP','RSS','HTML')"
    fuentes = [f for f in cx.execute(sql + " ORDER BY id") if not solo or f["slug"] in solo]
    resultados = []
    for f in fuentes:
        if not forzar and f["ultima_consulta"]:
            ultima = datetime.fromisoformat(f["ultima_consulta"].replace("Z", "+00:00"))
            if ultima + timedelta(hours=f["frecuencia_horas"]) > ahora:
                resultados.append(Lectura(f["slug"], "NO_TOCA", detalle=f"Se revisó el {f['ultima_consulta'][:10]}"))
                continue
        try:
            resultados.append(_leer_una(cx, f, red, ahora))
        except Exception as e:  # un fallo inesperado en una fuente no detiene las demás
            db.registrar_error(cx, "radar", type(e).__name__, f"{f['slug']}: {e}")
            resultados.append(Lectura(f["slug"], "ERROR", detalle=f"{type(e).__name__}: {e}"))
    return resultados


def _leer_una(cx: sqlite3.Connection, f: sqlite3.Row, red: _Cortesia, ahora: datetime) -> Lectura:
    previo = _estado(cx, f["id"])
    marca = ahora.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        if f["metodo"] == "HTML":
            nuevas, vistos, huella = _leer_html(f, previo, red)
        else:
            nuevas, vistos, huella = _leer_sitemap(f, previo, red, ahora)
    except PermissionError:
        motivo = "robots.txt no permite leer esta dirección: queda para revisión manual"
        cx.execute("UPDATE fuente SET ultima_consulta = ?, ultimo_error = ? WHERE id = ?", (marca, motivo, f["id"]))
        return Lectura(f["slug"], "BLOQUEADA", detalle=motivo)
    except (ErrorLectura, ValueError) as e:
        cx.execute("UPDATE fuente SET ultima_consulta = ?, ultimo_error = ? WHERE id = ?", (marca, str(e)[:500], f["id"]))
        db.registrar_error(cx, "radar", "LECTURA_FUENTE", f"{f['slug']}: {e}")
        return Lectura(f["slug"], "ERROR", detalle=str(e))
    partida = f["metodo"] == "HTML" and not previo["lecturas"]
    creadas = 0
    with db.transaccion(cx):
        if not partida:
            for n in nuevas[:MAX_NUEVAS]:
                creadas += int(_agregar(cx, f, n))
        _guardar_estado(cx, f["id"], vistos, huella, previo["lecturas"] + 1)
        cx.execute("UPDATE fuente SET ultima_consulta = ?, ultimo_error = NULL WHERE id = ?", (marca, f["id"]))
    if partida:
        return Lectura(f["slug"], "PUNTO_DE_PARTIDA", detalle=f"{len(vistos)} enlaces guardados como punto de partida")
    return Lectura(f["slug"], "NUEVAS" if creadas else "SIN_NOVEDADES", creadas)


def _agregar(cx: sqlite3.Connection, f: sqlite3.Row, n: dict) -> bool:
    """Como radar.agregar, pero dentro de la transacción de la lectura. La misma URL no se duplica."""
    if cx.execute("SELECT 1 FROM radar_item WHERE url = ?", (n["url"],)).fetchone():
        return False
    cx.execute(
        """INSERT INTO radar_item (fuente_id, titulo, url, resumen, fecha_publicacion, es_fuente_primaria, advertencias,
             detectado_en) VALUES (?,?,?,?,?,?,?,?)""",
        (f["id"], n["titulo"][:300], n["url"], n.get("resumen", f"Detectado por el lector en «{f['titulo']}»."),
         n.get("fecha"), int(_es_oficial(n["url"])),
         "Detectado automáticamente: el título sale del enlace. Lee la fuente antes de usarlo.", util.ahora_utc()))
    return True


ESTADOS_TEXTO = {
    "NUEVAS": "novedades", "SIN_NOVEDADES": "sin novedades", "PUNTO_DE_PARTIDA": "primera lectura (punto de partida)",
    "NO_TOCA": "todavía no toca", "BLOQUEADA": "bloqueada por robots.txt", "ERROR": "error",
}
