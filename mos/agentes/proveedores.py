"""Proveedores de IA con la interfaz compatible con OpenAI (Ollama local o un servicio externo).

Ambos son opcionales. El modo por defecto es ASISTIDO: el sistema prepara el prompt y una
persona lo resuelve con la IA que ya tiene, sin claves ni consumo automático.

El modo EXTERNO está apagado hasta que exista una autorización vigente en la tabla `autorizacion`
(categoría IA_EXTERNA), una clave en la variable de entorno MOS_IA_CLAVE y queden llamadas en el
tope diario. Ningún dato personal sale de la PC: los prompts con correos o teléfonos se rechazan.
"""

from __future__ import annotations

import json
import re
import sqlite3
import urllib.error
import urllib.request
from dataclasses import dataclass

from .. import util
from ..config import Config, clave_ia_externa

RE_PERSONAL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|(?<!\d)9\d{2}[ -]?\d{3}[ -]?\d{3}(?!\d)")


class ErrorProveedor(RuntimeError):
    pass


@dataclass
class Respuesta:
    json: object
    modelo: str
    texto: str


def autorizado_externo(cx: sqlite3.Connection) -> bool:
    fila = cx.execute(
        "SELECT 1 FROM autorizacion WHERE categoria = 'IA_EXTERNA' AND revocada_en IS NULL LIMIT 1").fetchone()
    return fila is not None


def llamadas_hoy(cx: sqlite3.Connection) -> int:
    hoy = util.ahora_utc()[:10]
    return cx.execute(
        "SELECT COUNT(*) FROM tarea_evento WHERE tipo = 'LLAMADA_IA' AND substr(en, 1, 10) = ?", (hoy,)).fetchone()[0]


def completar(cx: sqlite3.Connection, cfg: Config, modo: str, prompt: str, timeout_s: int = 180) -> Respuesta:
    if RE_PERSONAL.search(prompt):
        raise ErrorProveedor("El prompt contiene un correo o un teléfono. Los datos personales no salen de la PC.")
    if llamadas_hoy(cx) >= cfg.ia_limite_diario:
        raise ErrorProveedor(f"Se alcanzó el tope diario de {cfg.ia_limite_diario} llamadas de IA (MOS_IA_LIMITE_DIARIO).")
    if modo == "LOCAL":
        url = cfg.ia_url or "http://127.0.0.1:11434/v1"
        clave = None
    elif modo == "EXTERNO":
        if not autorizado_externo(cx):
            raise ErrorProveedor("El modo externo no está autorizado. Didi debe otorgarlo: python -m mos autorizar IA_EXTERNA.")
        url, clave = cfg.ia_url, clave_ia_externa()
        if not url or not clave:
            raise ErrorProveedor("Faltan MOS_IA_URL o MOS_IA_CLAVE en el entorno.")
    else:
        raise ErrorProveedor(f"El modo {modo} no llama a ningún proveedor.")
    if not cfg.ia_modelo:
        raise ErrorProveedor("Falta MOS_IA_MODELO (por ejemplo, el nombre del modelo de Ollama).")
    cuerpo = json.dumps({
        "model": cfg.ia_modelo,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    cabeceras = {"Content-Type": "application/json"}
    if clave:
        cabeceras["Authorization"] = f"Bearer {clave}"
    peticion = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=cuerpo, headers=cabeceras, method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=timeout_s) as r:
            datos = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ErrorProveedor(f"El proveedor respondió {e.code}: {e.read()[:300].decode('utf-8', 'replace')}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ErrorProveedor(f"No se pudo conectar con el proveedor en {url}: {e}") from e
    try:
        texto = datos["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ErrorProveedor("Respuesta del proveedor sin contenido.") from e
    return Respuesta(json=extraer_json(texto), modelo=datos.get("model", cfg.ia_modelo), texto=texto)


def extraer_json(texto: str) -> object:
    """Acepta JSON puro o dentro de un bloque ```json. Cualquier otra cosa es un error claro."""
    limpio = texto.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", limpio, re.S)
    if m:
        limpio = m.group(1).strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError as e:
        raise ErrorProveedor(f"La respuesta no es JSON válido: {e}") from e
