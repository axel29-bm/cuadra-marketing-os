"""Métricas: lo medido separado de lo estimado, y recomendaciones que se pueden explicar.

Las métricas llegan a mano o desde los CSV que exporta cada red (Meta Business Suite, YouTube Studio,
TikTok Studio, LinkedIn). Ninguna se inventa: si no hay dato, el resumen dice «sin datos».
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
import tomllib
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from . import config, db, util

NOMBRES = ('impresiones', 'alcance', 'visualizaciones', 'retencion_promedio_ms', 'reacciones', 'comentarios',
           'compartidos', 'guardados', 'clics', 'visitas', 'leads', 'formularios', 'conversaciones', 'solicitudes_demo',
           'demos_realizadas', 'ventas', 'ingresos_c', 'horas_produccion_min', 'gasto_c', 'correcciones',
           'errores_factuales', 'fallos_publicacion')
INTERACCIONES = ("reacciones", "comentarios", "compartidos", "guardados", "clics")


class ErrorMetrica(ValueError):
    pass


def registrar(cx: sqlite3.Connection, nombre: str, valor: int, fecha: str, *, naturaleza: str = "MEDIDA",
              origen: str = "MANUAL", publicacion_id: int | None = None, campana: str | None = None,
              nota: str = "") -> None:
    """Guarda una métrica. Registrar el mismo dato dos veces lo reemplaza, no lo duplica."""
    if nombre not in NOMBRES:
        raise ErrorMetrica(f"Métrica desconocida: {nombre}. Usa una de: {', '.join(NOMBRES)}.")
    if naturaleza not in ("MEDIDA", "ESTIMADA"):
        raise ErrorMetrica("La naturaleza debe ser MEDIDA o ESTIMADA.")
    if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
        raise ErrorMetrica("El valor debe ser un entero no negativo.")
    with db.transaccion(cx):
        campana_id = None
        if campana:
            fila = cx.execute("SELECT id FROM campana WHERE slug = ?", (campana,)).fetchone()
            if fila is None:
                raise ErrorMetrica(f"No existe la campaña «{campana}».")
            campana_id = fila["id"]
        if publicacion_id is None and campana_id is None:
            raise ErrorMetrica("Una métrica pertenece a una publicación o a una campaña.")
        cx.execute("""DELETE FROM metrica WHERE publicacion_id IS ? AND campana_id IS ? AND fecha = ? AND nombre = ?
                      AND naturaleza = ? AND origen = ?""", (publicacion_id, campana_id, fecha, nombre, naturaleza, origen))
        cx.execute("""INSERT INTO metrica (publicacion_id, campana_id, fecha, nombre, valor, naturaleza, origen, nota, creado_en)
                      VALUES (?,?,?,?,?,?,?,?,?)""",
                   (publicacion_id, campana_id, fecha, nombre, valor, naturaleza, origen, nota, util.ahora_utc()))


@dataclass
class Importacion:
    filas: int = 0
    emparejadas: int = 0
    metricas: int = 0
    sin_enlace: int = 0
    sin_publicacion: int = 0
    fecha_invalida: int = 0
    no_leidas: int = 0
    reconocidas: dict[str, str] = field(default_factory=dict)    # columna del archivo → métrica o campo
    ignoradas: list[str] = field(default_factory=list)
    ejemplos_sin_publicacion: list[str] = field(default_factory=list)


def _sin_tildes(texto: str) -> str:
    """«Id. de la publicación» y «id de la publicacion» se reconocen igual: sin tildes, signos ni mayúsculas."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def alias(raiz: Path | None = None) -> tuple[dict[str, str], dict[str, str]]:
    """(columna normalizada → url|id, columna normalizada → métrica) desde semillas/metricas-csv.toml."""
    ruta = (raiz or config.RAIZ) / "semillas" / "metricas-csv.toml"
    datos = tomllib.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    campos = {_sin_tildes(a): campo for campo, nombres in datos.get("columnas", {}).items() for a in nombres}
    medidas = {_sin_tildes(a): nombre for nombre, nombres in datos.get("metricas", {}).items() for a in nombres
               if nombre in NOMBRES}
    medidas.update({_sin_tildes(n): n for n in NOMBRES})     # el nombre propio de la métrica siempre vale
    campos.setdefault("url", "url")
    return campos, medidas


def _url_normal(url: str) -> str:
    partes = urlsplit(url.strip())
    if not partes.scheme or not partes.netloc:
        return ""
    return f"{partes.netloc.lower()}{partes.path.rstrip('/')}"


def _leer_tabla(ruta: Path) -> list[list[str]]:
    datos = ruta.read_bytes()
    if datos[:2] in (b"\xff\xfe", b"\xfe\xff"):
        texto = datos.decode("utf-16")
    else:
        try:
            texto = datos.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = datos.decode("cp1252")
    try:
        dialecto = csv.Sniffer().sniff(texto[:5000], delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    return [fila for fila in csv.reader(io.StringIO(texto), dialecto) if any(c.strip() for c in fila)]


def importar_csv(cx: sqlite3.Connection, ruta: Path, *, fecha: str | None = None, revisar: bool = False,
                 raiz: Path | None = None) -> Importacion:
    """Importa el CSV de estadísticas de una red (o una planilla propia con columnas url y nombres de métrica).

    Cada fila se enlaza con una publicación PUBLICADA por su URL o por su id en la red; las demás se cuentan, no se
    adivinan. `fecha` es el día en que se tomó el dato (por defecto hoy); una columna «fecha» en AAAA-MM-DD manda sobre ella. Con `revisar` no guarda nada.
    """
    campos, medidas = alias(raiz)
    tabla = _leer_tabla(ruta)
    res = Importacion()
    # El encabezado es la primera fila (de las 5 primeras) que tiene una columna de enlace o de id.
    inicio = next((n for n, fila in enumerate(tabla[:5])
                   if any(campos.get(_sin_tildes(c)) in ("url", "id") for c in fila)), None)
    if inicio is None:
        raise ErrorMetrica("No encontré una columna con el enlace o el id de la publicación. "
                           "Agrega su nombre en semillas/metricas-csv.toml ([columnas] url o id).")
    columnas: dict[int, tuple[str, str]] = {}
    for n, nombre in enumerate(tabla[inicio]):
        clave = _sin_tildes(nombre)
        if clave in campos:
            columnas[n] = ("campo", campos[clave])
            res.reconocidas[nombre] = campos[clave]
        elif clave in medidas:
            columnas[n] = ("metrica", medidas[clave])
            res.reconocidas[nombre] = medidas[clave]
        elif nombre.strip():
            res.ignoradas.append(nombre.strip())
    por_url = {_url_normal(f["url"]): f["id"] for f in cx.execute(
        "SELECT id, url FROM publicacion WHERE estado = 'PUBLICADA' AND url IS NOT NULL")}
    por_id = {f["id_externo"]: f["id"] for f in cx.execute(
        "SELECT id, id_externo FROM publicacion WHERE estado = 'PUBLICADA' AND id_externo IS NOT NULL")}
    dia = fecha or util.hoy_lima().isoformat()
    for fila in tabla[inicio + 1:]:
        res.filas += 1
        valores = {columnas[n]: c.strip() for n, c in enumerate(fila) if n in columnas}
        url = valores.get(("campo", "url"), "")
        ident = valores.get(("campo", "id"), "")
        con_numeros = any(entero(t) is not None for (tipo, _), t in valores.items() if tipo == "metrica")
        if (not url and not ident) or not con_numeros:
            res.sin_enlace += 1          # filas de descripción o totales que algunas redes agregan
            continue
        dia_fila = valores.get(("campo", "fecha"), "")[:10] or dia
        try:
            date.fromisoformat(dia_fila)
        except ValueError:
            res.fecha_invalida += 1      # sin fecha cierta no se guarda: no se inventa el día de la medición
            continue
        pub = por_url.get(_url_normal(url)) if url else None
        pub = pub or (por_id.get(ident) if ident else None)
        if pub is None:
            res.sin_publicacion += 1
            if len(res.ejemplos_sin_publicacion) < 5:
                res.ejemplos_sin_publicacion.append(url or ident)
            continue
        res.emparejadas += 1
        for (tipo, nombre), texto in valores.items():
            if tipo != "metrica" or not texto:
                continue
            valor = entero(texto)
            if valor is None:
                res.no_leidas += 1       # mejor sin dato que con uno falso («12.5», «1,2 mil»…)
                continue
            if not revisar:
                registrar(cx, nombre, valor, dia_fila, origen="CSV", publicacion_id=pub)
            res.metricas += 1
    return res


_MILES = re.compile(r"\d{1,3}([., \u00a0])\d{3}(\1\d{3})*")


def entero(texto: str) -> int | None:
    """Un número entero escrito como lo exportan las redes: «1234», «1,234», «1.234» o «1 234».

    «12.5» o «3,7» no son enteros: devuelve None en vez de leerlos como 125 o 37.
    """
    t = texto.strip()
    if t.isdigit():
        return int(t)
    if _MILES.fullmatch(t):
        return int(re.sub(r"\D", "", t))
    return None


def resumen(cx: sqlite3.Connection, desde: str, hasta: str, producto: str | None = None) -> dict:
    """Totales por canal y por naturaleza. Toma el último valor de cada métrica por publicación."""
    sql = """
      WITH ultimo AS (
        SELECT m.*, ROW_NUMBER() OVER (PARTITION BY m.publicacion_id, m.campana_id, m.nombre, m.naturaleza
                                       ORDER BY m.fecha DESC, m.id DESC) AS rn
        FROM metrica m WHERE m.fecha BETWEEN ? AND ?)
      SELECT COALESCE(pb.canal, 'campaña') AS canal, u.nombre, u.naturaleza, SUM(u.valor) AS total
      FROM ultimo u
      LEFT JOIN publicacion pb ON pb.id = u.publicacion_id
      LEFT JOIN pieza pz ON pz.id = pb.pieza_id
      LEFT JOIN campana c ON c.id = u.campana_id
      LEFT JOIN producto pr ON pr.id = COALESCE(pz.producto_id, c.producto_id)
      WHERE u.rn = 1 AND (? IS NULL OR pr.slug = ?)
      GROUP BY 1, 2, 3 ORDER BY 1, 2"""
    salida: dict = {"desde": desde, "hasta": hasta, "medido": {}, "estimado": {}}
    for f in cx.execute(sql, (desde, hasta, producto, producto)):
        destino = salida["medido" if f["naturaleza"] == "MEDIDA" else "estimado"]
        destino.setdefault(f["canal"], {})[f["nombre"]] = f["total"]
    publicadas = cx.execute("""SELECT COUNT(*) FROM publicacion WHERE estado = 'PUBLICADA'
                               AND substr(publicada_en, 1, 10) BETWEEN ? AND ?""", (desde, hasta)).fetchone()[0]
    salida["publicaciones"] = publicadas
    salida["sin_datos"] = not salida["medido"] and not salida["estimado"]
    return salida


def por_publicacion(cx: sqlite3.Connection, desde: str, hasta: str) -> list[dict]:
    """Rendimiento medido de cada publicación, con su tasa de interacción cuando hay alcance."""
    filas = cx.execute(
        """SELECT pb.id, pb.canal, pb.url, pz.codigo, pz.formato, pz.titulo, pz.tipo_afirmacion, pz.idea_id,
                  m.nombre, MAX(m.valor) AS valor
           FROM publicacion pb JOIN pieza pz ON pz.id = pb.pieza_id
           JOIN metrica m ON m.publicacion_id = pb.id AND m.naturaleza = 'MEDIDA'
           WHERE pb.estado = 'PUBLICADA' AND substr(pb.publicada_en, 1, 10) BETWEEN ? AND ?
           GROUP BY pb.id, m.nombre""", (desde, hasta)).fetchall()
    pubs: dict[int, dict] = {}
    for f in filas:
        p = pubs.setdefault(f["id"], {k: f[k] for k in ("id", "canal", "url", "codigo", "formato", "titulo",
                                                        "tipo_afirmacion", "idea_id")} | {"metricas": {}})
        p["metricas"][f["nombre"]] = f["valor"]
    for p in pubs.values():
        alcance = p["metricas"].get("alcance") or p["metricas"].get("impresiones")
        inter = sum(p["metricas"].get(n, 0) for n in INTERACCIONES)
        p["tasa_interaccion_bp"] = round(10000 * inter / alcance) if alcance else None
    return sorted(pubs.values(), key=lambda p: (p["tasa_interaccion_bp"] or -1), reverse=True)


def recomendaciones(cx: sqlite3.Connection, desde: str, hasta: str, minimo_alcance: int = 200) -> list[dict]:
    """Qué repetir, cambiar o detener, con el motivo. Solo sobre datos medidos y con alcance suficiente."""
    pubs = [p for p in por_publicacion(cx, desde, hasta)
            if (p["metricas"].get("alcance") or p["metricas"].get("impresiones") or 0) >= minimo_alcance]
    if len(pubs) < 3:
        return [{"decision": "INVESTIGAR", "motivo": f"Hay {len(pubs)} publicaciones con alcance medido de al menos "
                 f"{minimo_alcance}. Hacen falta 3 o más para comparar sin engañarse."}]
    tasas = sorted(p["tasa_interaccion_bp"] for p in pubs)
    mediana = tasas[len(tasas) // 2]
    salida = []
    for p in pubs:
        leads_ = p["metricas"].get("leads", 0) + p["metricas"].get("solicitudes_demo", 0)
        if leads_ > 0:
            salida.append({"decision": "CONTINUAR", "pieza": p["codigo"],
                           "motivo": f"Generó {leads_} interesados medidos. Repite el tema en otro formato."})
        elif p["tasa_interaccion_bp"] >= mediana * 1.5:
            salida.append({"decision": "CONTINUAR", "pieza": p["codigo"],
                           "motivo": f"Interacción de {p['tasa_interaccion_bp'] / 100:.1f} %, muy por encima de la mediana "
                                     f"({mediana / 100:.1f} %). Prueba la misma idea con otro llamado a la acción."})
        elif p["tasa_interaccion_bp"] <= mediana * 0.5:
            salida.append({"decision": "MODIFICAR", "pieza": p["codigo"],
                           "motivo": f"Interacción de {p['tasa_interaccion_bp'] / 100:.1f} %, la mitad de la mediana. "
                                     "Cambia el gancho antes de repetir el tema."})
    salida.append({"decision": "INVESTIGAR",
                   "motivo": "Ninguna recomendación atribuye ventas a una publicación: no hay forma de medirlo todavía."})
    return salida


def reciclables(cx: sqlite3.Connection, hoy: str | None = None, dias: int = 60) -> list[dict]:
    """Piezas que funcionaron, publicadas hace más de N días: candidatas a una nueva versión en otro formato.

    Las métricas se registran como acumulados, así que de cada publicación cuenta el último valor medido.
    """
    hoy = hoy or util.hoy_lima().isoformat()
    filas = cx.execute(
        """WITH ultimo AS (
             SELECT publicacion_id, nombre, valor,
                    ROW_NUMBER() OVER (PARTITION BY publicacion_id, nombre ORDER BY fecha DESC, id DESC) AS rn
             FROM metrica WHERE naturaleza = 'MEDIDA' AND publicacion_id IS NOT NULL)
           SELECT pz.codigo, pz.titulo, pz.formato, GROUP_CONCAT(DISTINCT pb.canal) AS canal,
                  MIN(pb.publicada_en) AS publicada_en,
                  SUM(CASE WHEN u.nombre IN ('leads','solicitudes_demo') THEN u.valor ELSE 0 END) AS interesados,
                  SUM(CASE WHEN u.nombre IN ('guardados','compartidos') THEN u.valor ELSE 0 END) AS guardados
           FROM pieza pz JOIN publicacion pb ON pb.pieza_id = pz.id AND pb.estado = 'PUBLICADA'
           LEFT JOIN ultimo u ON u.publicacion_id = pb.id AND u.rn = 1
           WHERE julianday(?) - julianday(substr(pb.publicada_en, 1, 10)) >= ?
           GROUP BY pz.id HAVING interesados > 0 OR guardados > 0
           ORDER BY interesados DESC, guardados DESC""", (hoy, dias)).fetchall()
    return [dict(f) | {"sugerencia": "Actualiza los datos, cambia el formato y vuelve a pasar por el auditor."}
            for f in filas]
