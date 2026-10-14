"""Métricas: lo medido separado de lo estimado, y recomendaciones que se pueden explicar.

Las métricas llegan a mano o desde los CSV que exporta cada red (Meta Business Suite, YouTube Studio,
TikTok Studio, LinkedIn). Ninguna se inventa: si no hay dato, el resumen dice «sin datos».
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from . import db, util

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


def importar_csv(cx: sqlite3.Connection, ruta: Path, *, columna_url: str = "url", columna_fecha: str = "fecha",
                 mapeo: dict[str, str] | None = None) -> dict[str, int]:
    """Importa un CSV con una fila por publicación. Cada fila se enlaza por la URL publicada.

    mapeo: nombre de columna del CSV → nombre de métrica (por ejemplo {"Alcance": "alcance"}).
    """
    m = mapeo or {n: n for n in NOMBRES}
    conteo = {"filas": 0, "metricas": 0, "sin_publicacion": 0}
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            conteo["filas"] += 1
            pub = cx.execute("SELECT id FROM publicacion WHERE url = ?", ((fila.get(columna_url) or "").strip(),)).fetchone()
            if pub is None:
                conteo["sin_publicacion"] += 1
                continue
            fecha = (fila.get(columna_fecha) or util.hoy_lima().isoformat()).strip()[:10]
            for columna, nombre in m.items():
                texto = (fila.get(columna) or "").replace(",", "").replace(".", "").strip()
                if texto.isdigit():
                    registrar(cx, nombre, int(texto), fecha, origen="CSV", publicacion_id=pub["id"])
                    conteo["metricas"] += 1
    return conteo


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
    """Piezas que funcionaron, publicadas hace más de N días: candidatas a una nueva versión en otro formato."""
    hoy = hoy or util.hoy_lima().isoformat()
    filas = cx.execute(
        """SELECT pz.codigo, pz.titulo, pz.formato, pb.canal, pb.publicada_en,
                  SUM(CASE WHEN m.nombre IN ('leads','solicitudes_demo') THEN m.valor ELSE 0 END) AS interesados,
                  SUM(CASE WHEN m.nombre IN ('guardados','compartidos') THEN m.valor ELSE 0 END) AS guardados
           FROM pieza pz JOIN publicacion pb ON pb.pieza_id = pz.id AND pb.estado = 'PUBLICADA'
           LEFT JOIN metrica m ON m.publicacion_id = pb.id AND m.naturaleza = 'MEDIDA'
           WHERE julianday(?) - julianday(substr(pb.publicada_en, 1, 10)) >= ?
           GROUP BY pz.id HAVING interesados > 0 OR guardados > 0
           ORDER BY interesados DESC, guardados DESC""", (hoy, dias)).fetchall()
    return [dict(f) | {"sugerencia": "Actualiza los datos, cambia el formato y vuelve a pasar por el auditor."}
            for f in filas]
