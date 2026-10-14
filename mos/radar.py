"""Radar de novedades: elementos detectados en fuentes oficiales, que una persona verifica.

Nada se publica como noticia sin pasar por aquí: el elemento debe estar VERIFICADO (fuente primaria
oficial y fecha de verificación, la base lo exige) antes de que una pieza de tipo NOTICIA lo use.
La lectura automática de fuentes (sitemap de El Peruano, índices de SUNAT) está en radar_lector.py.
"""

from __future__ import annotations

import sqlite3

from . import db, util
from .calidad.auditor import _es_oficial


class ErrorRadar(ValueError):
    pass


def agregar(cx: sqlite3.Connection, *, titulo: str, url: str, fuente: str | None = None, resumen: str = "",
            fecha_publicacion: str | None = None, fecha_vigencia: str | None = None, afecta_a: str = "",
            que_cambia: str = "", propuesta_contenido: str = "", advertencias: str = "") -> tuple[int, bool]:
    """Agrega un elemento. La misma URL dos veces no se duplica. Devuelve (id, es_nuevo)."""
    if not url.startswith("https://"):
        raise ErrorRadar("El enlace debe empezar con https://")
    with db.transaccion(cx):
        existente = cx.execute("SELECT id FROM radar_item WHERE url = ?", (url,)).fetchone()
        if existente:
            return existente["id"], False
        fuente_id = None
        if fuente:
            fila = cx.execute("SELECT id FROM fuente WHERE slug = ?", (fuente,)).fetchone()
            fuente_id = fila["id"] if fila else None
        cur = cx.execute(
            """INSERT INTO radar_item (fuente_id, titulo, url, resumen, fecha_publicacion, fecha_vigencia, afecta_a,
                 que_cambia, es_fuente_primaria, advertencias, propuesta_contenido, detectado_en)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fuente_id, titulo, url, resumen, fecha_publicacion, fecha_vigencia, afecta_a, que_cambia,
             int(_es_oficial(url)), advertencias, propuesta_contenido, util.ahora_utc()))
    return cur.lastrowid, True


def verificar(cx: sqlite3.Connection, item_id: int, por: str) -> None:
    """Una persona confirma que leyó la fuente primaria. Solo se puede con un enlace oficial."""
    with db.transaccion(cx):
        item = cx.execute("SELECT * FROM radar_item WHERE id = ?", (item_id,)).fetchone()
        if item is None:
            raise ErrorRadar(f"No existe el elemento {item_id}.")
        if not _es_oficial(item["url"]):
            raise ErrorRadar("Solo se verifica con un enlace a la fuente oficial (SUNAT, El Peruano, MEF, gob.pe…). "
                             "Busca la norma o el comunicado original.")
        cx.execute("""UPDATE radar_item SET estado_verificacion = 'VERIFICADA', es_fuente_primaria = 1,
                      verificado_por = ?, verificado_en = ? WHERE id = ?""", (por, util.ahora_utc(), item_id))
        db.auditar(cx, por, "radar_item", item_id, "VERIFICAR")


def descartar(cx: sqlite3.Connection, item_id: int, por: str, rumor: bool = False) -> None:
    with db.transaccion(cx):
        n = cx.execute("UPDATE radar_item SET estado_verificacion = ? WHERE id = ?",
                       ("RUMOR" if rumor else "DESCARTADA", item_id)).rowcount
        if not n:
            raise ErrorRadar(f"No existe el elemento {item_id}.")
        db.auditar(cx, por, "radar_item", item_id, "RUMOR" if rumor else "DESCARTAR")


def pendientes(cx: sqlite3.Connection, limite: int = 50) -> list[sqlite3.Row]:
    return cx.execute("""SELECT r.*, f.titulo AS fuente FROM radar_item r LEFT JOIN fuente f ON f.id = r.fuente_id
                         WHERE r.estado_verificacion = 'SIN_VERIFICAR' ORDER BY r.detectado_en DESC LIMIT ?""",
                      (limite,)).fetchall()
