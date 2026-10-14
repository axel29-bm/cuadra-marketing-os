"""Campañas como archivos: campanas/<slug>/campana.toml trae la campaña, el calendario y el contenido de cada pieza.

`cargar` lo pasa a la base sin duplicar (cada pieza se reconoce por su clave), crea una versión solo si el contenido
cambió y vuelve a pasar cada pieza por el auditor. `calendario_md` y `calendario_csv` sacan el calendario legible y `exportar_paquete`
junta los archivos renderizados de la última versión de cada pieza en una carpeta para entregar.
"""

from __future__ import annotations

import copy
import csv
import io
import re
import shutil
import sqlite3
import tomllib
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import contenido, db, util
from .config import Config

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class ErrorCampana(ValueError):
    pass


def leer(carpeta: Path) -> dict:
    ruta = carpeta / "campana.toml"
    if not ruta.exists():
        raise ErrorCampana(f"No encuentro {ruta}.")
    datos = tomllib.loads(ruta.read_text(encoding="utf-8"))
    piezas = {p["clave"]: p for p in datos.get("pieza", [])}
    if len(piezas) != len(datos.get("pieza", [])):
        raise ErrorCampana("Hay claves de pieza repetidas en campana.toml.")
    resueltas = []
    for p in datos.get("pieza", []):
        resueltas.append(_resolver(p, piezas, set()))
    datos["pieza"] = resueltas
    return datos


def _resolver(p: dict, todas: dict, visitadas: set) -> dict:
    """Una pieza puede basarse en otra: hereda plantilla, tipo, capacidades, fuentes y textos, y cambia lo suyo."""
    if "basado_en" not in p:
        return p
    if p["clave"] in visitadas:
        raise ErrorCampana(f"La pieza {p['clave']} se basa en sí misma.")
    base = todas.get(p["basado_en"])
    if base is None:
        raise ErrorCampana(f"La pieza {p['clave']} se basa en «{p['basado_en']}», que no existe.")
    base = _resolver(base, todas, visitadas | {p["clave"]})
    salida = {k: copy.deepcopy(v) for k, v in base.items() if k not in ("clave", "fecha", "contenido")}
    salida.update({k: v for k, v in p.items() if k != "contenido"})
    salida["contenido"] = {**copy.deepcopy(base.get("contenido", {})), **p.get("contenido", {})}
    return salida


_FECHA = re.compile(r'^(\s*(?:fecha|inicio|fin)\s*=\s*")(\d{4}-\d{2}-\d{2})(")', re.M)


def mover(carpeta: Path, dias: int) -> int:
    """Corre todas las fechas del archivo (campaña, piezas y días de revisión) sin tocar nada más. Devuelve cuántas cambió."""
    ruta = carpeta / "campana.toml"
    leer(carpeta)  # que el archivo sea válido antes de reescribirlo
    texto, n = _FECHA.subn(lambda m: m.group(1) + (date.fromisoformat(m.group(2)) + timedelta(days=dias)).isoformat()
                           + m.group(3), ruta.read_text(encoding="utf-8"))
    ruta.write_text(texto, encoding="utf-8")
    return n


@dataclass
class Resumen:
    creadas: list[str] = field(default_factory=list)
    actualizadas: list[str] = field(default_factory=list)
    sin_cambios: list[str] = field(default_factory=list)
    auditoria: dict[str, str] = field(default_factory=dict)


def _titulo(p: dict) -> str:
    return f"[{p['clave']}] {p['tema']}"


def cargar(cx: sqlite3.Connection, cfg: Config, carpeta: Path, por: str = "Didi") -> Resumen:
    datos = leer(carpeta)
    c = datos["campana"]
    contenido.crear_campana(cx, c["producto"], slug=c["slug"], nombre=c["nombre"], objetivo=c["objetivo"],
                            hipotesis=c["hipotesis"], oferta=c["oferta"], cta=c["cta"], metrica_exito=c["metrica_exito"],
                            meta_valor=c.get("meta_valor"), audiencia=c.get("audiencia"), inicio=c.get("inicio"),
                            fin=c.get("fin"), por=por)
    campana_id = cx.execute("SELECT id FROM campana WHERE slug = ?", (c["slug"],)).fetchone()["id"]
    res = Resumen()
    for p in datos["pieza"]:
        fila = cx.execute("SELECT codigo FROM pieza WHERE campana_id = ? AND titulo LIKE ?",
                          (campana_id, f"[{p['clave']}]%")).fetchone()
        if fila is None:
            codigo = contenido.crear_pieza(cx, c["producto"], formato=p["formato"], canal=p["canal"], titulo=_titulo(p),
                                           tipo_afirmacion=p["tipo"], campana=c["slug"], fecha_prevista=p["fecha"],
                                           plantilla=p.get("plantilla"), por=por)
            res.creadas.append(codigo)
        else:
            codigo = fila["codigo"]
            with db.transaccion(cx):
                cx.execute("""UPDATE pieza SET formato = ?, canal = ?, titulo = ?, tipo_afirmacion = ?, fecha_prevista = ?,
                                plantilla = ?, actualizado_en = ? WHERE codigo = ? AND estado NOT IN ('PUBLICADA', 'ARCHIVADA')""",
                           (p["formato"], p["canal"], _titulo(p), p["tipo"], p["fecha"], p.get("plantilla"),
                            util.ahora_utc(), codigo))
        pieza = contenido.obtener_pieza(cx, codigo)
        if pieza["estado"] in ("PUBLICADA", "ARCHIVADA"):
            res.sin_cambios.append(codigo)
            continue
        cuerpo = {"contenido": p["contenido"], "capacidades": sorted(p.get("capacidades", [])), "fuentes": p.get("fuentes", [])}
        actual = contenido.version_actual(cx, pieza)
        nueva = actual is None or actual["hash"] != util.sha256_texto(util.a_json(cuerpo))
        if nueva:
            contenido.nueva_version(cx, codigo, p["contenido"], capacidades=p.get("capacidades", []),
                                    fuentes=p.get("fuentes", []), autor=por, nota=f"Cargada desde {carpeta.name}/campana.toml")
            if fila is not None:
                res.actualizadas.append(codigo)
        elif fila is not None:
            res.sin_cambios.append(codigo)
        # Se audita siempre: las reglas del auditor o la matriz del producto pueden haber cambiado desde la última carga.
        res.auditoria[codigo] = contenido.auditar_pieza(cx, cfg.raiz, codigo).resultado
    return res


def piezas_de(cx: sqlite3.Connection, slug: str) -> dict[str, sqlite3.Row]:
    """Clave del archivo → fila de la pieza (con el resultado de su última auditoría)."""
    filas = cx.execute("""SELECT pz.*, (SELECT resultado FROM revision r WHERE r.pieza_id = pz.id AND r.version = pz.version_actual
                                        ORDER BY r.id DESC LIMIT 1) AS auditoria
                          FROM pieza pz JOIN campana c ON c.id = pz.campana_id WHERE c.slug = ?""", (slug,)).fetchall()
    return {f["titulo"][1:f["titulo"].index("]")]: f for f in filas}


# ------------------------------------------------------------------------------------------- calendario

COLUMNAS = ["fecha", "dia", "producto", "audiencia", "objetivo", "etapa", "pilar", "tema", "formato", "canal", "gancho", "copy", "cta", "fuente",
            "activos", "verificacion", "aprobacion", "metrica", "pieza", "auditor"]


APROBACION = {
    "SIN CARGAR": "Sin cargar en el sistema", "BORRADOR": "Borrador sin auditar", "EN_REVISION": "En revisión",
    "CORRECCIONES": "Frenada por el auditor: corrígela antes de aprobar", "LISTA_PARA_APROBAR": "Lista para tu aprobación",
    "APROBADA": "Aprobada por ti", "PROGRAMADA": "Programada", "PUBLICADA": "Publicada", "RECHAZADA": "Rechazada",
    "ARCHIVADA": "Archivada",
}


def filas_calendario(datos: dict, piezas_bd: dict | None = None) -> list[dict]:
    piezas_bd = piezas_bd or {}
    filas = []
    for p in datos["pieza"]:
        bd = piezas_bd.get(p["clave"])
        ct = p["contenido"]
        guion = " / ".join(e.get("locucion", "") for e in ct.get("escenas", []) if e.get("locucion"))
        estado = bd["estado"] if bd else "SIN CARGAR"
        filas.append({
            "fecha": p["fecha"], "dia": DIAS[date.fromisoformat(p["fecha"]).weekday()], "producto": datos["campana"]["producto"],
            "audiencia": p.get("audiencia", ""), "objetivo": p.get("objetivo", ""), "etapa": p.get("etapa", "").lower(),
            "pilar": p.get("pilar", ""), "tema": p["tema"],
            "formato": f"{p['formato']} · plantilla {p.get('plantilla', '—')} ({', '.join(p.get('formatos', []))})",
            "canal": p["canal"], "gancho": ct.get("gancho", ""), "copy": ct.get("copy", "") + (f"\n\nGuion: {guion}" if guion else ""),
            "cta": ct.get("cta", ""), "fuente": " ".join(p.get("fuentes", [])) or p.get("fuente", "—"),
            "activos": p.get("activos", ""), "verificacion": p.get("verificacion", ""),
            "aprobacion": APROBACION.get(estado, estado.lower().replace("_", " ")),
            "metrica": p.get("metrica", ""), "pieza": bd["codigo"] if bd else "", "auditor": (bd["auditoria"] or "") if bd else "",
        })
    for d in datos.get("dia", []):
        filas.append({k: "" for k in COLUMNAS} | {"fecha": d["fecha"], "dia": DIAS[date.fromisoformat(d["fecha"]).weekday()],
                                                    "producto": datos["campana"]["producto"], "tema": d["actividad"],
                                                    "formato": "sin publicación", "objetivo": d.get("objetivo", "")})
    return sorted(filas, key=lambda f: (f["fecha"], f["canal"]))


def calendario_csv(filas: list[dict]) -> str:
    salida = io.StringIO()
    w = csv.DictWriter(salida, fieldnames=COLUMNAS)
    w.writeheader()
    w.writerows(filas)
    return salida.getvalue()


def _celda(texto: str) -> str:
    return (texto or "").replace("|", "\\|").replace("\n", "<br>")


def calendario_md(datos: dict, filas: list[dict]) -> str:
    c = datos["campana"]
    lineas = [f"# Calendario de 30 días · {c['nombre']}", "",
              f"Del {c['inicio']} al {c['fin']}. Generado desde `campanas/{c['slug']}/campana.toml` con "
              f"`python -m mos campana calendario campanas/{c['slug']}`. No lo edites a mano: edita el TOML y vuelve a generarlo.", "",
              f"**Objetivo:** {c['objetivo']}", "", f"**Hipótesis:** {c['hipotesis']}", "",
              f"**Llamado principal:** {c['cta']}. **Métrica de éxito:** {c['metrica_exito']} (meta: {c.get('meta_valor', '—')}).", "",
              "Nada se publica sin tu aprobación. «Auditor» es el resultado de la revisión automática de la versión actual; "
              "«Pieza» es el código en la base donde se generó este calendario (en otra base puede cambiar).", "",
              "## Resumen", "", "| Fecha | Día | Canal | Formato | Tema | Objetivo | Métrica | Auditor | Pieza |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for f in filas:
        lineas.append(f"| {f['fecha']} | {f['dia']} | {f['canal'] or '—'} | {_celda(f['formato'])} | {_celda(f['tema'])} | "
                      f"{_celda(f['objetivo'])} | {_celda(f['metrica'])} | {f['auditor'].lower().replace('_', ' ')} | {f['pieza']} |")
    lineas += ["", "## Detalle por día", ""]
    for f in filas:
        lineas.append(f"### {f['fecha']} · {f['dia']} · {f['canal'] or 'sin publicación'}")
        lineas.append("")
        if not f["canal"]:
            lineas += [f"{f['tema']}", ""]
            continue
        for etiqueta, clave in (("Tema", "tema"), ("Audiencia", "audiencia"), ("Objetivo", "objetivo"), ("Etapa del embudo", "etapa"),
                                ("Pilar", "pilar"), ("Formato", "formato"),
                                ("Gancho", "gancho"), ("Llamado", "cta"), ("Fuente", "fuente"), ("Archivos", "activos"),
                                ("Verificación", "verificacion"), ("Aprobación", "aprobacion"), ("Métrica principal", "metrica"),
                                ("Pieza en el sistema", "pieza")):
            if f[clave]:
                lineas.append(f"- **{etiqueta}:** {f[clave]}")
        lineas += ["", "Texto para publicar:", "", "```text", f["copy"].strip(), "```", ""]
    return "\n".join(lineas) + "\n"


# ------------------------------------------------------------------------------------------- paquete

def exportar_paquete(cx: sqlite3.Connection, cfg: Config, carpeta: Path, destino: Path) -> list[Path]:
    """Copia los archivos de la última versión de cada pieza a destino/<fecha>-<clave>/ junto con su texto."""
    datos = leer(carpeta)
    bd = piezas_de(cx, datos["campana"]["slug"])
    copiados = []
    for p in datos["pieza"]:
        fila = bd.get(p["clave"])
        if fila is None:
            continue
        sub = destino / f"{p['fecha']}-{p['clave']}"
        sub.mkdir(parents=True, exist_ok=True)
        activos = cx.execute("SELECT DISTINCT ruta FROM activo WHERE pieza_id = ? AND version = ? ORDER BY ruta",
                             (fila["id"], fila["version_actual"])).fetchall()
        for a in activos:
            origen = cfg.espacio / a["ruta"]
            if origen.exists():
                nombre = origen.name.replace(f"{fila['codigo']}-v{fila['version_actual']}", p["clave"])
                shutil.copy2(origen, sub / nombre)
                copiados.append(sub / nombre)
        ct = p["contenido"]
        texto = [f"# {p['tema']}", "", f"- Fecha prevista: {p['fecha']} · Canal: {p['canal']} · Pieza: {fila['codigo']}",
                 f"- Auditor: {(fila['auditoria'] or 'sin auditar').lower().replace('_', ' ')} · Estado: {fila['estado'].lower().replace('_', ' ')}",
                 f"- Verificación: {p.get('verificacion', '')}", "", "## Texto para publicar", "", ct.get("copy", "").strip(), ""]
        if ct.get("cta"):
            texto += [f"Llamado: {ct['cta']}", ""]
        (sub / "texto.md").write_text("\n".join(texto), encoding="utf-8")
        copiados.append(sub / "texto.md")
    return copiados
