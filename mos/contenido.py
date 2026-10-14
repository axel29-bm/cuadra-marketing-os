"""Ideas, campañas, piezas, versiones, revisiones, aprobaciones y publicaciones.

El recorrido de una pieza es siempre el mismo:
  borrador → versión → auditoría automática → aprobación humana → paquete de publicación → publicada (con prueba)
Una aprobación vale para una versión concreta (por su hash). Si el contenido cambia, hay que aprobar de nuevo.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from . import canales, db, util
from .calidad import auditor as aud

ETAPAS_EMBUDO = ("ATENCION", "INTERES", "CONSIDERACION", "CONVERSION", "FIDELIZACION")

# Pesos de la puntuación de ideas. Suman 1. Están aquí, a la vista, para poder discutirlos.
PESOS_IDEA = {
    "valor_comercial": 0.30,   # ¿acerca a un contador a la beta o a una demostración?
    "relevancia": 0.25,        # ¿le duele de verdad al público?
    "atencion": 0.20,          # ¿detiene el scroll?
    "esfuerzo": 0.15,          # invertido: menos esfuerzo, más puntos
    "coste": 0.10,             # invertido: menos coste, más puntos
}


class ErrorContenido(ValueError):
    """Una regla del flujo de contenido impide la operación. El mensaje dice qué hacer."""


# ------------------------------------------------------------------------------------------- utilidades

def _producto_id(cx: sqlite3.Connection, slug: str) -> int:
    fila = cx.execute("SELECT id FROM producto WHERE slug = ?", (slug,)).fetchone()
    if fila is None:
        raise ErrorContenido(f"No existe el producto «{slug}». Ejecuta primero: python -m mos iniciar")
    return fila["id"]


def _siguiente(cx: sqlite3.Connection, tabla: str, prefijo: str) -> str:
    n = cx.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {tabla}").fetchone()[0]
    return f"{prefijo}-{n:04d}"


def _id_opcional(cx: sqlite3.Connection, tabla: str, columna: str, valor: str | None) -> int | None:
    if not valor:
        return None
    fila = cx.execute(f"SELECT id FROM {tabla} WHERE {columna} = ?", (valor,)).fetchone()
    if fila is None:
        raise ErrorContenido(f"No existe {tabla} «{valor}».")
    return fila["id"]


# ----------------------------------------------------------------------------------------------- ideas

def puntuar_idea(relevancia: int, atencion: int, valor_comercial: int, coste: int, esfuerzo: int, *,
                 fecha_oportunidad: str | None = None, canal_del_producto: bool = True,
                 hoy: date | None = None) -> tuple[int, dict]:
    """Puntuación de 0 a 100 y su explicación, factor por factor."""
    valores = {"relevancia": relevancia, "atencion": atencion, "valor_comercial": valor_comercial,
               "coste": coste, "esfuerzo": esfuerzo}
    for k, v in valores.items():
        if not isinstance(v, int) or not 1 <= v <= 5:
            raise ErrorContenido(f"{k} debe ser un entero de 1 a 5.")
    detalle: dict[str, dict] = {}
    total = 0.0
    for factor, peso in PESOS_IDEA.items():
        v = valores[factor]
        normal = (5 - v) / 4 if factor in ("coste", "esfuerzo") else (v - 1) / 4
        puntos = round(100 * peso * normal, 1)
        total += puntos
        detalle[factor] = {"valor": v, "peso": peso, "puntos": puntos}
    ajustes = []
    if fecha_oportunidad:
        dias = (date.fromisoformat(fecha_oportunidad) - (hoy or util.hoy_lima())).days
        if 0 <= dias <= 14:
            total += 5
            ajustes.append({"motivo": f"Oportunidad en {dias} días", "puntos": 5})
        elif dias < 0:
            total -= 10
            ajustes.append({"motivo": "La fecha de oportunidad ya pasó", "puntos": -10})
    if not canal_del_producto:
        total -= 10
        ajustes.append({"motivo": "El canal no está entre los canales del producto", "puntos": -10})
    detalle["ajustes"] = ajustes
    final = max(0, min(100, round(total)))
    detalle["explicacion"] = (
        f"{final}/100: valor comercial {valores['valor_comercial']}/5, relevancia {relevancia}/5, "
        f"atención {atencion}/5, esfuerzo {esfuerzo}/5 y coste {coste}/5 (los dos últimos restan)."
        + "".join(f" {a['motivo']} ({a['puntos']:+d})." for a in ajustes))
    return final, detalle


def crear_idea(cx: sqlite3.Connection, producto: str, *, problema: str, idea_central: str, formato: str, canal: str,
               etapa_embudo: str, objetivo: str, relevancia: int, atencion: int, valor_comercial: int, coste: int,
               esfuerzo: int, evidencia: str = "", campana: str | None = None, audiencia: str | None = None,
               fecha_oportunidad: str | None = None, responsable: str = "Didi", proxima_accion: str = "") -> str:
    if etapa_embudo not in ETAPAS_EMBUDO:
        raise ErrorContenido(f"Etapa del embudo no válida: {etapa_embudo}. Usa una de {', '.join(ETAPAS_EMBUDO)}.")
    with db.transaccion(cx):
        pid = _producto_id(cx, producto)
        canales_producto = util.de_json(cx.execute("SELECT canales FROM producto WHERE id = ?", (pid,)).fetchone()[0], [])
        puntos, detalle = puntuar_idea(relevancia, atencion, valor_comercial, coste, esfuerzo,
                                       fecha_oportunidad=fecha_oportunidad,
                                       canal_del_producto=not canales_producto or canal in canales_producto)
        aud_id = None
        if audiencia:
            fila = cx.execute("SELECT id FROM audiencia WHERE producto_id = ? AND slug = ?", (pid, audiencia)).fetchone()
            if fila is None:
                raise ErrorContenido(f"No existe la audiencia «{audiencia}» en {producto}.")
            aud_id = fila["id"]
        codigo = _siguiente(cx, "idea", "I")
        ahora = util.ahora_utc()
        cx.execute(
            """INSERT INTO idea (codigo, producto_id, campana_id, audiencia_id, problema, idea_central, formato, canal,
                 etapa_embudo, objetivo, relevancia, atencion, valor_comercial, coste, esfuerzo, evidencia,
                 fecha_oportunidad, responsable, proxima_accion, puntuacion, puntuacion_detalle, estado, creado_en, actualizado_en)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'EVALUADA',?,?)""",
            (codigo, pid, _id_opcional(cx, "campana", "slug", campana), aud_id, problema, idea_central, formato, canal,
             etapa_embudo, objetivo, relevancia, atencion, valor_comercial, coste, esfuerzo, evidencia,
             fecha_oportunidad, responsable, proxima_accion, puntos, util.a_json(detalle), ahora, ahora))
        db.auditar(cx, responsable, "idea", None, "CREAR", {"codigo": codigo, "puntuacion": puntos})
    return codigo


def ideas_priorizadas(cx: sqlite3.Connection, producto: str | None = None, limite: int = 20) -> list[sqlite3.Row]:
    sql = """SELECT i.*, p.slug AS producto FROM idea i JOIN producto p ON p.id = i.producto_id
             WHERE i.estado IN ('NUEVA','EVALUADA','SELECCIONADA')"""
    params: list = []
    if producto:
        sql += " AND p.slug = ?"
        params.append(producto)
    return cx.execute(sql + " ORDER BY i.puntuacion DESC, i.id LIMIT ?", (*params, limite)).fetchall()


def cambiar_estado_idea(cx: sqlite3.Connection, codigo: str, estado: str, por: str = "Didi") -> None:
    with db.transaccion(cx):
        n = cx.execute("UPDATE idea SET estado = ?, actualizado_en = ? WHERE codigo = ?",
                       (estado, util.ahora_utc(), codigo)).rowcount
        if not n:
            raise ErrorContenido(f"No existe la idea {codigo}.")
        db.auditar(cx, por, "idea", None, "ESTADO", {"codigo": codigo, "estado": estado})


# -------------------------------------------------------------------------------------------- campañas

def crear_campana(cx: sqlite3.Connection, producto: str, *, slug: str, nombre: str, objetivo: str, hipotesis: str,
                  oferta: str, cta: str, metrica_exito: str, meta_valor: int | None = None,
                  audiencia: str | None = None, inicio: str | None = None, fin: str | None = None,
                  presupuesto_c: int = 0, por: str = "Didi") -> int:
    with db.transaccion(cx):
        pid = _producto_id(cx, producto)
        aud_id = None
        if audiencia:
            fila = cx.execute("SELECT id FROM audiencia WHERE producto_id = ? AND slug = ?", (pid, audiencia)).fetchone()
            aud_id = fila["id"] if fila else None
        ahora = util.ahora_utc()
        cx.execute(
            """INSERT INTO campana (producto_id, slug, nombre, objetivo, audiencia_id, hipotesis, oferta, cta, metrica_exito,
                 meta_valor, inicio, fin, presupuesto_c, creado_en, actualizado_en)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(slug) DO UPDATE SET nombre=excluded.nombre, objetivo=excluded.objetivo,
                 audiencia_id=excluded.audiencia_id, hipotesis=excluded.hipotesis, oferta=excluded.oferta, cta=excluded.cta,
                 metrica_exito=excluded.metrica_exito, meta_valor=excluded.meta_valor, inicio=excluded.inicio,
                 fin=excluded.fin, presupuesto_c=excluded.presupuesto_c, actualizado_en=excluded.actualizado_en""",
            (pid, slug, nombre, objetivo, aud_id, hipotesis, oferta, cta, metrica_exito, meta_valor, inicio, fin,
             presupuesto_c, ahora, ahora))
        cid = cx.execute("SELECT id FROM campana WHERE slug = ?", (slug,)).fetchone()["id"]
        db.auditar(cx, por, "campana", cid, "GUARDAR", {"slug": slug})
    return cid


# ---------------------------------------------------------------------------------------------- piezas

def crear_pieza(cx: sqlite3.Connection, producto: str, *, formato: str, canal: str, titulo: str, tipo_afirmacion: str,
                campana: str | None = None, idea: str | None = None, fecha_prevista: str | None = None,
                plantilla: str | None = None, por: str = "Didi") -> str:
    if tipo_afirmacion not in aud.TIPOS_AFIRMACION:
        raise ErrorContenido(f"Tipo de afirmación no válido: {tipo_afirmacion}.")
    with db.transaccion(cx):
        pid = _producto_id(cx, producto)
        codigo = _siguiente(cx, "pieza", "P")
        ahora = util.ahora_utc()
        idea_id = _id_opcional(cx, "idea", "codigo", idea)
        cx.execute(
            """INSERT INTO pieza (codigo, producto_id, campana_id, idea_id, formato, canal, titulo, tipo_afirmacion,
                 fecha_prevista, plantilla, creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (codigo, pid, _id_opcional(cx, "campana", "slug", campana), idea_id, formato, canal, titulo,
             tipo_afirmacion, fecha_prevista, plantilla, ahora, ahora))
        if idea_id:
            cx.execute("UPDATE idea SET estado = 'EN_PRODUCCION', actualizado_en = ? WHERE id = ?", (ahora, idea_id))
        db.auditar(cx, por, "pieza", None, "CREAR", {"codigo": codigo})
    return codigo


def obtener_pieza(cx: sqlite3.Connection, codigo: str) -> sqlite3.Row:
    fila = cx.execute("""SELECT pz.*, pr.slug AS producto FROM pieza pz JOIN producto pr ON pr.id = pz.producto_id
                         WHERE pz.codigo = ?""", (codigo,)).fetchone()
    if fila is None:
        raise ErrorContenido(f"No existe la pieza {codigo}.")
    return fila


def version_actual(cx: sqlite3.Connection, pieza: sqlite3.Row) -> sqlite3.Row | None:
    return cx.execute("SELECT * FROM pieza_version WHERE pieza_id = ? AND numero = ?",
                      (pieza["id"], pieza["version_actual"])).fetchone()


def nueva_version(cx: sqlite3.Connection, codigo: str, contenido: dict, *, capacidades: list[str] | None = None,
                  fuentes: list[str] | None = None, autor: str = "Didi", nota: str = "") -> int:
    """Guarda una versión nueva. El contenido es un objeto con los textos (gancho, copy, cta, textos de plantilla…)."""
    if not isinstance(contenido, dict) or not contenido:
        raise ErrorContenido("El contenido de la versión debe ser un objeto con al menos un texto.")
    with db.transaccion(cx):
        p = obtener_pieza(cx, codigo)
        if p["estado"] in ("PUBLICADA", "ARCHIVADA"):
            raise ErrorContenido(f"La pieza {codigo} está {p['estado'].lower()}: crea una pieza nueva para reutilizarla.")
        numero = p["version_actual"] + 1
        cuerpo = {"contenido": contenido, "capacidades": sorted(capacidades or []), "fuentes": fuentes or []}
        hash_ = util.sha256_texto(util.a_json(cuerpo))
        cx.execute(
            """INSERT INTO pieza_version (pieza_id, numero, contenido, capacidades, fuentes, hash, autor, nota, creado_en)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (p["id"], numero, util.a_json(contenido), util.a_json(cuerpo["capacidades"]), util.a_json(cuerpo["fuentes"]),
             hash_, autor, nota, util.ahora_utc()))
        cx.execute("UPDATE pieza SET version_actual = ?, estado = 'BORRADOR', actualizado_en = ? WHERE id = ?",
                   (numero, util.ahora_utc(), p["id"]))
        db.auditar(cx, autor, "pieza", p["id"], "VERSION", {"numero": numero, "hash": hash_})
    return numero


def textos_de(contenido: dict, prefijo: str = "") -> dict[str, str]:
    """Aplana el contenido a campo → texto visible. Ignora claves técnicas (rutas, colores, números)."""
    tecnicas = {"plantilla", "formato", "formatos", "capturas", "imagen", "archivo", "color", "musica",
                "fecha_publicacion_fuente", "revisado_por_contador", "es_demostracion_guiada", "hashtags"}
    salida: dict[str, str] = {}
    for clave, valor in contenido.items():
        if clave in tecnicas:
            continue
        nombre = f"{prefijo}{clave}"
        if isinstance(valor, str) and valor.strip():
            salida[nombre] = valor
        elif isinstance(valor, dict):
            salida.update(textos_de(valor, nombre + "."))
        elif isinstance(valor, list):
            for i, elemento in enumerate(valor):
                if isinstance(elemento, str) and elemento.strip():
                    salida[f"{nombre}[{i}]"] = elemento
                elif isinstance(elemento, dict):
                    salida.update(textos_de(elemento, f"{nombre}[{i}]."))
    return salida


def pieza_para_auditar(pieza: sqlite3.Row, version: sqlite3.Row, raiz: Path) -> aud.PiezaParaAuditar:
    contenido = util.de_json(version["contenido"], {})
    fuentes = [f for f in util.de_json(version["fuentes"], []) if isinstance(f, str)]
    limites = canales.limites(pieza["canal"], raiz)
    return aud.PiezaParaAuditar(
        tipo_afirmacion=pieza["tipo_afirmacion"], canal=pieza["canal"], textos=textos_de(contenido),
        capacidades=util.de_json(version["capacidades"], []), fuentes=fuentes, cta=contenido.get("cta", ""),
        formato=pieza["formato"], fecha_publicacion_fuente=contenido.get("fecha_publicacion_fuente", ""),
        revisado_por_contador=bool(contenido.get("revisado_por_contador", False)),
        es_demostracion_guiada=bool(contenido.get("es_demostracion_guiada", False)),
        limites_canal={k: v for k, v in limites.items() if k in contenido},
    )


def auditar_pieza(cx: sqlite3.Connection, raiz: Path, codigo: str) -> aud.Informe:
    """Corre el auditor sobre la versión actual y deja la revisión registrada."""
    p = obtener_pieza(cx, codigo)
    v = version_actual(cx, p)
    if v is None:
        raise ErrorContenido(f"La pieza {codigo} no tiene contenido todavía.")
    politica = aud.Politica.desde_carpeta(raiz / "productos" / p["producto"])
    informe = aud.auditar(pieza_para_auditar(p, v, raiz), politica)
    estado = "CORRECCIONES" if informe.resultado == "RECHAZADO" else "LISTA_PARA_APROBAR"
    with db.transaccion(cx):
        cx.execute("INSERT INTO revision (pieza_id, version, revisor, resultado, hallazgos, creado_en) VALUES (?,?,?,?,?,?)",
                   (p["id"], v["numero"], "AUDITOR_AUTOMATICO", informe.resultado, util.a_json(informe.como_lista()),
                    util.ahora_utc()))
        cx.execute("UPDATE pieza SET estado = ?, actualizado_en = ? WHERE id = ?", (estado, util.ahora_utc(), p["id"]))
    return informe


def decidir(cx: sqlite3.Connection, codigo: str, decision: str, por: str, comentario: str = "") -> None:
    """Aprobación humana de la versión actual. Solo se aprueba lo que pasó el auditor sin bloqueos."""
    if decision not in ("APROBADA", "RECHAZADA", "CORRECCIONES"):
        raise ErrorContenido("La decisión debe ser APROBADA, RECHAZADA o CORRECCIONES.")
    with db.transaccion(cx):
        p = obtener_pieza(cx, codigo)
        v = version_actual(cx, p)
        if v is None:
            raise ErrorContenido(f"La pieza {codigo} no tiene contenido que aprobar.")
        if decision == "APROBADA":
            rev = cx.execute("SELECT resultado FROM revision WHERE pieza_id = ? AND version = ? ORDER BY id DESC LIMIT 1",
                             (p["id"], v["numero"])).fetchone()
            if rev is None:
                raise ErrorContenido("Antes de aprobar, pasa la pieza por el auditor: python -m mos pieza auditar " + codigo)
            if rev["resultado"] == "RECHAZADO":
                raise ErrorContenido("El auditor encontró bloqueos en esta versión. Corrígela y vuelve a auditar.")
        cx.execute("""INSERT INTO aprobacion (pieza_id, version, hash_version, decision, comentario, decidido_por, decidido_en)
                      VALUES (?,?,?,?,?,?,?)""",
                   (p["id"], v["numero"], v["hash"], decision, comentario, por, util.ahora_utc()))
        cx.execute("UPDATE pieza SET estado = ?, actualizado_en = ? WHERE id = ?", (decision, util.ahora_utc(), p["id"]))
        db.auditar(cx, por, "pieza", p["id"], decision, {"version": v["numero"], "comentario": comentario})


def aprobacion_vigente(cx: sqlite3.Connection, pieza: sqlite3.Row) -> sqlite3.Row | None:
    v = version_actual(cx, pieza)
    if v is None:
        return None
    a = cx.execute("SELECT * FROM aprobacion WHERE pieza_id = ? AND version = ? ORDER BY id DESC LIMIT 1",
                   (pieza["id"], v["numero"])).fetchone()
    if a is None or a["decision"] != "APROBADA" or a["hash_version"] != v["hash"]:
        return None
    return a


# --------------------------------------------------------------------------------------- publicaciones

def preparar_publicacion(cx: sqlite3.Connection, codigo: str, *, canal: str | None = None, copy: str | None = None,
                         archivos: list[str] | None = None, fecha_prevista: str | None = None,
                         metodo: str = "MANUAL", cuenta: str = "", por: str = "Didi") -> int:
    """Deja listo el paquete para publicar. No publica nada: eso lo hace Didi o su programador nativo."""
    if metodo == "API_OFICIAL" and not _autorizado(cx, "PUBLICACION_API"):
        raise ErrorContenido("Publicar por API necesita la autorización PUBLICACION_API de Didi.")
    with db.transaccion(cx):
        p = obtener_pieza(cx, codigo)
        if aprobacion_vigente(cx, p) is None:
            raise ErrorContenido(f"La pieza {codigo} no tiene una aprobación vigente para su versión actual.")
        v = version_actual(cx, p)
        contenido = util.de_json(v["contenido"], {})
        texto = copy if copy is not None else contenido.get("copy", "")
        if not texto:
            raise ErrorContenido("El paquete necesita el texto que acompaña la publicación (copy).")
        ahora = util.ahora_utc()
        cur = cx.execute(
            """INSERT INTO publicacion (pieza_id, version, canal, cuenta, copy, archivos, fecha_prevista, metodo,
                 creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (p["id"], v["numero"], canal or p["canal"], cuenta, texto, util.a_json(archivos or []),
             fecha_prevista or p["fecha_prevista"], metodo, ahora, ahora))
        db.auditar(cx, por, "publicacion", cur.lastrowid, "PREPARAR", {"pieza": codigo})
    return cur.lastrowid


def _autorizado(cx: sqlite3.Connection, categoria: str) -> bool:
    return cx.execute("SELECT 1 FROM autorizacion WHERE categoria = ? AND revocada_en IS NULL LIMIT 1",
                      (categoria,)).fetchone() is not None


def marcar_programada(cx: sqlite3.Connection, publicacion_id: int, fecha_prevista: str, por: str = "Didi") -> None:
    with db.transaccion(cx):
        n = cx.execute("""UPDATE publicacion SET estado = 'PROGRAMADA', fecha_prevista = ?, actualizado_en = ?
                          WHERE id = ? AND estado IN ('PAQUETE_LISTO','PROGRAMADA')""",
                       (fecha_prevista, util.ahora_utc(), publicacion_id)).rowcount
        if not n:
            raise ErrorContenido(f"La publicación {publicacion_id} no existe o ya terminó.")
        db.auditar(cx, por, "publicacion", publicacion_id, "PROGRAMAR", {"fecha": fecha_prevista})


def confirmar_publicacion(cx: sqlite3.Connection, publicacion_id: int, *, url: str | None = None,
                          id_externo: str | None = None, publicada_en: str | None = None, por: str = "Didi") -> None:
    """Solo con prueba: la URL pública o el id que devolvió la red. La base lo exige también."""
    if not (url or id_externo):
        raise ErrorContenido("Para marcarla como publicada hace falta la URL pública o el id de la red.")
    if url and not url.startswith("https://"):
        raise ErrorContenido("La URL de la publicación debe empezar con https://")
    with db.transaccion(cx):
        fila = cx.execute("SELECT pieza_id, estado FROM publicacion WHERE id = ?", (publicacion_id,)).fetchone()
        if fila is None:
            raise ErrorContenido(f"No existe la publicación {publicacion_id}.")
        ahora = util.ahora_utc()
        cx.execute("""UPDATE publicacion SET estado = 'PUBLICADA', url = ?, id_externo = ?, publicada_en = ?,
                        error = NULL, actualizado_en = ? WHERE id = ?""",
                   (url, id_externo, publicada_en or ahora, ahora, publicacion_id))
        cx.execute("UPDATE pieza SET estado = 'PUBLICADA', actualizado_en = ? WHERE id = ?", (ahora, fila["pieza_id"]))
        db.auditar(cx, por, "publicacion", publicacion_id, "CONFIRMAR", {"url": url, "id_externo": id_externo})


def registrar_fallo(cx: sqlite3.Connection, publicacion_id: int, error: str, por: str = "Didi") -> None:
    with db.transaccion(cx):
        n = cx.execute("""UPDATE publicacion SET estado = 'FALLIDA', error = ?, reintentos = reintentos + 1,
                          actualizado_en = ? WHERE id = ?""", (error, util.ahora_utc(), publicacion_id)).rowcount
        if not n:
            raise ErrorContenido(f"No existe la publicación {publicacion_id}.")
        db.registrar_error(cx, "publicacion", "FALLO_PUBLICACION", f"Publicación {publicacion_id}: {error}")
        db.auditar(cx, por, "publicacion", publicacion_id, "FALLO", {"error": error})


def calendario(cx: sqlite3.Connection, desde: str, hasta: str, producto: str | None = None) -> list[sqlite3.Row]:
    sql = """SELECT pz.codigo, pz.fecha_prevista, pz.canal, pz.formato, pz.titulo, pz.estado, pz.tipo_afirmacion,
                    pr.slug AS producto, c.slug AS campana
             FROM pieza pz JOIN producto pr ON pr.id = pz.producto_id LEFT JOIN campana c ON c.id = pz.campana_id
             WHERE pz.fecha_prevista BETWEEN ? AND ?"""
    params: list = [desde, hasta]
    if producto:
        sql += " AND pr.slug = ?"
        params.append(producto)
    return cx.execute(sql + " ORDER BY pz.fecha_prevista, pz.id", params).fetchall()
