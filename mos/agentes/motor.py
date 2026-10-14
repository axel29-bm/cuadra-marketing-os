"""Motor de tareas: crea, prepara, recibe, valida y cierra el trabajo de los agentes.

Garantías:
- Idempotencia: la misma tarea activa no se crea dos veces.
- Sin ciclos: profundidad máxima 3 y un tope de subtareas por tarea.
- Sin éxito falso: una tarea solo se completa si su salida cumple el esquema y los criterios.
- Sin silencio: cada paso y cada error queda en tarea_evento.
- Sin gasto oculto: el modo externo está apagado por defecto, pide autorización y tiene tope diario.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .. import db, util
from ..config import Config
from . import proveedores
from .contrato import ErrorContrato, describir_esquema, validar_esquema
from .registro import agente, ruta_prompt

ACTIVOS = ("PENDIENTE", "PREPARADA", "EN_CURSO", "REQUIERE_APROBACION")
PROFUNDIDAD_MAXIMA = 3


class ErrorTarea(RuntimeError):
    pass


def _evento(cx: sqlite3.Connection, tarea_id: int, tipo: str, detalle: Any = "") -> None:
    texto = detalle if isinstance(detalle, str) else util.a_json(detalle)
    cx.execute("INSERT INTO tarea_evento (tarea_id, en, tipo, detalle) VALUES (?,?,?,?)",
               (tarea_id, util.ahora_utc(), tipo, texto[:8000]))


def _siguiente_codigo(cx: sqlite3.Connection) -> str:
    n = cx.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM tarea").fetchone()[0]
    return f"T-{n:04d}"


def obtener(cx: sqlite3.Connection, codigo: str) -> sqlite3.Row:
    fila = cx.execute("SELECT * FROM tarea WHERE codigo = ?", (codigo,)).fetchone()
    if fila is None:
        raise ErrorTarea(f"No existe la tarea {codigo}.")
    return fila


def crear(cx: sqlite3.Connection, agente_id: str, objetivo: str, entradas: dict, *,
          restricciones: list[str] | None = None, padre: str | None = None, modo: str = "ASISTIDO",
          vence_en_horas: int | None = 72) -> str:
    a = agente(agente_id)
    problemas = validar_esquema(entradas, a.entradas)
    if problemas:
        raise ErrorContrato(problemas)
    modo_final = "DETERMINISTA" if a.modo == "DETERMINISTA" else modo
    clave = util.sha256_texto(util.a_json({"agente": a.id, "objetivo": objetivo, "entradas": entradas}))
    with db.transaccion(cx):
        existente = cx.execute(
            f"SELECT codigo FROM tarea WHERE clave_idempotencia = ? AND estado IN ({','.join('?' * len(ACTIVOS))})",
            (clave, *ACTIVOS)).fetchone()
        if existente:
            return existente["codigo"]
        padre_id, profundidad = None, 0
        if padre:
            p = obtener(cx, padre)
            padre_id, profundidad = p["id"], p["profundidad"] + 1
            if profundidad > PROFUNDIDAD_MAXIMA:
                raise ErrorTarea(f"Se alcanzó la profundidad máxima de subtareas ({PROFUNDIDAD_MAXIMA}).")
            hijas = cx.execute("SELECT COUNT(*) FROM tarea WHERE padre_id = ?", (padre_id,)).fetchone()[0]
            if hijas >= agente(p["agente"]).max_subtareas:
                raise ErrorTarea(f"La tarea {padre} ya tiene {hijas} subtareas; no se crean más.")
        ahora = util.ahora_utc()
        vence = None
        if vence_en_horas:
            vence = (datetime.now(timezone.utc) + timedelta(hours=vence_en_horas)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        codigo = _siguiente_codigo(cx)
        cur = cx.execute(
            """INSERT INTO tarea (codigo, agente, objetivo, entradas, restricciones, salida_esperada, estado, modo,
                                   requiere_aprobacion, max_intentos, padre_id, profundidad, clave_idempotencia,
                                   vence_en, creado_en, actualizado_en)
               VALUES (?,?,?,?,?,?, 'PENDIENTE', ?,?,?,?,?,?,?,?,?)""",
            (codigo, a.id, objetivo, util.a_json(entradas), util.a_json(restricciones or []),
             describir_esquema(a.salida), modo_final, int(a.requiere_aprobacion), a.max_intentos,
             padre_id, profundidad, clave, vence, ahora, ahora))
        _evento(cx, cur.lastrowid, "CREADA", {"agente": a.id, "modo": modo_final})
    return codigo


def paquete(cfg: Config, tarea: sqlite3.Row, contexto_texto: str = "") -> str:
    """Prompt completo y autocontenido para el modo asistido, local o externo."""
    a = agente(tarea["agente"])
    rol = ""
    ruta = ruta_prompt(cfg.raiz, a)
    if ruta and ruta.exists():
        comun = cfg.raiz / "prompts" / "_comun.md"
        rol = (comun.read_text(encoding="utf-8").strip() + "\n\n" if comun.exists() else "") + ruta.read_text(encoding="utf-8")
    restricciones = util.de_json(tarea["restricciones"], [])
    partes = [
        f"# Tarea {tarea['codigo']} · {a.nombre}",
        rol.strip(),
        "## Objetivo", tarea["objetivo"],
        "## Entradas", "```json\n" + json.dumps(util.de_json(tarea["entradas"], {}), ensure_ascii=False, indent=2) + "\n```",
    ]
    if contexto_texto:
        partes += ["## Contexto del producto (fuente de verdad)", contexto_texto.strip()]
    if restricciones:
        partes += ["## Restricciones de esta tarea", "\n".join(f"- {r}" for r in restricciones)]
    if a.no_hace:
        partes += ["## Este rol no hace", "\n".join(f"- {r}" for r in a.no_hace)]
    partes += [
        "## Formato de salida",
        "Responde solo con un objeto JSON válido, sin texto antes ni después, con esta forma:",
        "```\n" + tarea["salida_esperada"] + "\n```",
        "Si no puedes cumplir algo con evidencia, dilo en el campo correspondiente en vez de inventarlo.",
    ]
    return "\n\n".join(p for p in partes if p)


def preparar(cx: sqlite3.Connection, cfg: Config, codigo: str, contexto_texto: str = "") -> Path:
    t = obtener(cx, codigo)
    if t["estado"] not in ("PENDIENTE", "PREPARADA", "EN_CURSO"):
        raise ErrorTarea(f"La tarea {codigo} está {t['estado'].lower()} y no se puede preparar.")
    carpeta = cfg.tareas / codigo
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "PROMPT.md").write_text(paquete(cfg, t, contexto_texto), encoding="utf-8")
    (carpeta / "LEEME.txt").write_text(
        "1. Copia PROMPT.md en tu asistente de IA (o pídele a Claude Code que lo resuelva).\n"
        "2. Guarda la respuesta JSON en resultado.json, en esta misma carpeta.\n"
        f"3. Ejecuta: python -m mos tarea completar {codigo}\n", encoding="utf-8")
    with db.transaccion(cx):
        cx.execute("UPDATE tarea SET estado = 'PREPARADA', actualizado_en = ? WHERE id = ?", (util.ahora_utc(), t["id"]))
        _evento(cx, t["id"], "PREPARADA", str(carpeta))
    return carpeta


def registrar_resultado(cx: sqlite3.Connection, codigo: str, resultado: Any, contexto: dict | None = None,
                        evidencias: list[str] | None = None, coste_real_c: int = 0) -> str:
    """Valida la salida contra el contrato. Devuelve el estado final de la tarea."""
    t = obtener(cx, codigo)
    if t["estado"] not in ("PENDIENTE", "PREPARADA", "EN_CURSO"):
        raise ErrorTarea(f"La tarea {codigo} está {t['estado'].lower()}: no acepta resultados.")
    a = agente(t["agente"])
    entradas = util.de_json(t["entradas"], {})
    problemas = validar_esquema(resultado, a.salida)
    if not problemas:
        for nombre, criterio in a.criterios:
            try:
                problemas += [f"[{nombre}] {p}" for p in criterio(entradas, resultado, contexto or {})]
            except Exception as e:  # un criterio roto no aprueba nada
                problemas.append(f"[{nombre}] el criterio falló: {e}")
    intentos = t["intentos"] + 1
    ahora = util.ahora_utc()
    with db.transaccion(cx):
        if problemas:
            estado = "FALLIDA" if intentos >= t["max_intentos"] else "EN_CURSO"
            errores = util.de_json(t["errores"], []) + [{"intento": intentos, "en": ahora, "problemas": problemas}]
            cx.execute("UPDATE tarea SET estado=?, intentos=?, errores=?, actualizado_en=? WHERE id=?",
                       (estado, intentos, util.a_json(errores), ahora, t["id"]))
            _evento(cx, t["id"], "RECHAZADA", {"intento": intentos, "problemas": problemas})
            if estado == "FALLIDA":
                db.registrar_error(cx, "agentes", "TAREA_FALLIDA", f"{codigo} agotó {intentos} intentos", "\n".join(problemas))
            return estado
        estado = "REQUIERE_APROBACION" if t["requiere_aprobacion"] else "COMPLETADA"
        cx.execute("""UPDATE tarea SET estado=?, intentos=?, resultado=?, evidencias=?, coste_real_c=coste_real_c+?,
                      actualizado_en=? WHERE id=?""",
                   (estado, intentos, util.a_json(resultado), util.a_json(evidencias or []), coste_real_c, ahora, t["id"]))
        _evento(cx, t["id"], "VALIDADA", {"estado": estado})
    return estado


def aprobar(cx: sqlite3.Connection, codigo: str, por: str, comentario: str = "") -> None:
    t = obtener(cx, codigo)
    if t["estado"] != "REQUIERE_APROBACION":
        raise ErrorTarea(f"La tarea {codigo} no está esperando aprobación.")
    with db.transaccion(cx):
        cx.execute("UPDATE tarea SET estado='COMPLETADA', actualizado_en=? WHERE id=?", (util.ahora_utc(), t["id"]))
        _evento(cx, t["id"], "APROBADA", {"por": por, "comentario": comentario})
        db.auditar(cx, por, "tarea", t["id"], "APROBAR", {"comentario": comentario})


def cancelar(cx: sqlite3.Connection, codigo: str, motivo: str) -> None:
    t = obtener(cx, codigo)
    if t["estado"] not in ACTIVOS:
        raise ErrorTarea(f"La tarea {codigo} ya terminó ({t['estado'].lower()}).")
    with db.transaccion(cx):
        cx.execute("UPDATE tarea SET estado='CANCELADA', actualizado_en=? WHERE id=?", (util.ahora_utc(), t["id"]))
        _evento(cx, t["id"], "CANCELADA", motivo)


def revisar_vencidas(cx: sqlite3.Connection) -> list[str]:
    """Las tareas que pasan su plazo fallan con su motivo, en vez de quedar colgadas para siempre."""
    ahora = util.ahora_utc()
    filas = cx.execute(
        "SELECT codigo, id FROM tarea WHERE vence_en IS NOT NULL AND vence_en < ? AND estado IN ('PENDIENTE','PREPARADA','EN_CURSO')",
        (ahora,)).fetchall()
    vencidas = []
    with db.transaccion(cx):
        for f in filas:
            cx.execute("UPDATE tarea SET estado='FALLIDA', errores=json_insert(errores, '$[#]', json(?)), actualizado_en=? WHERE id=?",
                       (util.a_json({"en": ahora, "problemas": ["Plazo vencido sin resultado"]}), ahora, f["id"]))
            _evento(cx, f["id"], "VENCIDA")
            db.registrar_error(cx, "agentes", "TAREA_VENCIDA", f"{f['codigo']} venció sin resultado")
            vencidas.append(f["codigo"])
    return vencidas


def ejecutar(cx: sqlite3.Connection, cfg: Config, codigo: str, contexto: dict | None = None,
             contexto_texto: str = "") -> str:
    """Ejecuta según el modo. En modo asistido solo prepara el paquete y espera el resultado."""
    t = obtener(cx, codigo)
    a = agente(t["agente"])
    if t["modo"] == "DETERMINISTA":
        if a.ejecutor is None:
            raise ErrorTarea(f"El agente {a.id} no tiene ejecutor determinista registrado.")
        with db.transaccion(cx):
            cx.execute("UPDATE tarea SET estado='EN_CURSO', actualizado_en=? WHERE id=?", (util.ahora_utc(), t["id"]))
        resultado = a.ejecutor(cx, util.de_json(t["entradas"], {}))
        return registrar_resultado(cx, codigo, resultado, contexto)
    if t["modo"] == "ASISTIDO":
        preparar(cx, cfg, codigo, contexto_texto)
        return "PREPARADA"
    texto = paquete(cfg, t, contexto_texto)
    with db.transaccion(cx):
        cx.execute("UPDATE tarea SET estado='EN_CURSO', actualizado_en=? WHERE id=?", (util.ahora_utc(), t["id"]))
    try:
        respuesta = proveedores.completar(cx, cfg, t["modo"], texto)
    except proveedores.ErrorProveedor as e:
        with db.transaccion(cx):
            _evento(cx, t["id"], "ERROR_PROVEEDOR", str(e))
            db.registrar_error(cx, "agentes", "PROVEEDOR", str(e))
        raise
    with db.transaccion(cx):
        _evento(cx, t["id"], "LLAMADA_IA", {"modo": t["modo"], "modelo": respuesta.modelo})
    return registrar_resultado(cx, codigo, respuesta.json, contexto)
