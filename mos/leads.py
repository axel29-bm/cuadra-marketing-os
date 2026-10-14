"""Leads: interesados en un producto, guardados en la PC, con consentimiento y sin duplicados.

Reglas (Ley 29733, su reglamento D.S. 016-2024-JUS y Ley 28493; ver docs/EMBUDOS-Y-LEADS.md):
- Se guarda la prueba del consentimiento: fecha, versión del texto aceptado y medio.
- La publicidad necesita un consentimiento aparte. Sin él, solo se responde lo que la persona pidió.
- Quien pide la baja deja de recibir publicidad, y su contacto queda en la lista de supresión (solo el hash).
- La persona puede pedir sus datos (exportar) o que se borren (suprimir). Ambas cosas se hacen con un comando.
- Los datos personales nunca salen en prompts de IA, registros, capturas ni ejemplos.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

from . import db, util

ESTADOS = ("NUEVO", "CONTACTADO", "CUALIFICADO", "DEMO_AGENDADA", "DEMO_HECHA", "BETA", "PROPUESTA", "GANADO",
           "PERDIDO", "NO_CONTACTAR")
TERMINALES = ("GANADO", "PERDIDO", "NO_CONTACTAR")


class ErrorLead(ValueError):
    pass


def normalizar_email(email: str | None) -> str | None:
    if not email or not email.strip():
        return None
    e = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", e):
        raise ErrorLead(f"Correo no válido: {e}")
    return e


def normalizar_telefono(telefono: str | None) -> str | None:
    if not telefono or not telefono.strip():
        return None
    digitos = re.sub(r"\D", "", telefono)
    if len(digitos) == 9 and digitos.startswith("9"):
        return "+51" + digitos
    if len(digitos) == 11 and digitos.startswith("519"):
        return "+" + digitos
    if 8 <= len(digitos) <= 15:
        return "+" + digitos
    raise ErrorLead("Teléfono no válido.")


def _hash_contacto(valor: str) -> str:
    return util.sha256_texto("contacto:" + valor)


def _suprimido(cx: sqlite3.Connection, email: str | None, telefono: str | None) -> str | None:
    for v in (email, telefono):
        if v:
            fila = cx.execute("SELECT motivo FROM lista_supresion WHERE hash = ?", (_hash_contacto(v),)).fetchone()
            if fila:
                return fila["motivo"]
    return None


def _evento(cx: sqlite3.Connection, lead_id: int, tipo: str, detalle: str = "") -> None:
    cx.execute("INSERT INTO lead_evento (lead_id, en, tipo, detalle) VALUES (?,?,?,?)",
               (lead_id, util.ahora_utc(), tipo, detalle))


def registrar(cx: sqlite3.Connection, producto: str, *, fuente: str, email: str | None = None,
              telefono: str | None = None, nombre: str = "", problema_principal: str = "",
              empresas_que_lleva: int | None = None, campana: str | None = None, consentimiento: bool = False,
              consentimiento_publicidad: bool = False, finalidad: str = "", consentimiento_version: str | None = None,
              consentimiento_medio: str | None = None, consentimiento_en: str | None = None,
              notas: str = "") -> tuple[str, bool]:
    """Registra o actualiza un lead. Devuelve (uid, es_nuevo). Procesar dos veces no duplica."""
    em, tel = normalizar_email(email), normalizar_telefono(telefono)
    if not em and not tel:
        raise ErrorLead("Un lead necesita un correo o un teléfono.")
    if consentimiento_publicidad and not consentimiento:
        raise ErrorLead("El consentimiento para publicidad requiere también el consentimiento principal.")
    if consentimiento and not finalidad:
        raise ErrorLead("Indica para qué se usarán los datos (finalidad) al registrar el consentimiento.")
    ahora = util.ahora_utc()
    with db.transaccion(cx):
        pid = cx.execute("SELECT id FROM producto WHERE slug = ?", (producto,)).fetchone()
        if pid is None:
            raise ErrorLead(f"No existe el producto «{producto}».")
        campana_id = None
        if campana:
            fila = cx.execute("SELECT id FROM campana WHERE slug = ?", (campana,)).fetchone()
            campana_id = fila["id"] if fila else None
        suprimido = _suprimido(cx, em, tel)
        if suprimido == "BAJA":
            consentimiento_publicidad = False
        existente = cx.execute(
            "SELECT * FROM lead WHERE (email IS NOT NULL AND email = ?) OR (telefono IS NOT NULL AND telefono = ?) LIMIT 1",
            (em, tel)).fetchone()
        if existente:
            cambios = {
                "email": existente["email"] or em,
                "telefono": existente["telefono"] or tel,
                "nombre": existente["nombre"] or nombre,
                "problema_principal": existente["problema_principal"] or problema_principal,
                "empresas_que_lleva": existente["empresas_que_lleva"] if existente["empresas_que_lleva"] is not None
                else empresas_que_lleva,
            }
            sets = ", ".join(f"{k} = ?" for k in cambios)
            cx.execute(f"UPDATE lead SET {sets}, actualizado_en = ? WHERE id = ?",
                       (*cambios.values(), ahora, existente["id"]))
            if consentimiento and not existente["consentimiento"]:
                cx.execute("""UPDATE lead SET consentimiento = 1, finalidad = ?, consentimiento_en = ?,
                              consentimiento_version = ?, consentimiento_medio = ? WHERE id = ?""",
                           (finalidad, consentimiento_en or ahora, consentimiento_version, consentimiento_medio,
                            existente["id"]))
            if consentimiento_publicidad and not existente["consentimiento_publicidad"] and existente["baja_en"] is None:
                cx.execute("UPDATE lead SET consentimiento_publicidad = 1 WHERE id = ?", (existente["id"],))
            _evento(cx, existente["id"], "REINGRESO", f"fuente={fuente}")
            return existente["uid"], False
        uid = util.uid()
        clave = _hash_contacto(em or tel)
        cur = cx.execute(
            """INSERT INTO lead (uid, ingreso_en, producto_id, fuente, campana_id, problema_principal, nombre, email,
                 telefono, empresas_que_lleva, estado, consentimiento, consentimiento_publicidad, finalidad,
                 consentimiento_en, consentimiento_version, consentimiento_medio, clave_dedup, notas, actualizado_en,
                 seguimiento_en, proxima_accion)
               VALUES (?,?,?,?,?,?,?,?,?,?,'NUEVO',?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, ahora, pid["id"], fuente, campana_id, problema_principal, nombre, em, tel, empresas_que_lleva,
             int(consentimiento), int(consentimiento_publicidad), finalidad,
             (consentimiento_en or ahora) if consentimiento else None, consentimiento_version, consentimiento_medio,
             clave, notas, ahora, util.hoy_lima().isoformat(), "Responder y preguntar qué le interesa"))
        _evento(cx, cur.lastrowid, "INGRESO", f"fuente={fuente}")
        db.auditar(cx, "sistema", "lead", cur.lastrowid, "INGRESO", {"uid": uid, "fuente": fuente})
    return uid, True


def _por_uid(cx: sqlite3.Connection, uid: str) -> sqlite3.Row:
    fila = cx.execute("SELECT * FROM lead WHERE uid = ?", (uid,)).fetchone()
    if fila is None:
        raise ErrorLead(f"No existe el lead {uid}.")
    return fila


def actualizar(cx: sqlite3.Connection, uid: str, *, estado: str | None = None, proxima_accion: str | None = None,
               seguimiento_en: str | None = None, nota: str | None = None, por: str = "Didi") -> None:
    if estado and estado not in ESTADOS:
        raise ErrorLead(f"Estado no válido: {estado}.")
    with db.transaccion(cx):
        lead = _por_uid(cx, uid)
        if estado == "NO_CONTACTAR":
            _baja(cx, lead)
        campos, valores = [], []
        for nombre, valor in (("estado", estado), ("proxima_accion", proxima_accion), ("seguimiento_en", seguimiento_en)):
            if valor is not None:
                campos.append(f"{nombre} = ?")
                valores.append(valor)
        if estado in TERMINALES:
            campos.append("seguimiento_en = NULL")
        if campos:
            cx.execute(f"UPDATE lead SET {', '.join(campos)}, actualizado_en = ? WHERE id = ?",
                       (*valores, util.ahora_utc(), lead["id"]))
        if estado:
            _evento(cx, lead["id"], "ESTADO", estado)
        if nota:
            _evento(cx, lead["id"], "NOTA", nota)
        db.auditar(cx, por, "lead", lead["id"], "ACTUALIZAR", {"uid": uid, "estado": estado})


def _baja(cx: sqlite3.Connection, lead: sqlite3.Row) -> None:
    ahora = util.ahora_utc()
    cx.execute("""UPDATE lead SET consentimiento_publicidad = 0, baja_en = COALESCE(baja_en, ?), estado = 'NO_CONTACTAR',
                  seguimiento_en = NULL, actualizado_en = ? WHERE id = ?""", (ahora, ahora, lead["id"]))
    for v in (lead["email"], lead["telefono"]):
        if v:
            cx.execute("INSERT OR IGNORE INTO lista_supresion (hash, motivo, en) VALUES (?, 'BAJA', ?)",
                       (_hash_contacto(v), ahora))
    _evento(cx, lead["id"], "BAJA", "Pidió no recibir más mensajes")


def dar_de_baja(cx: sqlite3.Connection, contacto: str, por: str = "Didi") -> int:
    """Baja por correo o teléfono. Devuelve cuántos registros cambió. Sirve aunque el lead no exista."""
    em = normalizar_email(contacto) if "@" in contacto else None
    tel = None if em else normalizar_telefono(contacto)
    with db.transaccion(cx):
        filas = cx.execute("SELECT * FROM lead WHERE email = ? OR telefono = ?", (em, tel)).fetchall()
        for f in filas:
            _baja(cx, f)
        cx.execute("INSERT OR IGNORE INTO lista_supresion (hash, motivo, en) VALUES (?, 'BAJA', ?)",
                   (_hash_contacto(em or tel), util.ahora_utc()))
        db.auditar(cx, por, "lead", None, "BAJA", {"registros": len(filas)})
    return len(filas)


def exportar_titular(cx: sqlite3.Connection, contacto: str) -> dict:
    """Derecho de acceso: todo lo que se guarda de una persona, para entregárselo."""
    em = normalizar_email(contacto) if "@" in contacto else None
    tel = None if em else normalizar_telefono(contacto)
    filas = cx.execute("SELECT * FROM lead WHERE email = ? OR telefono = ?", (em, tel)).fetchall()
    salida = []
    for f in filas:
        eventos = [dict(e) for e in cx.execute(
            "SELECT en, tipo, detalle FROM lead_evento WHERE lead_id = ? ORDER BY id", (f["id"],))]
        datos = {k: f[k] for k in f.keys() if k not in ("id", "clave_dedup", "producto_id", "campana_id")}
        salida.append({"datos": datos, "historial": eventos})
    return {"generado_en": util.ahora_utc(), "registros": salida}


def suprimir(cx: sqlite3.Connection, contacto: str, por: str = "Didi") -> int:
    """Derecho de supresión: borra los datos y su historial. Queda solo el hash en la lista de supresión."""
    em = normalizar_email(contacto) if "@" in contacto else None
    tel = None if em else normalizar_telefono(contacto)
    with db.transaccion(cx):
        filas = cx.execute("SELECT id, email, telefono FROM lead WHERE email = ? OR telefono = ?", (em, tel)).fetchall()
        ahora = util.ahora_utc()
        for f in filas:
            for v in (f["email"], f["telefono"]):
                if v:
                    cx.execute("INSERT OR REPLACE INTO lista_supresion (hash, motivo, en) VALUES (?, 'SUPRESION', ?)",
                               (_hash_contacto(v), ahora))
            cx.execute("DELETE FROM lead WHERE id = ?", (f["id"],))
        cx.execute("INSERT OR REPLACE INTO lista_supresion (hash, motivo, en) VALUES (?, 'SUPRESION', ?)",
                   (_hash_contacto(em or tel), ahora))
        db.auditar(cx, por, "lead", None, "SUPRIMIR", {"registros": len(filas)})
    return len(filas)


def seguimientos(cx: sqlite3.Connection, fecha: str | None = None) -> list[dict]:
    """Leads con seguimiento vencido o para hoy. Sin datos de contacto: se consultan aparte."""
    hoy = fecha or util.hoy_lima().isoformat()
    filas = cx.execute(
        f"""SELECT l.uid, l.nombre, l.estado, l.proxima_accion, l.seguimiento_en, l.consentimiento_publicidad,
                   l.problema_principal, l.empresas_que_lleva, p.slug AS producto
            FROM lead l JOIN producto p ON p.id = l.producto_id
            WHERE l.seguimiento_en IS NOT NULL AND l.seguimiento_en <= ?
              AND l.estado NOT IN ({','.join('?' * len(TERMINALES))})
            ORDER BY l.seguimiento_en, l.id""", (hoy, *TERMINALES)).fetchall()
    return [dict(f) for f in filas]


def importar_csv(cx: sqlite3.Connection, ruta: Path, producto: str, fuente: str, *, finalidad: str,
                 consentimiento_version: str, mapeo: dict[str, str] | None = None) -> dict[str, int]:
    """Importa un CSV exportado de un formulario (Tally, Google Forms…). Sin consentimiento no entra."""
    m = {"nombre": "nombre", "email": "email", "telefono": "telefono", "problema": "problema",
         "empresas": "empresas", "consentimiento": "consentimiento", "publicidad": "publicidad", "fecha": "fecha"}
    m.update(mapeo or {})
    conteo = {"nuevos": 0, "actualizados": 0, "sin_consentimiento": 0, "invalidos": 0}
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            si = lambda k: str(fila.get(m[k], "")).strip().lower() in {"1", "si", "sí", "true", "yes", "x", "acepto"}
            if not si("consentimiento"):
                conteo["sin_consentimiento"] += 1
                continue
            try:
                empresas = fila.get(m["empresas"], "").strip()
                _, nuevo = registrar(
                    cx, producto, fuente=fuente, email=fila.get(m["email"]), telefono=fila.get(m["telefono"]),
                    nombre=fila.get(m["nombre"], "").strip(), problema_principal=fila.get(m["problema"], "").strip(),
                    empresas_que_lleva=int(empresas) if empresas.isdigit() else None, consentimiento=True,
                    consentimiento_publicidad=si("publicidad"), finalidad=finalidad,
                    consentimiento_version=consentimiento_version, consentimiento_medio=f"csv:{fuente}",
                    consentimiento_en=fila.get(m["fecha"]) or None)
                conteo["nuevos" if nuevo else "actualizados"] += 1
            except ErrorLead:
                conteo["invalidos"] += 1
    return conteo


def exportar_csv(cx: sqlite3.Connection, ruta: Path, producto: str | None = None) -> int:
    """Exporta los leads a un CSV local (para Didi). El archivo contiene datos personales: no se comparte."""
    sql = """SELECT l.uid, l.ingreso_en, p.slug AS producto, l.fuente, l.nombre, l.email, l.telefono, l.problema_principal,
                    l.empresas_que_lleva, l.estado, l.proxima_accion, l.seguimiento_en, l.consentimiento,
                    l.consentimiento_publicidad, l.consentimiento_en, l.consentimiento_version, l.baja_en
             FROM lead l JOIN producto p ON p.id = l.producto_id"""
    params: list = []
    if producto:
        sql += " WHERE p.slug = ?"
        params.append(producto)
    filas = cx.execute(sql + " ORDER BY l.ingreso_en", params).fetchall()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(filas[0].keys() if filas else ["uid"])
        for fila in filas:
            w.writerow(list(fila))
    return len(filas)


def embudo(cx: sqlite3.Connection, producto: str | None = None) -> dict[str, int]:
    sql = "SELECT l.estado, COUNT(*) FROM lead l JOIN producto p ON p.id = l.producto_id"
    params: list = []
    if producto:
        sql += " WHERE p.slug = ?"
        params.append(producto)
    conteo = dict(cx.execute(sql + " GROUP BY l.estado", params).fetchall())
    return {e: conteo.get(e, 0) for e in ESTADOS}
