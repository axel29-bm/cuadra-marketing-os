"""Auditor de calidad, marca y cumplimiento: la barrera antes de aprobar una pieza.

No confía en lo que diga el agente que produjo la pieza: vuelve a leer los textos y los contrasta
con la matriz de capacidades del producto, sus prohibiciones, la etapa comercial y las reglas de
cada canal. Devuelve hallazgos con severidad. Un hallazgo BLOQUEANTE impide aprobar.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .. import util

BLOQUEANTE = "BLOQUEANTE"
ADVERTENCIA = "ADVERTENCIA"

TIPOS_AFIRMACION = ("EDUCATIVA", "PROMOCIONAL", "DESARROLLO", "NOTICIA", "HUMOR", "CAPTACION")
ETAPAS_CON_VENTA = {"PREVENTA", "DISPONIBLE"}

ESTADOS_LEGIBLES = {
    "IMPLEMENTADO_VERIFICADO": "implementado y verificado",
    "IMPLEMENTADO_PARCIAL": "implementado parcialmente",
    "EN_DESARROLLO": "en desarrollo",
    "PLANIFICADO": "planificado",
    "SIN_EVIDENCIA": "sin evidencia suficiente",
}

# Dominios que cuentan como fuente primaria para noticias contables y tributarias de Perú.
DOMINIOS_OFICIALES = (
    "gob.pe", "sunat.gob.pe", "elperuano.pe", "mef.gob.pe", "smv.gob.pe", "sbs.gob.pe",
    "inei.gob.pe", "produce.gob.pe", "congreso.gob.pe", "minjus.gob.pe", "indecopi.gob.pe",
)

# Frases de relleno típicas de textos generados que restan credibilidad. Son advertencias, no bloqueos.
MULETILLAS = (
    r"en el mundo (actual|de hoy)", r"en la era digital", r"sin lugar a dudas", r"lleva(r)? tu \w+ al siguiente nivel",
    r"descubre (el poder|c[oó]mo)", r"revoluciona(r|ndo)?", r"desbloquea", r"sum[eé]rgete", r"potencia(r)? tu",
    r"transforma(r)? tu", r"soluci[oó]n integral", r"de vanguardia", r"innovador(a)?", r"game ?changer",
    r"en un abrir y cerrar de ojos", r"no busques m[aá]s", r"todo lo que necesitas",
)

EXAGERACIONES = (
    r"\bel mejor\b", r"\bla mejor\b", r"\b[uú]nic[oa] en el mercado\b", r"n[uú]mero 1", r"\b100 ?%",
    r"garantizad[oa]s?", r"nunca m[aá]s", r"para siempre", r"cero errores", r"sin errores",
)

RE_URL = re.compile(r"https?://[^\s)>\]]+", re.I)
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
RE_TELEFONO = re.compile(r"(?<!\d)(?:\+?51[ -]?)?9\d{2}[ -]?\d{3}[ -]?\d{3}(?!\d)")
RE_RUC = re.compile(r"(?<!\d)(10|15|17|20)\d{9}(?!\d)")
RE_DNI = re.compile(r"\bDNI\D{0,5}(\d{8})\b", re.I)
RE_MONTO = re.compile(r"S/\.?\s?\d|US\$\s?\d|\$\s?\d|USD\s?\d", re.I)


@dataclass
class Hallazgo:
    regla: str
    severidad: str
    mensaje: str
    campo: str = ""
    sugerencia: str = ""

    def como_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass
class Capacidad:
    codigo: str
    nombre: str
    estado: str
    uso: str
    frase: str = ""
    matiz: str = ""
    prohibido: list[str] = field(default_factory=list)


@dataclass
class Politica:
    """Lo que un producto permite afirmar hoy."""

    producto: str
    nombre_marca: str
    etapa_comercial: str
    disponible_al_publico: bool
    precio_definido: bool
    capacidades: dict[str, Capacidad]
    prohibiciones: list[tuple[str, str]]          # (patrón, motivo)
    contactos_propios: tuple[str, ...] = ()       # correos y teléfonos de la marca que sí pueden aparecer

    @classmethod
    def desde_carpeta(cls, carpeta: Path) -> "Politica":
        producto = tomllib.loads((carpeta / "producto.toml").read_text(encoding="utf-8"))
        matriz = tomllib.loads((carpeta / "capacidades.toml").read_text(encoding="utf-8"))
        caps = {
            c["codigo"]: Capacidad(
                codigo=c["codigo"], nombre=c["nombre"], estado=c["estado"], uso=c["uso"],
                frase=c.get("frase", ""), matiz=c.get("matiz", ""), prohibido=list(c.get("prohibido", [])),
            )
            for c in matriz.get("capacidad", [])
        }
        prohibiciones = [(p["patron"], p["motivo"]) for p in matriz.get("prohibicion_global", [])]
        contactos = tuple(producto.get("contactos_propios", []))
        return cls(
            producto=producto["slug"],
            nombre_marca=producto.get("nombre_comercial") or producto["nombre_provisional"],
            etapa_comercial=producto["etapa_comercial"],
            disponible_al_publico=bool(producto.get("disponible_al_publico", False)),
            precio_definido=bool(producto.get("precio_definido", False)),
            capacidades=caps,
            prohibiciones=prohibiciones,
            contactos_propios=contactos,
        )


@dataclass
class PiezaParaAuditar:
    tipo_afirmacion: str
    canal: str
    textos: dict[str, str]                         # campo → texto visible (titular, copy, guion, textos de la imagen)
    capacidades: list[str] = field(default_factory=list)
    fuentes: list[str] = field(default_factory=list)
    cta: str = ""
    formato: str = ""
    fecha_publicacion_fuente: str = ""
    revisado_por_contador: bool = False
    es_demostracion_guiada: bool = False
    limites_canal: dict = field(default_factory=dict)


@dataclass
class Informe:
    hallazgos: list[Hallazgo]

    @property
    def resultado(self) -> str:
        if any(h.severidad == BLOQUEANTE for h in self.hallazgos):
            return "RECHAZADO"
        return "CON_OBSERVACIONES" if self.hallazgos else "APROBADO"

    @property
    def bloqueantes(self) -> list[Hallazgo]:
        return [h for h in self.hallazgos if h.severidad == BLOQUEANTE]

    def como_lista(self) -> list[dict]:
        return [h.como_dict() for h in self.hallazgos]


def auditar(pieza: PiezaParaAuditar, politica: Politica) -> Informe:
    h: list[Hallazgo] = []
    textos = {k: v for k, v in pieza.textos.items() if isinstance(v, str) and v.strip()}
    if not textos:
        return Informe([Hallazgo("contenido", BLOQUEANTE, "La pieza no tiene textos que revisar.")])
    if pieza.tipo_afirmacion not in TIPOS_AFIRMACION:
        h.append(Hallazgo("tipo", BLOQUEANTE, f"Tipo de afirmación desconocido: {pieza.tipo_afirmacion}."))

    h += _etapa_comercial(pieza, politica)
    h += _capacidades_citadas(pieza, politica)
    for campo, texto in textos.items():
        h += _frases_prohibidas(campo, texto, politica)
        h += _precios(campo, texto, politica)
        h += _datos_personales(campo, texto, politica)
        h += _estilo(campo, texto)
        h += _ortografia_basica(campo, texto)
        h += _marca(campo, texto, politica)
        h += _enlaces(campo, texto)
    h += _noticia(pieza)
    h += _cta(pieza, politica)
    h += _limites(pieza, textos)
    return Informe(_sin_repetidos(h))


# ---------------------------------------------------------------------------------------------- reglas

def _etapa_comercial(p: PiezaParaAuditar, pol: Politica) -> list[Hallazgo]:
    if p.tipo_afirmacion == "PROMOCIONAL" and pol.etapa_comercial not in ETAPAS_CON_VENTA:
        return [Hallazgo(
            "etapa_comercial", BLOQUEANTE,
            f"{pol.nombre_marca} está en {pol.etapa_comercial.lower().replace('_', ' ')}: no hay nada que vender todavía.",
            sugerencia="Usa CAPTACION (lista de espera, beta, demostración) o DESARROLLO (historia del producto).",
        )]
    return []


def _capacidades_citadas(p: PiezaParaAuditar, pol: Politica) -> list[Hallazgo]:
    h = []
    for codigo in p.capacidades:
        cap = pol.capacidades.get(codigo)
        if cap is None:
            h.append(Hallazgo("capacidad", BLOQUEANTE, f"La capacidad {codigo} no existe en la matriz del producto."))
            continue
        if cap.uso == "NO_ANUNCIAR" and p.tipo_afirmacion != "DESARROLLO":
            h.append(Hallazgo("capacidad", BLOQUEANTE,
                              f"{cap.nombre} ({codigo}) está {ESTADOS_LEGIBLES[cap.estado]} y no se puede anunciar.",
                              sugerencia=cap.matiz or "Quítala o conviértela en una historia de desarrollo."))
        elif cap.uso == "NO_ANUNCIAR":
            h.append(Hallazgo("capacidad", ADVERTENCIA,
                              f"{cap.nombre} solo puede contarse como trabajo en curso. Dilo de forma explícita.",
                              sugerencia="Ejemplo: «Estoy trabajando en…», «todavía no está disponible»."))
        elif cap.uso == "SOLO_DEMO" and not p.es_demostracion_guiada:
            h.append(Hallazgo("capacidad", BLOQUEANTE,
                              f"{cap.nombre} solo se muestra en una demostración guiada, no se promete en una pieza.",
                              sugerencia=cap.matiz))
        elif cap.uso == "CON_MATICES":
            h.append(Hallazgo("capacidad", ADVERTENCIA, f"{cap.nombre} necesita su aclaración: {cap.matiz}"))
    texto_total = " ".join(p.textos.values())
    if p.tipo_afirmacion in {"PROMOCIONAL", "CAPTACION"} and not p.capacidades and _menciona_producto(texto_total, pol):
        h.append(Hallazgo("capacidad", ADVERTENCIA,
                          "La pieza habla del producto pero no cita qué capacidades afirma.",
                          sugerencia="Anota los códigos de la matriz para que el auditor pueda contrastarlos."))
    return h


def _menciona_producto(texto: str, pol: Politica) -> bool:
    return pol.nombre_marca.lower() in texto.lower()


def _frases_prohibidas(campo: str, texto: str, pol: Politica) -> list[Hallazgo]:
    h = []
    for cap in pol.capacidades.values():
        for patron in cap.prohibido:
            if re.search(patron, texto, re.I):
                h.append(Hallazgo("afirmacion_no_demostrada", BLOQUEANTE,
                                  f"«{_extracto(texto, patron)}» promete más de lo verificado ({cap.codigo}, {ESTADOS_LEGIBLES[cap.estado]}).",
                                  campo, cap.frase or cap.matiz))
    for patron, motivo in pol.prohibiciones:
        if re.search(patron, texto, re.I):
            h.append(Hallazgo("afirmacion_no_demostrada", BLOQUEANTE,
                              f"«{_extracto(texto, patron)}»: {motivo}", campo))
    return h


def _precios(campo: str, texto: str, pol: Politica) -> list[Hallazgo]:
    if RE_MONTO.search(texto) and not pol.precio_definido:
        return [Hallazgo("precio", BLOQUEANTE, "Aparece un importe y el producto no tiene precio aprobado.", campo,
                         "Quita el importe. Un precio solo entra cuando está definido y autorizado.")]
    if re.search(r"\d+ ?% de descuento|precio anterior|antes S/", texto, re.I) and not pol.precio_definido:
        return [Hallazgo("precio", BLOQUEANTE, "Descuento o precio anterior sin precio aprobado.", campo)]
    return []


def _datos_personales(campo: str, texto: str, pol: Politica) -> list[Hallazgo]:
    h = []
    propios = {util.normalizar(c) for c in pol.contactos_propios}
    for correo in RE_EMAIL.findall(texto):
        if util.normalizar(correo) not in propios:
            h.append(Hallazgo("datos_personales", BLOQUEANTE, f"Aparece el correo {correo}.", campo,
                              "Usa solo los contactos propios de la marca configurados en producto.toml."))
    for tel in RE_TELEFONO.findall(texto):
        if util.normalizar(tel) not in propios:
            h.append(Hallazgo("datos_personales", BLOQUEANTE, "Aparece un número de celular que no es de la marca.", campo))
    for m in RE_RUC.finditer(texto):
        ruc = m.group(0)
        if not ruc.startswith(("2099", "2098")):  # prefijos ficticios de la empresa de ejemplo
            h.append(Hallazgo("datos_personales", BLOQUEANTE, f"Aparece un RUC real o posible ({ruc[:2]}…{ruc[-2:]}).", campo,
                              "En ejemplos usa la empresa de ejemplo (RUC 2099…) o tapa el número."))
    if RE_DNI.search(texto):
        h.append(Hallazgo("datos_personales", BLOQUEANTE, "Aparece un DNI.", campo))
    return h


def _estilo(campo: str, texto: str) -> list[Hallazgo]:
    h = []
    for patron in MULETILLAS:
        if re.search(patron, texto, re.I):
            h.append(Hallazgo("estilo", ADVERTENCIA, f"Frase de relleno: «{_extracto(texto, patron)}».", campo,
                              "Dilo con un hecho concreto del trabajo del contador."))
    for patron in EXAGERACIONES:
        if re.search(patron, texto, re.I):
            h.append(Hallazgo("exageracion", ADVERTENCIA, f"Exageración: «{_extracto(texto, patron)}».", campo,
                              "Cámbiala por algo que se pueda mostrar en pantalla."))
    palabras = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", texto)
    mayus = [p for p in palabras if p.isupper() and p not in {"RUC", "SUNAT", "SIRE", "SOL", "IGV", "PLE", "PCGE", "MYPE", "DNI", "CUO", "ITF", "ISC", "ICBPER", "SBS", "CUADRA", "PDF", "TXT", "ZIP", "CSV", "RCE", "RVIE", "INDECOPI", "MEF", "UIT", "IVAP", "SMV", "DEMO"}]
    if len(palabras) >= 8 and len(mayus) / len(palabras) > 0.3:
        h.append(Hallazgo("estilo", ADVERTENCIA, "Demasiadas palabras en mayúsculas: se lee como un grito.", campo))
    return h


def _ortografia_basica(campo: str, texto: str) -> list[Hallazgo]:
    h = []
    for m in re.finditer(r"\b(\w+)\s+\1\b", texto, re.I):
        if m.group(1).lower() not in {"no", "sí", "si", "ja"}:
            h.append(Hallazgo("ortografia", ADVERTENCIA, f"Palabra repetida: «{m.group(0)}».", campo))
    for oracion in re.split(r"(?<=[.!?…])\s+|\n+", texto):
        if "?" in oracion and "¿" not in oracion:
            h.append(Hallazgo("ortografia", ADVERTENCIA, f"Falta el signo de apertura ¿ en «{oracion.strip()[:60]}».", campo))
        if "!" in oracion and "¡" not in oracion:
            h.append(Hallazgo("ortografia", ADVERTENCIA, f"Falta el signo de apertura ¡ en «{oracion.strip()[:60]}».", campo))
    if re.search(r" [,.;:!?]", texto):
        h.append(Hallazgo("ortografia", ADVERTENCIA, "Hay un espacio antes de un signo de puntuación.", campo))
    if re.search(r"[^\S\n]{2,}", texto):
        h.append(Hallazgo("ortografia", ADVERTENCIA, "Hay espacios dobles.", campo))
    if re.search(r"S/\.", texto):
        h.append(Hallazgo("ortografia", ADVERTENCIA, "El símbolo del sol se escribe S/ sin punto.", campo))
    return h


def _marca(campo: str, texto: str, pol: Politica) -> list[Hallazgo]:
    nombre = pol.nombre_marca
    variantes = {m.group(0) for m in re.finditer(re.escape(nombre), texto, re.I)}
    raras = [v for v in variantes if v not in {nombre, nombre.upper()}]
    if raras:
        return [Hallazgo("marca", ADVERTENCIA, f"El nombre aparece como «{raras[0]}». Escribe {nombre}.", campo)]
    return []


def _enlaces(campo: str, texto: str) -> list[Hallazgo]:
    h = []
    for url in RE_URL.findall(texto):
        if url.lower().startswith("http://"):
            h.append(Hallazgo("enlace", ADVERTENCIA, f"Enlace sin https: {url}", campo))
    return h


def _noticia(p: PiezaParaAuditar) -> list[Hallazgo]:
    if p.tipo_afirmacion != "NOTICIA":
        return []
    h = []
    oficiales = [u for u in p.fuentes if _es_oficial(u)]
    if not oficiales:
        h.append(Hallazgo("fuente", BLOQUEANTE, "Una noticia necesita al menos un enlace a la fuente oficial primaria.",
                          sugerencia="SUNAT, El Peruano, MEF o gob.pe. Un medio o un modelo de IA no bastan."))
    if not p.fecha_publicacion_fuente:
        h.append(Hallazgo("fuente", BLOQUEANTE, "Falta la fecha de publicación de la fuente."))
    if not p.revisado_por_contador:
        h.append(Hallazgo("revision_profesional", BLOQUEANTE,
                          "Contenido normativo sin revisión de un contador. Debe revisarlo antes de publicarse."))
    return h


def _es_oficial(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return any(host == d or host.endswith("." + d) for d in DOMINIOS_OFICIALES)


def _cta(p: PiezaParaAuditar, pol: Politica) -> list[Hallazgo]:
    h = []
    if p.tipo_afirmacion in {"CAPTACION", "PROMOCIONAL"} and not p.cta.strip():
        h.append(Hallazgo("cta", BLOQUEANTE, "Una pieza de captación necesita una llamada a la acción."))
    if p.cta and not pol.disponible_al_publico and re.search(r"desc[aá]rga|c[oó]mpra|adquiere|suscr[ií]bete al plan|prueba gratis", p.cta, re.I):
        h.append(Hallazgo("cta", BLOQUEANTE, f"La llamada «{p.cta}» ofrece algo que todavía no existe.",
                          sugerencia="Ejemplos válidos: «Quiero participar en la beta», «Pide una demostración»."))
    return h


def _limites(p: PiezaParaAuditar, textos: dict[str, str]) -> list[Hallazgo]:
    h = []
    for campo, maximo in p.limites_canal.items():
        texto = textos.get(campo, "")
        if texto and len(texto) > maximo:
            h.append(Hallazgo("longitud", BLOQUEANTE,
                              f"{campo} tiene {len(texto)} caracteres y {p.canal} admite {maximo}.", campo))
    return h


# ------------------------------------------------------------------------------------------ utilidades

def _extracto(texto: str, patron: str) -> str:
    m = re.search(patron, texto, re.I)
    return m.group(0) if m else patron


def _sin_repetidos(hallazgos: list[Hallazgo]) -> list[Hallazgo]:
    vistos, salida = set(), []
    for x in hallazgos:
        clave = (x.regla, x.mensaje, x.campo)
        if clave not in vistos:
            vistos.add(clave)
            salida.append(x)
    return salida
