"""Base de datos local SQLite: conexión, migraciones, transacciones y copias de seguridad."""

from __future__ import annotations

import contextlib
import sqlite3
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Iterator

from . import util

PRAGMAS = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = FULL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA busy_timeout = 5000",
)


class BaseMasNueva(RuntimeError):
    """La base fue creada por una versión más nueva del programa."""


def _migraciones() -> list[tuple[int, str, str]]:
    salida = []
    for entrada in resources.files("mos.migraciones").iterdir():
        nombre = entrada.name
        if nombre.endswith(".sql") and nombre[:4].isdigit():
            salida.append((int(nombre[:4]), nombre, entrada.read_text(encoding="utf-8")))
    return sorted(salida)


def version_esquema() -> int:
    migs = _migraciones()
    return migs[-1][0] if migs else 0


def conectar(ruta: Path) -> sqlite3.Connection:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(ruta, isolation_level=None)  # transacciones explícitas
    cx.row_factory = sqlite3.Row
    for p in PRAGMAS:
        cx.execute(p)
    return cx


def migrar(cx: sqlite3.Connection) -> list[str]:
    """Aplica las migraciones pendientes, una transacción por migración. Devuelve las aplicadas."""
    actual = cx.execute("PRAGMA user_version").fetchone()[0]
    ultima = version_esquema()
    if actual > ultima:
        raise BaseMasNueva(f"La base está en la versión {actual} y este programa llega a la {ultima}.")
    aplicadas = []
    for numero, nombre, sql in _migraciones():
        if numero <= actual:
            continue
        cx.execute("BEGIN IMMEDIATE")
        try:
            for sentencia in _sentencias(sql):
                cx.execute(sentencia)
            cx.execute(f"PRAGMA user_version = {numero}")
            cx.execute("COMMIT")
        except Exception:
            cx.execute("ROLLBACK")
            raise
        aplicadas.append(nombre)
    return aplicadas


def _sentencias(sql: str) -> Iterator[str]:
    """Divide un script en sentencias completas usando el propio analizador de SQLite."""
    buffer = ""
    for linea in sql.splitlines(keepends=True):
        if not buffer and linea.strip().startswith("--"):
            continue
        buffer += linea
        if sqlite3.complete_statement(buffer):
            if buffer.strip():
                yield buffer.strip()
            buffer = ""
    if buffer.strip():
        raise ValueError("La migración termina con una sentencia incompleta.")


@contextlib.contextmanager
def transaccion(cx: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Una operación = una transacción. Si algo falla, no queda nada a medias."""
    cx.execute("BEGIN IMMEDIATE")
    try:
        yield cx
    except BaseException:
        cx.execute("ROLLBACK")
        raise
    else:
        cx.execute("COMMIT")


def auditar(cx: sqlite3.Connection, actor: str, entidad: str, entidad_id: int | None, accion: str,
            detalle: dict | None = None) -> None:
    cx.execute(
        "INSERT INTO auditoria (en, actor, entidad, entidad_id, accion, detalle) VALUES (?,?,?,?,?,?)",
        (util.ahora_utc(), actor, entidad, entidad_id, accion, util.a_json(detalle or {})),
    )


def registrar_error(cx: sqlite3.Connection, modulo: str, codigo: str, mensaje: str, detalle: str = "") -> int:
    """Los errores nunca se pierden en silencio: quedan en la base y se ven en la pantalla Hoy."""
    cur = cx.execute(
        "INSERT INTO registro_error (en, modulo, codigo, mensaje, detalle) VALUES (?,?,?,?,?)",
        (util.ahora_utc(), modulo, codigo, mensaje, detalle[:4000]),
    )
    return int(cur.lastrowid)


def respaldar(cx: sqlite3.Connection, carpeta: Path, conservar: int = 14) -> Path:
    """Copia consistente con la API de respaldo de SQLite, verificada con integrity_check."""
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")   # con microsegundos: dos copias seguidas no chocan
    destino = carpeta / f"mos-{marca}.db"
    temporal = destino.with_suffix(".tmp")
    with contextlib.closing(sqlite3.connect(temporal)) as copia:
        cx.backup(copia)
        estado = copia.execute("PRAGMA integrity_check").fetchone()[0]
        if estado != "ok":
            raise RuntimeError(f"La copia no pasó la comprobación de integridad: {estado}")
    temporal.replace(destino)
    copias = sorted(carpeta.glob("mos-*.db"))
    for vieja in copias[:-conservar]:
        vieja.unlink()
    return destino
