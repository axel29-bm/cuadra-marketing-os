"""Los tres roles que son código: no gastan, no inventan y siempre dan el mismo resultado con los mismos datos."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from .. import contenido, leads, metricas, util
from ..config import RAIZ


def ejecutar_leads(cx: sqlite3.Connection, entradas: dict) -> dict:
    fecha = entradas.get("fecha") or util.hoy_lima().isoformat()
    pendientes = leads.seguimientos(cx, fecha)
    for p in pendientes:
        dias = (date.fromisoformat(fecha) - date.fromisoformat(p["seguimiento_en"])).days
        p["dias_de_atraso"] = dias
        if not p["consentimiento_publicidad"]:
            p["advertencia"] = "Sin consentimiento para publicidad: solo responde lo que pidió."
    return {
        "seguimientos": pendientes,
        "vencidos": sum(1 for p in pendientes if p["dias_de_atraso"] > 0),
        "embudo": leads.embudo(cx),
    }


def ejecutar_analista(cx: sqlite3.Connection, entradas: dict) -> dict:
    hasta = entradas.get("hasta") or util.hoy_lima().isoformat()
    desde = entradas.get("desde") or (date.fromisoformat(hasta) - timedelta(days=28)).isoformat()
    return {
        "resumen": metricas.resumen(cx, desde, hasta, entradas.get("producto")),
        "recomendaciones": metricas.recomendaciones(cx, desde, hasta),
        "reciclables": metricas.reciclables(cx, hasta),
    }


def ejecutar_auditor(cx: sqlite3.Connection, entradas: dict) -> dict:
    informe = contenido.auditar_pieza(cx, RAIZ, entradas["pieza"])
    return {"resultado": informe.resultado, "hallazgos": informe.como_lista()}
