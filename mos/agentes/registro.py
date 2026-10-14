"""Los once roles del departamento de marketing, con su contrato.

Ocho roles necesitan redactar o razonar (modo IA); tres son código determinista que no
cuesta nada ni inventa nada. Un mismo motor de IA puede asumir todos los roles de IA: lo que
cambia es el contrato, el prompt y los criterios de éxito.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from ..calidad import auditor as aud
from . import deterministas
from .contrato import Agente

ETAPAS = ("ATENCION", "INTERES", "CONSIDERACION", "CONVERSION", "FIDELIZACION")
TIPOS = aud.TIPOS_AFIRMACION
CATEGORIAS_MENSAJE = ("INTERES_COMERCIAL", "DUDA_FUNCION", "DEMO", "SOPORTE", "QUEJA", "OBJECION",
                      "TRIBUTARIA", "SPAM", "HUMANO")


# ------------------------------------------------------------------------------- criterios comunes

def _fecha_iso(valor: str) -> bool:
    try:
        date.fromisoformat(valor)
        return True
    except (TypeError, ValueError):
        return False


def _politica(ctx: dict) -> aud.Politica | None:
    return ctx.get("politica")


def _auditar_textos(textos: dict, tipo: str, canal: str, capacidades: list, cta: str, ctx: dict) -> list[str]:
    pol = _politica(ctx)
    if pol is None:
        return ["No hay política del producto para auditar los textos."]
    informe = aud.auditar(aud.PiezaParaAuditar(tipo_afirmacion=tipo, canal=canal, textos=textos,
                                               capacidades=capacidades, cta=cta), pol)
    return [f"{h.campo or 'texto'}: {h.mensaje}" for h in informe.bloqueantes]


def c_hechos_con_fuente(entradas, resultado, ctx):
    problemas = []
    for i, hecho in enumerate(resultado.get("hechos", [])):
        url = hecho.get("url", "")
        if not url.startswith("https://") or not urlparse(url).hostname:
            problemas.append(f"hechos[{i}]: un hecho sin enlace https verificable es una hipótesis, no un hecho")
        if not _fecha_iso(hecho.get("fecha_consulta", "")):
            problemas.append(f"hechos[{i}]: fecha_consulta debe ser AAAA-MM-DD")
    return problemas


def c_hipotesis_sin_cifras_inventadas(entradas, resultado, ctx):
    problemas = []
    for i, h in enumerate(resultado.get("hipotesis", [])):
        if re.search(r"\d+ ?%|\d{2,}[.,]?\d* (contadores|empresas|usuarios)", h.get("enunciado", "")):
            problemas.append(f"hipotesis[{i}]: una hipótesis no lleva cifras de mercado; si hay cifra, va como hecho con fuente")
    return problemas


def c_radar_fuentes(entradas, resultado, ctx):
    problemas = []
    for i, item in enumerate(resultado.get("items", [])):
        if item.get("es_fuente_primaria") and not aud._es_oficial(item.get("url", "")):
            problemas.append(f"items[{i}]: marcado como fuente primaria pero el enlace no es de un dominio oficial")
        if not _fecha_iso(item.get("fecha_publicacion", "")):
            problemas.append(f"items[{i}]: fecha_publicacion debe ser AAAA-MM-DD")
        if item.get("fecha_vigencia") and not _fecha_iso(item["fecha_vigencia"]):
            problemas.append(f"items[{i}]: fecha_vigencia debe ser AAAA-MM-DD")
    return problemas


def c_campanas_completas(entradas, resultado, ctx):
    problemas = []
    for i, c in enumerate(resultado.get("campanas", [])):
        problemas += [f"campanas[{i}].{p}" for p in _auditar_textos(
            {"oferta": c.get("oferta", ""), "cta": c.get("cta", "")}, "CAPTACION", "plan", [], c.get("cta", ""), ctx)]
        for j, pieza in enumerate(c.get("piezas", [])):
            if not _fecha_iso(pieza.get("fecha", "")):
                problemas.append(f"campanas[{i}].piezas[{j}]: fecha debe ser AAAA-MM-DD")
    return problemas


def c_copys_sin_bloqueos(entradas, resultado, ctx):
    problemas = []
    tipo = entradas.get("tipo_afirmacion", "EDUCATIVA")
    canal = entradas.get("canal", "")
    for i, v in enumerate(resultado.get("variantes", [])):
        textos = {"gancho": v.get("gancho", ""), "copy": v.get("copy", "")}
        problemas += [f"variantes[{i}] {p}" for p in _auditar_textos(
            textos, tipo, canal, v.get("capacidades", []), v.get("cta", ""), ctx)]
    if len(resultado.get("variantes", [])) < 2:
        problemas.append("Entrega al menos dos variantes para poder comparar")
    return problemas


def c_concepto_visual(entradas, resultado, ctx):
    plantillas: set[str] = ctx.get("plantillas", set())
    problemas = []
    if plantillas and resultado.get("plantilla") not in plantillas:
        problemas.append(f"plantilla: «{resultado.get('plantilla')}» no existe. Disponibles: {', '.join(sorted(plantillas))}")
    textos = {k: v for k, v in resultado.get("textos", {}).items() if isinstance(v, str)}
    problemas += _auditar_textos(textos, entradas.get("tipo_afirmacion", "EDUCATIVA"), "imagen",
                                 entradas.get("capacidades", []), textos.get("cta", ""), ctx)
    return problemas


def c_guion_coherente(entradas, resultado, ctx):
    problemas = []
    total = sum(e.get("duracion_s", 0) for e in resultado.get("escenas", []))
    objetivo = resultado.get("duracion_s", 0)
    if objetivo and abs(total - objetivo) > max(3, objetivo * 0.1):
        problemas.append(f"Las escenas suman {total} s y la duración objetivo es {objetivo} s")
    voz = " ".join(e.get("voz", "") for e in resultado.get("escenas", []))
    pantalla = " ".join(e.get("en_pantalla", "") for e in resultado.get("escenas", []))
    problemas += _auditar_textos({"voz": voz, "pantalla": pantalla, "gancho": resultado.get("gancho", "")},
                                 entradas.get("tipo_afirmacion", "EDUCATIVA"), "video",
                                 entradas.get("capacidades", []), "", ctx)
    musica = resultado.get("musica", "")
    if musica and musica.lower() not in {"sin música", "sin musica"} and "licencia" not in musica.lower():
        problemas.append("musica: indica la pista y su licencia, o «sin música»")
    return problemas


def c_respuestas_prudentes(entradas, resultado, ctx):
    problemas = []
    for i, r in enumerate(resultado.get("respuestas", [])):
        if r.get("categoria") in {"TRIBUTARIA", "QUEJA", "HUMANO"} and not r.get("requiere_humano"):
            problemas.append(f"respuestas[{i}]: {r.get('categoria')} siempre requiere intervención humana")
        problemas += [f"respuestas[{i}] {p}" for p in _auditar_textos(
            {"borrador": r.get("borrador", "")}, "EDUCATIVA", "comentario", [], "", ctx)]
    return problemas


def c_prioridades_accionables(entradas, resultado, ctx):
    return [f"prioridades[{i}]: la acción debe empezar con un verbo y caber en una línea"
            for i, p in enumerate(resultado.get("prioridades", []))
            if len(p.get("accion", "")) > 140]


# ------------------------------------------------------------------------------------- los agentes

AGENTES: dict[str, Agente] = {}


def _registrar(a: Agente) -> Agente:
    AGENTES[a.id] = a
    return a


_registrar(Agente(
    id="director", nombre="Director de marketing y orquestador", modo="IA",
    responsabilidad="Prioriza campañas y tareas según objetivos comerciales, evita duplicidades, vigila el presupuesto "
                    "y resume la semana. Su prioridad son oportunidades comerciales, no volumen de contenido.",
    entradas={"periodo": str, "estado_del_sistema": dict, "objetivos?": [str]},
    salida={"resumen": str,
            "prioridades": [{"accion": str, "motivo": str, "responsable": str}],
            "bloqueos?": [str],
            "experimentos?": [{"codigo": str, "decision": ("CONTINUAR", "MODIFICAR", "DETENER", "INVESTIGAR"), "motivo": str}]},
    criterios=(("prioridades_accionables", c_prioridades_accionables),),
    prompt="director.md",
    no_hace=("aprobar gastos", "publicar", "inventar resultados"),
))

_registrar(Agente(
    id="investigador", nombre="Investigador de mercado y competencia", modo="IA",
    responsabilidad="Investiga problemas del público, competidores, mensajes y objeciones. Separa hechos con fuente de hipótesis.",
    entradas={"pregunta": str, "producto": str},
    salida={"hechos": [{"afirmacion": str, "url": str, "fecha_consulta": str}],
            "hipotesis": [{"enunciado": str, "como_validar": str}],
            "preguntas_abiertas?": [str]},
    criterios=(("hechos_con_fuente", c_hechos_con_fuente), ("hipotesis_sin_cifras", c_hipotesis_sin_cifras_inventadas)),
    prompt="investigador.md",
    no_hace=("inventar comentarios, conversaciones o métricas de competidores",),
))

_registrar(Agente(
    id="radar", nombre="Radar contable, tributario y de noticias", modo="IA",
    responsabilidad="Detecta novedades en fuentes oficiales y propone contenido. Nunca marca una noticia como verificada: eso lo hace una persona.",
    entradas={"items_detectados": [dict]},
    salida={"items": [{"titulo": str, "url": str, "fecha_publicacion": str, "fecha_vigencia?": str,
                       "afecta_a": str, "que_cambia": str, "es_fuente_primaria": bool,
                       "advertencias": str, "propuesta_contenido": str}]},
    criterios=(("fuentes_oficiales", c_radar_fuentes),),
    requiere_aprobacion=True,
    prompt="radar.md",
    no_hace=("presentar rumores como noticias", "interpretar normas sin revisión de un contador"),
))

_registrar(Agente(
    id="estratega", nombre="Estratega editorial y de campañas", modo="IA",
    responsabilidad="Convierte objetivos e investigación en campañas, series y calendarios con hipótesis, oferta, CTA y métrica.",
    entradas={"producto": str, "objetivo": str, "periodo?": str, "capacidad_produccion?": str},
    salida={"campanas": [{"nombre": str, "objetivo": str, "audiencia": str, "hipotesis": str, "oferta": str,
                          "cta": str, "metrica_exito": str, "canales": [str],
                          "piezas": [{"fecha": str, "formato": str, "canal": str, "tema": str,
                                      "etapa_embudo": ETAPAS, "objetivo": str}]}]},
    criterios=(("campanas_completas", c_campanas_completas),),
    requiere_aprobacion=True,
    prompt="estratega.md",
))

_registrar(Agente(
    id="copywriter", nombre="Copywriter y guionista", modo="IA",
    responsabilidad="Escribe ganchos, copys, CTAs y variantes por canal, en español natural de Perú, sin promesas que no se puedan mostrar.",
    entradas={"pieza": str, "brief": str, "canal": str, "tipo_afirmacion": TIPOS},
    salida={"variantes": [{"gancho": str, "copy": str, "cta": str, "capacidades": [str], "hashtags?": [str]}]},
    criterios=(("copys_sin_bloqueos", c_copys_sin_bloqueos),),
    prompt="copywriter.md",
    no_hace=("inventar testimonios, cifras o precios",),
))

_registrar(Agente(
    id="director_creativo", nombre="Director creativo y diseñador gráfico", modo="IA",
    responsabilidad="Elige concepto, plantilla y jerarquía visual; entrega los textos definitivos de cada campo de la plantilla.",
    entradas={"pieza": str, "tipo_afirmacion": TIPOS, "capacidades?": [str], "plantilla_sugerida?": str},
    salida={"concepto": str, "plantilla": str, "jerarquia": [str], "textos": dict, "formatos": [str],
            "capturas_necesarias?": [str]},
    criterios=(("concepto_visual", c_concepto_visual),),
    prompt="director_creativo.md",
    no_hace=("generar texto dentro de imágenes generativas", "recrear pantallas que no existen"),
))

_registrar(Agente(
    id="productor_audiovisual", nombre="Productor audiovisual y motion designer", modo="IA",
    responsabilidad="Convierte una idea en un guion por escenas con voz, texto en pantalla, capturas, ritmo y adaptaciones.",
    entradas={"pieza": str, "tipo_afirmacion": TIPOS, "duracion_objetivo_s": int, "capacidades?": [str]},
    salida={"titulo": str, "duracion_s": int, "gancho": str,
            "escenas": [{"n": int, "duracion_s": int, "voz": str, "en_pantalla": str, "visual": str, "capturas?": [str]}],
            "musica?": str, "instrucciones_montaje": [str],
            "adaptaciones": [{"canal": str, "formato": str, "copy": str}]},
    criterios=(("guion_coherente", c_guion_coherente),),
    prompt="productor_audiovisual.md",
))

_registrar(Agente(
    id="community", nombre="Community manager", modo="IA",
    responsabilidad="Clasifica comentarios y mensajes y redacta borradores de respuesta. No envía nada: lo envía una persona.",
    entradas={"mensajes": [{"canal": str, "texto": str}]},
    salida={"respuestas": [{"categoria": CATEGORIAS_MENSAJE, "borrador": str, "accion_sugerida": str,
                            "requiere_humano": bool}]},
    criterios=(("respuestas_prudentes", c_respuestas_prudentes),),
    requiere_aprobacion=True,
    prompt="community.md",
    no_hace=("prometer descuentos", "responder como asesor tributario", "afirmar funciones no disponibles"),
))

_registrar(Agente(
    id="leads", nombre="Responsable de leads y embudos", modo="DETERMINISTA",
    responsabilidad="Registra, deduplica y ordena los leads; propone el siguiente seguimiento y detecta cuándo ya no corresponde contactar.",
    entradas={"fecha?": str},
    salida={"seguimientos": list, "vencidos": int, "embudo": dict},
    prompt=None,
    no_hace=("enviar mensajes", "contactar sin consentimiento para publicidad"),
    ejecutor=deterministas.ejecutar_leads,
))

_registrar(Agente(
    id="analista", nombre="Analista de rendimiento", modo="DETERMINISTA",
    responsabilidad="Junta las métricas disponibles, separa lo medido de lo estimado y recomienda qué repetir, cambiar o detener.",
    entradas={"desde?": str, "hasta?": str, "producto?": str},
    salida={"resumen": dict, "recomendaciones": [dict], "reciclables": list},
    prompt=None,
    no_hace=("atribuir ventas a una publicación sin evidencia", "presentar estimaciones como medidas"),
    ejecutor=deterministas.ejecutar_analista,
))

_registrar(Agente(
    id="auditor", nombre="Auditor de calidad, marca y cumplimiento", modo="DETERMINISTA",
    responsabilidad="Revisa cada pieza contra la matriz de capacidades, la etapa comercial, las reglas del canal, la privacidad y "
                    "el estilo. Puede rechazarla y explica qué corregir. No confía en lo que diga el agente anterior.",
    entradas={"pieza": str},
    salida={"resultado": ("APROBADO", "CON_OBSERVACIONES", "RECHAZADO"), "hallazgos": list},
    prompt=None,
    ejecutor=deterministas.ejecutar_auditor,
))


def agente(id_: str) -> Agente:
    try:
        return AGENTES[id_]
    except KeyError:
        raise KeyError(f"No existe el agente «{id_}». Disponibles: {', '.join(AGENTES)}") from None


def ruta_prompt(raiz: Path, a: Agente) -> Path | None:
    return (raiz / "prompts" / a.prompt) if a.prompt else None
