"""Carga la configuración versionada (archivos TOML) en la base, sin duplicar.

Lo que se escribe a mano y se revisa en git (productos, matrices de capacidades, marcas, fuentes,
herramientas, licencias) vive en TOML. Lo operativo (piezas, aprobaciones, leads, métricas) vive en
la base. Ejecutar la carga dos veces deja el mismo resultado.
"""

from __future__ import annotations

import sqlite3
import tomllib
from pathlib import Path

from . import db, util


def _leer(ruta: Path) -> dict:
    return tomllib.loads(ruta.read_text(encoding="utf-8"))


def cargar_todo(cx: sqlite3.Connection, raiz: Path) -> dict[str, int]:
    conteo: dict[str, int] = {}
    with db.transaccion(cx):
        for ruta in sorted((raiz / "marcas").glob("*/marca.toml")):
            _marca(cx, ruta.parent, _leer(ruta))
            conteo["marcas"] = conteo.get("marcas", 0) + 1
        for carpeta in sorted(p for p in (raiz / "productos").iterdir() if (p / "producto.toml").exists()):
            n = _producto(cx, carpeta)
            for k, v in n.items():
                conteo[k] = conteo.get(k, 0) + v
        archivos = {
            "fuentes": raiz / "semillas" / "fuentes.toml",
            "herramientas": raiz / "semillas" / "herramientas.toml",
            "licencias": raiz / "semillas" / "licencias.toml",
        }
        if archivos["fuentes"].exists():
            conteo["fuentes"] = _fuentes(cx, _leer(archivos["fuentes"]))
        if archivos["herramientas"].exists():
            conteo["herramientas"] = _herramientas(cx, _leer(archivos["herramientas"]))
        if archivos["licencias"].exists():
            conteo["licencias"] = _licencias(cx, _leer(archivos["licencias"]))
    return conteo


def _marca(cx: sqlite3.Connection, carpeta: Path, d: dict) -> None:
    ahora = util.ahora_utc()
    tokens = {k: v for k, v in d.items() if isinstance(v, dict)}
    cx.execute(
        """INSERT INTO marca (slug, nombre, descripcion, tokens, logo, provisional, creado_en, actualizado_en)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(slug) DO UPDATE SET nombre=excluded.nombre, descripcion=excluded.descripcion,
             tokens=excluded.tokens, logo=excluded.logo, provisional=excluded.provisional, actualizado_en=excluded.actualizado_en""",
        (d["slug"], d["nombre"], d.get("descripcion", ""), util.a_json(tokens), d.get("logo"),
         int(d.get("provisional", True)), ahora, ahora))


def _producto(cx: sqlite3.Connection, carpeta: Path) -> dict[str, int]:
    p = _leer(carpeta / "producto.toml")
    ahora = util.ahora_utc()
    marca = cx.execute("SELECT id FROM marca WHERE slug = ?", (p.get("marca", ""),)).fetchone()
    matriz = _leer(carpeta / "capacidades.toml") if (carpeta / "capacidades.toml").exists() else {}
    meta = matriz.get("meta", {})
    cx.execute(
        """INSERT INTO producto (slug, nombre_provisional, nombre_comercial, sector, publico_objetivo, problemas,
             propuesta_valor, precio, precio_definido, estado_desarrollo, etapa_comercial, disponible_al_publico,
             validacion_contable, marca_id, canales, competidores, presupuesto_mensual_c, repositorio,
             commit_auditado, fecha_auditoria, notas, creado_en, actualizado_en)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(slug) DO UPDATE SET nombre_provisional=excluded.nombre_provisional,
             nombre_comercial=excluded.nombre_comercial, sector=excluded.sector,
             publico_objetivo=excluded.publico_objetivo, problemas=excluded.problemas,
             propuesta_valor=excluded.propuesta_valor, precio=excluded.precio, precio_definido=excluded.precio_definido,
             estado_desarrollo=excluded.estado_desarrollo, etapa_comercial=excluded.etapa_comercial,
             disponible_al_publico=excluded.disponible_al_publico, validacion_contable=excluded.validacion_contable,
             marca_id=excluded.marca_id, canales=excluded.canales, competidores=excluded.competidores,
             presupuesto_mensual_c=excluded.presupuesto_mensual_c, repositorio=excluded.repositorio,
             commit_auditado=excluded.commit_auditado, fecha_auditoria=excluded.fecha_auditoria,
             notas=excluded.notas, actualizado_en=excluded.actualizado_en""",
        (p["slug"], p["nombre_provisional"], p.get("nombre_comercial") or None, p["sector"], p["publico_objetivo"],
         util.a_json(p.get("problemas", [])), p["propuesta_valor"], p.get("precio") or None,
         int(p.get("precio_definido", False)), p["estado_desarrollo"], p["etapa_comercial"],
         int(p.get("disponible_al_publico", False)), p.get("validacion_contable"), marca["id"] if marca else None,
         util.a_json(p.get("canales", [])), util.a_json(p.get("competidores", [])),
         int(p.get("presupuesto_mensual_c", 0)), p.get("repositorio"), meta.get("commit_auditado"),
         meta.get("fecha_auditoria"), p.get("notas", ""), ahora, ahora))
    pid = cx.execute("SELECT id FROM producto WHERE slug = ?", (p["slug"],)).fetchone()["id"]
    conteo = {"productos": 1, "capacidades": 0, "audiencias": 0}

    codigos = []
    for c in matriz.get("capacidad", []):
        codigos.append(c["codigo"])
        cx.execute(
            """INSERT INTO capacidad (producto_id, codigo, nombre, estado, uso, evidencia, frase, matiz, prohibido, verificado_en)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(producto_id, codigo) DO UPDATE SET nombre=excluded.nombre, estado=excluded.estado,
                 uso=excluded.uso, evidencia=excluded.evidencia, frase=excluded.frase, matiz=excluded.matiz,
                 prohibido=excluded.prohibido, verificado_en=excluded.verificado_en""",
            (pid, c["codigo"], c["nombre"], c["estado"], c["uso"], c["evidencia"], c.get("frase"), c.get("matiz"),
             util.a_json(c.get("prohibido", [])), meta.get("fecha_auditoria", util.ahora_utc()[:10])))
        conteo["capacidades"] += 1
    if codigos:
        cx.execute(f"DELETE FROM capacidad WHERE producto_id = ? AND codigo NOT IN ({','.join('?' * len(codigos))})",
                   (pid, *codigos))
    cx.execute("DELETE FROM prohibicion WHERE producto_id = ?", (pid,))
    for g in matriz.get("prohibicion_global", []):
        cx.execute("INSERT INTO prohibicion (producto_id, patron, motivo) VALUES (?,?,?)", (pid, g["patron"], g["motivo"]))

    if (carpeta / "audiencias.toml").exists():
        for a in _leer(carpeta / "audiencias.toml").get("audiencia", []):
            cx.execute(
                """INSERT INTO audiencia (producto_id, slug, nombre, descripcion, dolores, objeciones, canales, naturaleza)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(producto_id, slug) DO UPDATE SET nombre=excluded.nombre, descripcion=excluded.descripcion,
                     dolores=excluded.dolores, objeciones=excluded.objeciones, canales=excluded.canales,
                     naturaleza=excluded.naturaleza""",
                (pid, a["slug"], a["nombre"], a["descripcion"], util.a_json(a.get("dolores", [])),
                 util.a_json(a.get("objeciones", [])), util.a_json(a.get("canales", [])), a.get("naturaleza", "HIPOTESIS")))
            conteo["audiencias"] += 1
    return conteo


def _fuentes(cx: sqlite3.Connection, d: dict) -> int:
    n = 0
    for f in d.get("fuente", []):
        cx.execute(
            """INSERT INTO fuente (slug, tipo, organismo, titulo, url, rss_url, metodo, frecuencia_horas, activa, notas)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(slug) DO UPDATE SET tipo=excluded.tipo, organismo=excluded.organismo, titulo=excluded.titulo,
                 url=excluded.url, rss_url=excluded.rss_url, metodo=excluded.metodo,
                 frecuencia_horas=excluded.frecuencia_horas, activa=excluded.activa, notas=excluded.notas""",
            (f["slug"], f["tipo"], f.get("organismo", ""), f["titulo"], f["url"], f.get("rss_url"),
             f.get("metodo", "MANUAL"), int(f.get("frecuencia_horas", 24)), int(f.get("activa", True)), f.get("notas", "")))
        n += 1
    return n


def _herramientas(cx: sqlite3.Connection, d: dict) -> int:
    n = 0
    for h in d.get("herramienta", []):
        cx.execute(
            """INSERT INTO herramienta (slug, nombre, categoria, url, funcion, coste, licencia, limites, requisitos,
                 automatizacion, privacidad, riesgo, decision, verificacion, verificado_en, requiere_autorizacion)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(slug) DO UPDATE SET nombre=excluded.nombre, categoria=excluded.categoria, url=excluded.url,
                 funcion=excluded.funcion, coste=excluded.coste, licencia=excluded.licencia, limites=excluded.limites,
                 requisitos=excluded.requisitos, automatizacion=excluded.automatizacion, privacidad=excluded.privacidad,
                 riesgo=excluded.riesgo, decision=excluded.decision, verificacion=excluded.verificacion,
                 verificado_en=excluded.verificado_en, requiere_autorizacion=excluded.requiere_autorizacion""",
            (h["slug"], h["nombre"], h["categoria"], h["url"], h["funcion"], h["coste"], h["licencia"],
             h.get("limites", ""), h.get("requisitos", ""), h.get("automatizacion", ""), h.get("privacidad", ""),
             h.get("riesgo", ""), h["decision"], h["verificacion"], h["verificado_en"],
             int(h.get("requiere_autorizacion", False))))
        n += 1
    return n


def _licencias(cx: sqlite3.Connection, d: dict) -> int:
    n = 0
    for lic in d.get("recurso", []):
        cx.execute(
            """INSERT INTO licencia_recurso (recurso, tipo, licencia, url, uso_comercial, atribucion, verificado_en, notas)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(recurso) DO UPDATE SET tipo=excluded.tipo, licencia=excluded.licencia, url=excluded.url,
                 uso_comercial=excluded.uso_comercial, atribucion=excluded.atribucion,
                 verificado_en=excluded.verificado_en, notas=excluded.notas""",
            (lic["recurso"], lic["tipo"], lic["licencia"], lic["url"], int(lic["uso_comercial"]),
             lic.get("atribucion", ""), lic["verificado_en"], lic.get("notas", "")))
        n += 1
    return n
