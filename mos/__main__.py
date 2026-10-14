"""Línea de comandos del Marketing OS: python -m mos <comando>.

Los mensajes se escriben para una persona, no para un programador: qué pasó y qué hacer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, config, db, semillas, util


_ABIERTAS: list = []


def _cx(cfg: config.Config):
    cx = db.conectar(cfg.base)
    db.migrar(cx)
    _ABIERTAS.append(cx)
    return cx


def cmd_iniciar(cfg, args) -> int:
    cfg.espacio.mkdir(parents=True, exist_ok=True)
    cx = db.conectar(cfg.base)
    _ABIERTAS.append(cx)
    aplicadas = db.migrar(cx)
    conteo = semillas.cargar_todo(cx, cfg.raiz)
    print(f"Espacio de trabajo: {cfg.espacio}")
    print("Migraciones aplicadas: " + (", ".join(aplicadas) if aplicadas else "ninguna, la base ya estaba al día"))
    print("Cargado: " + ", ".join(f"{v} {k}" for k, v in sorted(conteo.items())))
    return 0


def cmd_estado(cfg, args) -> int:
    from .agentes import motor
    cx = _cx(cfg)
    vencidas = motor.revisar_vencidas(cx)
    print(f"Marketing OS {__version__} · base {cfg.base} · modo de IA {cfg.modo_ia}")
    for p in cx.execute("SELECT * FROM producto ORDER BY slug"):
        caps = dict(cx.execute("SELECT uso, COUNT(*) FROM capacidad WHERE producto_id = ? GROUP BY uso", (p["id"],)).fetchall())
        print(f"\n{p['nombre_provisional']} · {p['etapa_comercial'].lower().replace('_', ' ')} · "
              f"precio {'definido' if p['precio_definido'] else 'sin definir'}")
        print("  Capacidades: " + " · ".join(f"{n} {u.lower().replace('_', ' ')}" for u, n in sorted(caps.items())))
    tareas = dict(cx.execute("SELECT estado, COUNT(*) FROM tarea GROUP BY estado").fetchall())
    if tareas:
        print("\nTareas: " + " · ".join(f"{n} {e.lower().replace('_', ' ')}" for e, n in sorted(tareas.items())))
    errores = cx.execute("SELECT COUNT(*) FROM registro_error WHERE resuelto = 0").fetchone()[0]
    if errores:
        print(f"\nErrores sin resolver: {errores}. Míralos con: python -m mos errores")
    if vencidas:
        print("Tareas vencidas ahora: " + ", ".join(vencidas))
    return 0


def cmd_capacidades(cfg, args) -> int:
    cx = _cx(cfg)
    p = cx.execute("SELECT id, nombre_provisional FROM producto WHERE slug = ?", (args.producto,)).fetchone()
    if p is None:
        print(f"No existe el producto «{args.producto}».", file=sys.stderr)
        return 1
    sql = "SELECT * FROM capacidad WHERE producto_id = ?"
    params: list = [p["id"]]
    if args.uso:
        sql += " AND uso = ?"
        params.append(args.uso.upper())
    for c in cx.execute(sql + " ORDER BY codigo", params):
        print(f"{c['codigo']:<11} {c['uso']:<12} {c['estado']:<24} {c['nombre']}")
        if args.detalle:
            if c["frase"]:
                print(f"            Frase: {c['frase']}")
            if c["matiz"]:
                print(f"            Matiz: {c['matiz']}")
    return 0


def cmd_agentes(cfg, args) -> int:
    from .agentes.contrato import describir_esquema
    from .agentes.registro import AGENTES
    for a in AGENTES.values():
        print(f"{a.id:<22} {a.modo:<13} {a.nombre}")
        if args.detalle:
            print(f"  {a.responsabilidad}")
            print("  Entradas: " + describir_esquema(a.entradas).replace("\n", "\n  "))
            print("  Salida: " + describir_esquema(a.salida).replace("\n", "\n  "))
            if a.criterios:
                print("  Criterios de éxito: " + ", ".join(n for n, _ in a.criterios))
            print(f"  Aprobación humana: {'sí' if a.requiere_aprobacion else 'no'}")
            print()
    return 0


def _producto_unico(cfg):
    from .contexto import producto_unico
    return producto_unico(cfg)


def _contexto_producto(cfg, slug: str | None):
    from .contexto import de_producto
    return de_producto(cfg, slug)


def cmd_tarea(cfg, args) -> int:
    from .agentes import motor
    cx = _cx(cfg)
    if args.accion == "crear":
        if not args.agente or not args.objetivo:
            print("Para crear una tarea indica --agente y --objetivo.", file=sys.stderr)
            return 1
        entradas = json.loads(args.entradas) if args.entradas else {}
        codigo = motor.crear(cx, args.agente, args.objetivo, entradas, restricciones=args.restriccion or [],
                             padre=args.padre, modo=cfg.modo_ia)
        print(f"Tarea {codigo} creada para {args.agente}.")
        return 0
    if args.accion == "listar":
        for t in cx.execute("SELECT codigo, agente, estado, modo, objetivo FROM tarea ORDER BY id DESC LIMIT 50"):
            print(f"{t['codigo']}  {t['estado']:<20} {t['agente']:<22} {t['objetivo'][:70]}")
        return 0
    if not args.codigo:
        print("Indica el código de la tarea, por ejemplo T-0001.", file=sys.stderr)
        return 1
    t = motor.obtener(cx, args.codigo)
    producto = util.de_json(t["entradas"], {}).get("producto") or args.producto or _producto_unico(cfg)
    ctx, ctx_texto = _contexto_producto(cfg, producto)
    if args.accion == "preparar":
        carpeta = motor.preparar(cx, cfg, args.codigo, ctx_texto)
        print(f"Listo. El prompt está en {carpeta / 'PROMPT.md'}. Guarda la respuesta en {carpeta / 'resultado.json'}.")
        return 0
    if args.accion == "ejecutar":
        estado = motor.ejecutar(cx, cfg, args.codigo, ctx, ctx_texto)
        print(f"{args.codigo}: {estado.lower().replace('_', ' ')}")
        return 0
    if args.accion == "completar":
        ruta = Path(args.archivo) if args.archivo else cfg.tareas / args.codigo / "resultado.json"
        if not ruta.exists():
            print(f"No encuentro {ruta}. Guarda ahí la respuesta JSON del asistente.", file=sys.stderr)
            return 1
        from .agentes.proveedores import extraer_json
        resultado = extraer_json(ruta.read_text(encoding="utf-8"))
        estado = motor.registrar_resultado(cx, args.codigo, resultado, ctx, evidencias=[str(ruta)])
        print(f"{args.codigo}: {estado.lower().replace('_', ' ')}")
        if estado in ("EN_CURSO", "FALLIDA"):
            ultimo = util.de_json(motor.obtener(cx, args.codigo)["errores"], [])[-1]
            for p in ultimo["problemas"]:
                print(f"  - {p}")
            return 2
        return 0
    if args.accion == "aprobar":
        motor.aprobar(cx, args.codigo, args.por, args.comentario or "")
        print(f"{args.codigo} aprobada.")
        return 0
    if args.accion == "cancelar":
        motor.cancelar(cx, args.codigo, args.comentario or "Cancelada a mano")
        print(f"{args.codigo} cancelada.")
        return 0
    if args.accion == "ver":
        for k in t.keys():
            print(f"{k}: {t[k]}")
        for e in cx.execute("SELECT en, tipo, detalle FROM tarea_evento WHERE tarea_id = ? ORDER BY id", (t["id"],)):
            print(f"  {e['en']} {e['tipo']} {e['detalle'][:200]}")
        return 0
    return 1


def cmd_auditar(cfg, args) -> int:
    from .calidad.auditor import Politica, PiezaParaAuditar, auditar
    pol = Politica.desde_carpeta(cfg.raiz / "productos" / args.producto)
    if args.archivo:
        datos = json.loads(Path(args.archivo).read_text(encoding="utf-8"))
        pieza = PiezaParaAuditar(**datos)
    else:
        pieza = PiezaParaAuditar(tipo_afirmacion=args.tipo, canal=args.canal, textos={"texto": args.texto},
                                 capacidades=args.capacidad or [], cta=args.cta or "", fuentes=args.fuente or [])
    informe = auditar(pieza, pol)
    _imprimir_informe(informe)
    return 0 if informe.resultado != "RECHAZADO" else 2


def cmd_respaldar(cfg, args) -> int:
    cx = _cx(cfg)
    destino = db.respaldar(cx, cfg.respaldos)
    print(f"Copia verificada: {destino}")
    print("Consejo: copia esa carpeta a tu nube personal. La base viva no debe estar en una carpeta sincronizada.")
    return 0


def cmd_autorizar(cfg, args) -> int:
    cx = _cx(cfg)
    with db.transaccion(cx):
        if args.revocar:
            n = cx.execute("UPDATE autorizacion SET revocada_en = ? WHERE categoria = ? AND revocada_en IS NULL",
                           (util.ahora_utc(), args.categoria)).rowcount
            db.auditar(cx, args.por, "autorizacion", None, "REVOCAR", {"categoria": args.categoria})
            print(f"Revocadas {n} autorizaciones de {args.categoria}.")
        else:
            cx.execute("INSERT INTO autorizacion (categoria, alcance, otorgada_por, otorgada_en, nota) VALUES (?,?,?,?,?)",
                       (args.categoria, args.alcance, args.por, util.ahora_utc(), args.nota or ""))
            db.auditar(cx, args.por, "autorizacion", None, "OTORGAR", {"categoria": args.categoria, "alcance": args.alcance})
            print(f"Autorizado {args.categoria}: {args.alcance}. Se revoca con --revocar.")
    return 0


def cmd_errores(cfg, args) -> int:
    cx = _cx(cfg)
    for e in cx.execute("SELECT * FROM registro_error WHERE resuelto = 0 ORDER BY id DESC LIMIT 50"):
        print(f"#{e['id']} {e['en']} {e['modulo']}/{e['codigo']}: {e['mensaje']}")
    return 0


def _imprimir_informe(informe) -> None:
    print(f"Resultado: {informe.resultado.lower().replace('_', ' ')}")
    for h in informe.hallazgos:
        print(f"  [{h.severidad.lower()}] {h.mensaje}" + (f" Sugerencia: {h.sugerencia}" if h.sugerencia else ""))


def cmd_idea(cfg, args) -> int:
    from . import contenido
    cx = _cx(cfg)
    if args.accion == "crear":
        datos = json.loads(Path(args.archivo).read_text(encoding="utf-8")) if args.archivo else {}
        producto = datos.pop("producto", args.producto or _producto_unico(cfg))
        codigo = contenido.crear_idea(cx, producto, **datos)
        fila = cx.execute("SELECT puntuacion_detalle FROM idea WHERE codigo = ?", (codigo,)).fetchone()
        print(f"Idea {codigo}. {util.de_json(fila[0])['explicacion']}")
        return 0
    if args.accion == "listar":
        for i in contenido.ideas_priorizadas(cx, args.producto, args.limite):
            print(f"{i['codigo']}  {i['puntuacion']:>3}  {i['etapa_embudo']:<13} {i['canal']:<10} {i['idea_central'][:70]}")
        return 0
    if args.accion == "ver":
        i = cx.execute("SELECT * FROM idea WHERE codigo = ?", (args.codigo,)).fetchone()
        if i is None:
            print(f"No existe la idea {args.codigo}.", file=sys.stderr)
            return 1
        for k in i.keys():
            print(f"{k}: {i[k]}")
        return 0
    contenido.cambiar_estado_idea(cx, args.codigo, args.accion.upper(), args.por)
    print(f"{args.codigo}: {args.accion}")
    return 0


def cmd_pieza(cfg, args) -> int:
    from . import contenido
    cx = _cx(cfg)
    if args.accion == "crear":
        codigo = contenido.crear_pieza(cx, args.producto or _producto_unico(cfg), formato=args.formato, canal=args.canal,
                                       titulo=args.titulo, tipo_afirmacion=args.tipo, campana=args.campana,
                                       idea=args.idea, fecha_prevista=args.fecha, plantilla=args.plantilla, por=args.por)
        print(f"Pieza {codigo} creada. Agrega su contenido con: python -m mos pieza version {codigo} --archivo contenido.json")
        return 0
    if args.accion == "listar":
        for p in cx.execute("SELECT codigo, estado, fecha_prevista, canal, formato, titulo FROM pieza ORDER BY id DESC LIMIT 100"):
            print(f"{p['codigo']}  {p['estado']:<18} {p['fecha_prevista'] or '—':<10} {p['canal']:<10} {p['formato']:<10} {p['titulo'][:60]}")
        return 0
    if not args.codigo:
        print("Indica el código de la pieza, por ejemplo P-0001.", file=sys.stderr)
        return 1
    if args.accion == "version":
        datos = json.loads(Path(args.archivo).read_text(encoding="utf-8"))
        n = contenido.nueva_version(cx, args.codigo, datos.get("contenido", datos), capacidades=datos.get("capacidades"),
                                    fuentes=datos.get("fuentes"), autor=args.por, nota=args.comentario or "")
        print(f"{args.codigo}: versión {n} guardada. Siguiente paso: python -m mos pieza auditar {args.codigo}")
        return 0
    if args.accion == "auditar":
        informe = contenido.auditar_pieza(cx, cfg.raiz, args.codigo)
        _imprimir_informe(informe)
        return 0 if informe.resultado != "RECHAZADO" else 2
    if args.accion in ("aprobar", "rechazar", "corregir"):
        decision = {"aprobar": "APROBADA", "rechazar": "RECHAZADA", "corregir": "CORRECCIONES"}[args.accion]
        contenido.decidir(cx, args.codigo, decision, args.por, args.comentario or "")
        print(f"{args.codigo}: {decision.lower()}")
        return 0
    if args.accion == "ver":
        p = contenido.obtener_pieza(cx, args.codigo)
        for k in p.keys():
            print(f"{k}: {p[k]}")
        v = contenido.version_actual(cx, p)
        if v:
            print("contenido:", json.dumps(util.de_json(v["contenido"]), ensure_ascii=False, indent=2))
        for r in cx.execute("SELECT version, revisor, resultado, creado_en FROM revision WHERE pieza_id = ? ORDER BY id", (p["id"],)):
            print(f"  revisión v{r['version']} {r['revisor']}: {r['resultado']} ({r['creado_en']})")
        return 0
    return 1


def cmd_publicacion(cfg, args) -> int:
    from . import contenido
    cx = _cx(cfg)
    if args.accion == "preparar":
        pid = contenido.preparar_publicacion(cx, args.pieza, canal=args.canal, copy=args.copy,
                                             archivos=args.archivo or [], fecha_prevista=args.fecha, por=args.por)
        print(f"Paquete {pid} listo. Publícalo tú (o prográmalo en la herramienta nativa) y luego confirma con:")
        print(f"  python -m mos publicacion confirmar {pid} --url https://…")
        return 0
    if args.accion == "listar":
        for p in cx.execute("""SELECT pb.id, pb.estado, pb.canal, pb.fecha_prevista, pb.url, pz.codigo FROM publicacion pb
                               JOIN pieza pz ON pz.id = pb.pieza_id ORDER BY pb.id DESC LIMIT 100"""):
            print(f"#{p['id']:<4} {p['estado']:<14} {p['canal']:<10} {p['fecha_prevista'] or '—':<10} {p['codigo']} {p['url'] or ''}")
        return 0
    if args.id is None:
        print("Indica el número del paquete de publicación.", file=sys.stderr)
        return 1
    if args.accion == "programar":
        contenido.marcar_programada(cx, args.id, args.fecha, args.por)
    elif args.accion == "confirmar":
        contenido.confirmar_publicacion(cx, args.id, url=args.url, id_externo=args.id_externo, por=args.por)
    elif args.accion == "fallo":
        contenido.registrar_fallo(cx, args.id, args.error or "Sin detalle", args.por)
    print(f"Publicación {args.id}: {args.accion} registrado.")
    return 0


def cmd_lead(cfg, args) -> int:
    from . import leads
    cx = _cx(cfg)
    if args.accion == "registrar":
        if args.campana and not cx.execute("SELECT 1 FROM campana WHERE slug = ?", (args.campana,)).fetchone():
            print(f"No existe la campaña «{args.campana}» en la base. Cárgala con: python -m mos campana cargar campanas/{args.campana}",
                  file=sys.stderr)
            return 2
        uid, nuevo = leads.registrar(
            cx, args.producto or _producto_unico(cfg), fuente=args.fuente, email=args.email, telefono=args.telefono,
            nombre=args.nombre or "", problema_principal=args.problema or "", empresas_que_lleva=args.empresas,
            campana=args.campana, consentimiento=args.consentimiento, consentimiento_publicidad=args.publicidad,
            finalidad=args.finalidad or "", consentimiento_version=args.version_aviso, consentimiento_medio=args.medio,
            notas=args.nota or "")
        print(f"Lead {uid[:8]} {'registrado' if nuevo else 'ya existía: actualizado sin duplicar'}.")
        return 0
    if args.accion == "seguimientos":
        for s in leads.seguimientos(cx, args.fecha):
            print(f"{s['uid'][:8]}  {s['seguimiento_en']}  {s['estado']:<14} {s['nombre'] or '(sin nombre)'} · {s['proxima_accion']}")
        return 0
    if args.accion == "embudo":
        for estado, n in leads.embudo(cx, args.producto).items():
            print(f"{estado:<14} {n}")
        norte = leads.metrica_norte(cx, producto=args.producto, campana=args.campana)
        print(f"\nEn la lista con consentimiento{' (' + args.campana + ')' if args.campana else ''}: {norte}"
              " · métrica norte: sin baja ni supresión")
        return 0
    if args.accion == "importar":
        conteo = leads.importar_csv(cx, Path(args.archivo), args.producto or _producto_unico(cfg), args.fuente,
                                    finalidad=args.finalidad, consentimiento_version=args.version_aviso)
        print(", ".join(f"{k}: {v}" for k, v in conteo.items()))
        return 0
    if args.accion == "exportar":
        ruta = Path(args.archivo or cfg.salidas / "leads.csv")
        n = leads.exportar_csv(cx, ruta, args.producto)
        print(f"{n} leads en {ruta}. Ese archivo tiene datos personales: guárdalo solo en tu PC.")
        return 0
    if args.accion in ("baja", "acceso", "suprimir"):
        if not args.contacto:
            print("Indica --contacto con el correo o el teléfono de la persona.", file=sys.stderr)
            return 1
        if args.accion == "baja":
            print(f"Baja registrada ({leads.dar_de_baja(cx, args.contacto, args.por)} registros).")
        elif args.accion == "acceso":
            datos = leads.exportar_titular(cx, args.contacto)
            ruta = cfg.salidas / f"acceso-{util.ahora_utc()[:10]}-{util.uid()[:6]}.json"
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Datos de la persona en {ruta} ({len(datos['registros'])} registros). Entrégaselos y borra el archivo.")
        else:
            print(f"Datos suprimidos ({leads.suprimir(cx, args.contacto, args.por)} registros). Queda solo el hash para no volver a escribirle.")
        return 0
    if args.accion == "actualizar":
        leads.actualizar(cx, args.uid, estado=args.estado, proxima_accion=args.proxima, seguimiento_en=args.fecha,
                         nota=args.nota, por=args.por)
        print("Lead actualizado.")
        return 0
    return 1


def cmd_metrica(cfg, args) -> int:
    from . import metricas
    cx = _cx(cfg)
    if args.accion == "registrar":
        metricas.registrar(cx, args.nombre, args.valor, args.fecha or util.hoy_lima().isoformat(),
                           naturaleza=args.naturaleza, publicacion_id=args.publicacion, campana=args.campana,
                           nota=args.nota or "")
        print("Métrica registrada.")
        return 0
    if args.accion == "importar":
        if not args.archivo:
            print("Indica --archivo con el CSV que exportaste de la red.", file=sys.stderr)
            return 2
        r = metricas.importar_csv(cx, Path(args.archivo), fecha=args.fecha, revisar=args.revisar)
        print(("Revisión (no se guardó nada): " if args.revisar else "") +
              f"{r.filas} filas · {r.emparejadas} publicaciones reconocidas · {r.metricas} métricas "
              f"{'se guardarían' if args.revisar else 'guardadas'} con fecha {args.fecha or util.hoy_lima().isoformat()}.")
        print("Columnas que entiendo: " + (", ".join(f"{k} → {v}" for k, v in r.reconocidas.items()) or "ninguna"))
        if r.ignoradas:
            print("Columnas que no importo (si alguna es una métrica, agrégala en semillas/metricas-csv.toml): "
                  + ", ".join(r.ignoradas))
        if r.sin_enlace:
            print(f"{r.sin_enlace} filas sin enlace o sin números (descripciones o totales de la red): no se importan.")
        if r.fecha_invalida:
            print(f"{r.fecha_invalida} filas con una fecha que no es AAAA-MM-DD: no se importan.")
        if r.sin_publicacion:
            print(f"{r.sin_publicacion} filas no coinciden con ninguna publicación confirmada; por ejemplo: "
                  + ", ".join(r.ejemplos_sin_publicacion) + ". Confírmalas con publicacion confirmar --url.")
        if r.no_leidas:
            print(f"{r.no_leidas} valores no eran números enteros y no se importaron (mejor sin dato que con uno falso).")
        return 0
    hasta = args.hasta or util.hoy_lima().isoformat()
    desde = args.desde or hasta[:8] + "01"
    r = metricas.resumen(cx, desde, hasta, args.producto)
    if r["sin_datos"]:
        print(f"Sin datos entre {desde} y {hasta}. Registra métricas a mano o importa el CSV de cada red.")
        return 0
    for naturaleza in ("medido", "estimado"):
        for canal_, valores in r[naturaleza].items():
            print(f"[{naturaleza}] {canal_}: " + ", ".join(f"{k} {v}" for k, v in valores.items()))
    for rec in metricas.recomendaciones(cx, desde, hasta):
        print(f"→ {rec['decision']}: {rec.get('pieza', '')} {rec['motivo']}")
    return 0


def cmd_calendario(cfg, args) -> int:
    from . import contenido
    cx = _cx(cfg)
    desde = args.desde or util.hoy_lima().isoformat()
    hasta = args.hasta or "9999-12-31"
    filas = contenido.calendario(cx, desde, hasta, args.producto)
    if not filas:
        print("No hay piezas con fecha en ese rango.")
    for f in filas:
        print(f"{f['fecha_prevista']}  {f['codigo']}  {f['canal']:<10} {f['formato']:<10} {f['estado']:<18} {f['titulo'][:60]}")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m mos", description="Marketing OS: el departamento de marketing en tu PC.")
    ap.add_argument("--espacio", help="Carpeta de datos (por defecto ./espacio o MOS_ESPACIO)")
    sub = ap.add_subparsers(dest="comando", required=True)

    sub.add_parser("iniciar", help="Crea o actualiza la base y carga productos, marcas, fuentes y herramientas")
    sub.add_parser("estado", help="Resumen del sistema")
    sp = sub.add_parser("capacidades", help="Matriz de lo que se puede afirmar de un producto")
    sp.add_argument("producto")
    sp.add_argument("--uso", choices=["permitido", "con_matices", "solo_demo", "no_anunciar"])
    sp.add_argument("--detalle", action="store_true")
    sp = sub.add_parser("agentes", help="Los roles del departamento y sus contratos")
    sp.add_argument("--detalle", action="store_true")

    sp = sub.add_parser("tarea", help="Trabajo de los agentes")
    sp.add_argument("accion", choices=["crear", "listar", "preparar", "ejecutar", "completar", "aprobar", "cancelar", "ver"])
    sp.add_argument("codigo", nargs="?")
    sp.add_argument("--agente")
    sp.add_argument("--objetivo")
    sp.add_argument("--entradas", help="JSON con las entradas")
    sp.add_argument("--restriccion", action="append")
    sp.add_argument("--padre")
    sp.add_argument("--archivo")
    sp.add_argument("--producto")
    sp.add_argument("--por", default="Didi")
    sp.add_argument("--comentario")

    sp = sub.add_parser("auditar", help="Revisa un texto o una pieza contra la matriz del producto")
    sp.add_argument("--producto", default="cuadra")
    sp.add_argument("--archivo", help="JSON con los campos de PiezaParaAuditar")
    sp.add_argument("--tipo", default="CAPTACION")
    sp.add_argument("--canal", default="facebook")
    sp.add_argument("--texto", default="")
    sp.add_argument("--cta")
    sp.add_argument("--capacidad", action="append")
    sp.add_argument("--fuente", action="append")

    sub.add_parser("respaldar", help="Copia verificada de la base")
    sp = sub.add_parser("autorizar", help="Otorga o revoca una autorización (IA_EXTERNA, PUBLICACION_API…)")
    sp.add_argument("categoria")
    sp.add_argument("--alcance", default="")
    sp.add_argument("--por", default="Didi")
    sp.add_argument("--nota")
    sp.add_argument("--revocar", action="store_true")
    sub.add_parser("errores", help="Errores sin resolver")

    sp = sub.add_parser("idea", help="Banco de ideas con puntuación explicable")
    sp.add_argument("accion", choices=["crear", "listar", "ver", "seleccionada", "descartada", "archivada"])
    sp.add_argument("codigo", nargs="?")
    sp.add_argument("--archivo", help="JSON con los campos de la idea")
    sp.add_argument("--producto")
    sp.add_argument("--limite", type=int, default=20)
    sp.add_argument("--por", default="Didi")

    sp = sub.add_parser("pieza", help="Piezas de contenido: versiones, auditoría y aprobación")
    sp.add_argument("accion", choices=["crear", "listar", "ver", "version", "auditar", "aprobar", "rechazar", "corregir"])
    sp.add_argument("codigo", nargs="?")
    sp.add_argument("--producto")
    sp.add_argument("--formato")
    sp.add_argument("--canal")
    sp.add_argument("--titulo")
    sp.add_argument("--tipo", default="EDUCATIVA")
    sp.add_argument("--campana")
    sp.add_argument("--idea")
    sp.add_argument("--fecha")
    sp.add_argument("--plantilla")
    sp.add_argument("--archivo")
    sp.add_argument("--por", default="Didi")
    sp.add_argument("--comentario")

    sp = sub.add_parser("publicacion", help="Paquetes de publicación y su registro con prueba")
    sp.add_argument("accion", choices=["preparar", "listar", "programar", "confirmar", "fallo"])
    sp.add_argument("id", nargs="?", type=int)
    sp.add_argument("--pieza")
    sp.add_argument("--canal")
    sp.add_argument("--copy")
    sp.add_argument("--archivo", action="append")
    sp.add_argument("--fecha")
    sp.add_argument("--url")
    sp.add_argument("--id-externo", dest="id_externo")
    sp.add_argument("--error")
    sp.add_argument("--por", default="Didi")

    sp = sub.add_parser("lead", help="Interesados: registro, seguimiento, baja, acceso y supresión")
    sp.add_argument("accion", choices=["registrar", "seguimientos", "embudo", "importar", "exportar", "actualizar",
                                       "baja", "acceso", "suprimir"])
    sp.add_argument("uid", nargs="?")
    sp.add_argument("--producto")
    sp.add_argument("--fuente", default="manual")
    sp.add_argument("--email")
    sp.add_argument("--telefono")
    sp.add_argument("--nombre")
    sp.add_argument("--problema")
    sp.add_argument("--empresas", type=int)
    sp.add_argument("--campana")
    sp.add_argument("--consentimiento", action="store_true")
    sp.add_argument("--publicidad", action="store_true", help="Aceptó recibir publicidad (consentimiento aparte)")
    sp.add_argument("--finalidad")
    sp.add_argument("--version-aviso", dest="version_aviso", default="aviso-privacidad-v1")
    sp.add_argument("--medio")
    sp.add_argument("--archivo")
    sp.add_argument("--contacto")
    sp.add_argument("--estado")
    sp.add_argument("--proxima")
    sp.add_argument("--fecha")
    sp.add_argument("--nota")
    sp.add_argument("--por", default="Didi")

    sp = sub.add_parser("metrica", help="Métricas medidas o estimadas y recomendaciones")
    sp.add_argument("accion", choices=["registrar", "importar", "resumen"])
    sp.add_argument("--nombre")
    sp.add_argument("--valor", type=int)
    sp.add_argument("--fecha")
    sp.add_argument("--naturaleza", default="MEDIDA", choices=["MEDIDA", "ESTIMADA"])
    sp.add_argument("--publicacion", type=int)
    sp.add_argument("--campana")
    sp.add_argument("--nota")
    sp.add_argument("--archivo")
    sp.add_argument("--desde")
    sp.add_argument("--hasta")
    sp.add_argument("--producto")
    sp.add_argument("--revisar", action="store_true", help="Al importar, mostrar qué entraría sin guardar nada")

    sp = sub.add_parser("calendario", help="Piezas con fecha")
    sp.add_argument("--desde")
    sp.add_argument("--hasta")
    sp.add_argument("--producto")

    sp = sub.add_parser("fabrica", help="Plantillas visuales: imágenes, PDF, vídeo y guion a partir de los textos")
    sp.add_argument("accion", choices=["plantillas", "previas", "probar", "render"])
    sp.add_argument("codigo", nargs="?", help="Pieza a renderizar (P-0001)")
    sp.add_argument("--plantilla")
    sp.add_argument("--archivo", help="JSON con los textos (para probar)")
    sp.add_argument("--formato", action="append", help="Formato (se puede repetir): cuadrado, vertical, historia…")
    sp.add_argument("--audio", help="Voz grabada para unir al vídeo")
    sp.add_argument("--marca", default="cuadra")

    sp = sub.add_parser("campana", help="Campañas escritas en campanas/<slug>/campana.toml: cargar, renderizar, calendario y paquete")
    sp.add_argument("accion", choices=["cargar", "render", "calendario", "paquete", "mover"])
    sp.add_argument("carpeta", help="Carpeta de la campaña, por ejemplo campanas/lista-espera-beta")
    sp.add_argument("--solo", action="append", help="Solo esta pieza del archivo (clave, se puede repetir)")
    sp.add_argument("--forzar", action="store_true", help="Rehacer los archivos aunque ya existan")
    sp.add_argument("--destino", help="Carpeta de salida (calendario o paquete)")
    sp.add_argument("--semanas", type=int, help="Para mover: cuántas semanas correr todas las fechas")

    sp = sub.add_parser("sitio", help="La landing de la lista de espera: construir, ver en local, pendientes e importar")
    sp.add_argument("accion", choices=["construir", "ver", "pendientes", "importar"])
    sp.add_argument("--publicable", action="store_true", help="Negarse a construir si falta algo para publicar")
    sp.add_argument("--sin-abrir", action="store_true", help="No abrir el navegador")
    sp.add_argument("--sin-borrar", action="store_true", help="Al importar, no borrar las inscripciones del servidor")

    sp = sub.add_parser("experimento", help="Experimentos de campaña: cargar del archivo, ver el resultado medido y cerrar")
    sp.add_argument("accion", choices=["cargar", "listar", "resultado", "empezar", "cerrar", "cancelar"])
    sp.add_argument("objetivo", nargs="?", help="Código (EXP-01) o, para cargar, la carpeta de la campaña")
    sp.add_argument("--decision", choices=["CONTINUAR", "MODIFICAR", "DETENER", "INVESTIGAR"])
    sp.add_argument("--resultado", help="Al cerrar: qué se midió, en una o dos frases")
    sp.add_argument("--limitaciones")
    sp.add_argument("--motivo", help="Al cancelar: por qué")
    sp.add_argument("--por", default="Didi")

    sp = sub.add_parser("rutina", help="Rutina diaria (respaldo, radar, pendientes), resumen semanal y revisión mensual; se pueden programar")
    sp.add_argument("accion", choices=["diaria", "semanal", "mensual", "estado", "programar"])
    sp.add_argument("--sin-radar", action="store_true", help="En la diaria, no leer las fuentes del radar")
    sp.add_argument("--hasta", help="En la semanal, último día del resumen (AAAA-MM-DD; por defecto hoy)")
    sp.add_argument("--mes", help="En la mensual, el mes a revisar (AAAA-MM; por defecto el anterior)")

    sp = sub.add_parser("radar", help="Fuentes oficiales: leer las automáticas y ver lo que espera verificación")
    sp.add_argument("accion", choices=["leer", "pendientes", "fuentes"])
    sp.add_argument("--fuente", action="append", help="Solo esta fuente (slug, se puede repetir)")
    sp.add_argument("--forzar", action="store_true", help="Leer aunque todavía no toque según su frecuencia")

    sp = sub.add_parser("web", help="Abre el panel local en el navegador (solo en esta PC)")
    sp.add_argument("--sin-abrir", action="store_true", help="No abrir el navegador automáticamente")
    return ap


def cmd_fabrica(cfg, args) -> int:
    from .fabrica import plantillas, render
    raiz = cfg.raiz
    if args.accion == "plantillas":
        for nombre in sorted(plantillas.disponibles(raiz)):
            f = plantillas.ficha(raiz, nombre)
            print(f"{nombre:<16} {f['titulo']:<26} {', '.join(f['formatos'])}")
            print(f"{'':<16} {f['descripcion']}")
        print("\nFormatos: " + ", ".join(f"{k} {a}x{b}" for k, (a, b) in render.FORMATOS.items()))
        return 0
    if args.accion == "previas":
        nombres = [args.plantilla] if args.plantilla else sorted(plantillas.disponibles(raiz))
        with render.Navegador() as nav:
            for nombre in nombres:
                f = plantillas.ficha(raiz, nombre)
                formatos = args.formato or f["formatos"][:1]
                res = render.exportar(raiz, nombre, f["ejemplo"], raiz / "plantillas" / nombre / "previa", "previa",
                                      formatos=formatos, marca=args.marca, vista_previa=True, navegador=nav,
                                      titulo=f["titulo"])
                print(f"{nombre}: " + ", ".join(p.relative_to(raiz).as_posix() for p in res.archivos))
        return 0
    if args.accion == "probar":
        if not (args.plantilla and args.archivo):
            print("Indica --plantilla y --archivo con los textos en JSON.", file=sys.stderr)
            return 2
        datos = json.loads(Path(args.archivo).read_text(encoding="utf-8"))
        res = render.exportar(raiz, args.plantilla, datos, cfg.salidas / "pruebas", args.plantilla,
                              formatos=args.formato, marca=args.marca, vista_previa=True,
                              audio=Path(args.audio) if args.audio else None)
        for ruta in res.archivos:
            print(ruta)
        for aviso in res.avisos:
            print("Aviso: " + aviso)
        return 0
    if not args.codigo:
        print("Indica la pieza: python -m mos fabrica render P-0001", file=sys.stderr)
        return 2
    cx = _cx(cfg)
    res = render.exportar_pieza(cx, cfg, args.codigo, formatos=args.formato,
                                audio=Path(args.audio) if args.audio else None)
    for ruta in res.archivos:
        print(ruta)
    for nombre, ms in res.duraciones_ms.items():
        print(f"{nombre}: {ms / 1000:g} s")
    for aviso in res.avisos:
        print("Aviso: " + aviso)
    return 0


def cmd_web(cfg: config.Config, args) -> int:
    from .web.app import servir
    servir(cfg, abrir=not args.sin_abrir)
    return 0


def cmd_campana(cfg: config.Config, args) -> int:
    from . import campanas
    carpeta = Path(args.carpeta)
    datos = campanas.leer(carpeta)
    slug = datos["campana"]["slug"]
    if args.accion == "cargar":
        cx = _cx(cfg)
        res = campanas.cargar(cx, cfg, carpeta)
        print(f"Campaña «{datos['campana']['nombre']}»: {len(res.creadas)} piezas nuevas, {len(res.actualizadas)} con versión nueva, "
              f"{len(res.sin_cambios)} sin cambios.")
        bd = campanas.piezas_de(cx, slug)
        for p in datos["pieza"]:
            fila = bd[p["clave"]]
            print(f"  {p['fecha']} {p['clave']:<8} {fila['codigo']}  auditor: {res.auditoria.get(fila['codigo'], '').lower().replace('_', ' ')}")
        return 0
    if args.accion == "render":
        from .fabrica import render
        cx = _cx(cfg)
        bd = campanas.piezas_de(cx, slug)
        elegidas = [p for p in datos["pieza"] if p.get("plantilla") and (not args.solo or p["clave"] in args.solo)]
        faltan = [p["clave"] for p in elegidas if p["clave"] not in bd]
        if faltan:
            print("Primero carga la campaña (python -m mos campana cargar …). Faltan: " + ", ".join(faltan), file=sys.stderr)
            return 2
        cache: dict = {}  # la misma imagen o el mismo vídeo en varios canales se renderiza una sola vez
        with render.Navegador() as nav:
            for p in elegidas:
                fila = bd[p["clave"]]
                ya = cx.execute("SELECT COUNT(*) FROM activo WHERE pieza_id = ? AND version = ?",
                                (fila["id"], fila["version_actual"])).fetchone()[0]
                if ya and not args.forzar:
                    print(f"  {p['clave']:<8} {fila['codigo']} ya tiene {ya} archivos de su versión actual (usa --forzar para rehacerlos)")
                    continue
                res = render.exportar_pieza(cx, cfg, fila["codigo"], formatos=p.get("formatos"), navegador=nav, cache=cache)
                videos = ", ".join(f"vídeo de {ms / 1000:g} s" for ms in res.duraciones_ms.values())
                print(f"  {p['clave']:<8} {fila['codigo']} {len(res.archivos)} archivos" + (f" ({videos})" if videos else ""))
                for aviso in res.avisos:
                    print("    Aviso: " + aviso)
        return 0
    if args.accion == "mover":
        if not args.semanas:
            print("Indica cuántas semanas: --semanas 1 (o -1 para adelantar). Mover por semanas conserva los días de la semana.",
                  file=sys.stderr)
            return 2
        n = campanas.mover(carpeta, 7 * args.semanas)
        print(f"Movidas {n} fechas {abs(args.semanas)} semana(s) {'después' if args.semanas > 0 else 'antes'}. "
              "Vuelve a cargar la campaña para actualizar las piezas.")
        return 0
    if args.accion == "calendario":
        bd = campanas.piezas_de(_cx(cfg), slug) if cfg.base.exists() else {}
        filas = campanas.filas_calendario(datos, bd)
        destino = Path(args.destino) if args.destino else carpeta
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "CALENDARIO.md").write_text(campanas.calendario_md(datos, filas), encoding="utf-8")
        (destino / "calendario.csv").write_text(campanas.calendario_csv(filas), encoding="utf-8-sig", newline="")
        print(f"Calendario de {len(filas)} días en {destino / 'CALENDARIO.md'} y {destino / 'calendario.csv'}")
        return 0
    cx = _cx(cfg)
    destino = Path(args.destino) if args.destino else carpeta / "exportados"
    archivos = campanas.exportar_paquete(cx, cfg, carpeta, destino)
    print(f"Paquete en {destino}: {len(archivos)} archivos")
    return 0


def cmd_sitio(cfg: config.Config, args) -> int:
    import os
    from . import sitio
    if args.accion == "pendientes":
        faltan = sitio.pendientes_para_publicar(sitio.leer(cfg.raiz))
        print("Lista para publicar (con tu autorización)." if not faltan else "Falta para publicar la landing:")
        for f in faltan:
            print("  - " + f)
        return 0
    if args.accion == "construir":
        res = sitio.construir(cfg.raiz, publicable=args.publicable)
        print(f"Landing en {cfg.raiz / 'sitio' / 'dist'}: {len(res.archivos)} archivos." +
              (f" Es un borrador: faltan {len(res.pendientes)} cosas para publicarla (python -m mos sitio pendientes)."
               if res.pendientes else ""))
        for aviso in res.avisos:
            print("Aviso: " + aviso)
        return 0
    if args.accion == "ver":
        sitio.servir(cfg, abrir=not args.sin_abrir)
        return 0
    datos = sitio.leer(cfg.raiz)
    receptor = datos["publicacion"].get("receptor", "")
    if not receptor:
        print("La landing todavía no tiene receptor publicado (publicacion.receptor en sitio/sitio.toml).", file=sys.stderr)
        return 2
    conteo = sitio.importar_remoto(_cx(cfg), cfg, receptor, os.environ.get("MOS_CLAVE_LISTA", ""), borrar=not args.sin_borrar)
    print(f"Inscripciones: {conteo['nuevos']} nuevas, {conteo['actualizados']} ya estaban, {conteo['invalidos']} no válidas; "
          f"{conteo['borrados']} borradas del servidor.")
    return 0


def cmd_experimento(cfg: config.Config, args) -> int:
    from . import experimentos
    cx = _cx(cfg)
    if args.accion == "listar":
        filas = experimentos.listar(cx)
        if not filas:
            print("No hay experimentos. Cárgalos con: python -m mos experimento cargar campanas/<campaña>")
        for x in filas:
            d = util.de_json(x["definicion"], {})
            print(f"{x['codigo']}  {x['estado'].lower():<11} {d.get('titulo', x['hipotesis'][:60])}"
                  + (f" · decisión: {x['decision'].lower()}" if x["decision"] else ""))
        return 0
    if not args.objetivo:
        print("Indica el código del experimento (o la carpeta de la campaña para cargar).", file=sys.stderr)
        return 2
    if args.accion == "cargar":
        nuevos, actualizados = experimentos.cargar(cx, Path(args.objetivo), args.por)
        print(f"Experimentos: {nuevos} nuevos, {actualizados} actualizados (estado y decisión no se tocan).")
        return 0
    if args.accion == "resultado":
        r = experimentos.calcular(cx, args.objetivo)
        for clave, g in r.grupos.items():
            tasa = f"{g.tasa_bp / 100:.2f} %" if g.tasa_bp is not None else "sin datos"
            print(f"  {clave} · {g.nombre}: {g.publicaciones} publicaciones con dato · {g.numerador} / {g.denominador} = {tasa}"
                  + (f" · sin dato: {', '.join(g.faltan)}" if g.faltan else ""))
        print(r.lectura)
        return 0
    if args.accion == "empezar":
        experimentos.empezar(cx, args.objetivo, args.por)
    elif args.accion == "cerrar":
        if not args.decision:
            print("Indica --decision (CONTINUAR, MODIFICAR, DETENER o INVESTIGAR) y --resultado.", file=sys.stderr)
            return 2
        experimentos.cerrar(cx, args.objetivo, args.decision, args.resultado or "", args.por, args.limitaciones)
    else:
        experimentos.cancelar(cx, args.objetivo, args.motivo or "", args.por)
    print(f"{args.objetivo}: " + {"empezar": "en curso.", "cerrar": "terminado, con la decisión anotada.",
                                  "cancelar": "cancelado, con el motivo anotado."}[args.accion])
    return 0


def cmd_rutina(cfg: config.Config, args) -> int:
    from datetime import date
    from . import rutina
    cx = _cx(cfg)
    if args.accion == "programar":
        print("Para que la rutina corra sola, copia estos comandos en una consola de Windows (no se ejecutan desde aquí):\n")
        comandos = rutina.preparar_programacion(cfg)
        crear, quitar = comandos[:3], comandos[3:]
        print("\n".join(f"  {c}" for c in crear) + "\n\nPara quitarlas:\n\n" + "\n".join(f"  {c}" for c in quitar))
        print("\nLa PC tiene que estar encendida a esa hora. Si no lo está, la rutina corre la próxima vez.")
        return 0
    if args.accion == "estado":
        for tipo, fila in rutina.ultimas(cx).items():
            print(f"{tipo.lower():<8} " + (f"{fila['fecha']} · {fila['estado'].lower()} · {fila['informe']}" if fila else "nunca corrió"))
        for aviso in rutina.alertas(cx):
            print("Aviso: " + aviso)
        return 0
    if args.accion == "diaria":
        inf = rutina.diaria(cx, cfg, leer_radar=not args.sin_radar)
    elif args.accion == "mensual":
        inf = rutina.mensual(cx, cfg, mes=args.mes)
    else:
        inf = rutina.semanal(cx, cfg, hasta=date.fromisoformat(args.hasta) if args.hasta else None)
    print(f"Rutina {inf.tipo.lower()} del {inf.fecha}: {'todo bien' if inf.estado == 'OK' else 'con fallos'}. Informe en {inf.ruta}")
    for paso, resultado in inf.pasos.items():
        if resultado not in ("OK", "OMITIDO"):
            print(f"  {paso}: {resultado}")
    return 0 if inf.estado == "OK" else 3


def cmd_radar(cfg: config.Config, args) -> int:
    from . import radar, radar_lector
    cx = _cx(cfg)
    if args.accion == "leer":
        for r in radar_lector.leer_fuentes(cx, forzar=args.forzar, solo=args.fuente):
            extra = f" · {r.nuevas} nuevas" if r.nuevas else ""
            print(f"{r.fuente:<28} {radar_lector.ESTADOS_TEXTO.get(r.estado, r.estado)}{extra}" + (f" · {r.detalle}" if r.detalle else ""))
        return 0
    if args.accion == "fuentes":
        for f in cx.execute("SELECT * FROM fuente ORDER BY activa DESC, metodo, slug"):
            estado = "inactiva" if not f["activa"] else ("manual" if f["metodo"] == "MANUAL" else f["metodo"].lower())
            ultima = (f["ultima_consulta"] or "nunca")[:16]
            print(f"{f['slug']:<28} {estado:<9} cada {f['frecuencia_horas']:>3} h · última {ultima}"
                  + (f" · error: {f['ultimo_error']}" if f["ultimo_error"] else ""))
        return 0
    filas = radar.pendientes(cx)
    if not filas:
        print("No hay novedades esperando verificación.")
    for r in filas:
        print(f"{r['id']:>4}  {(r['fecha_publicacion'] or r['detectado_en'])[:10]}  {r['fuente'] or '—':<26} {r['titulo'][:70]}\n      {r['url']}")
    return 0


COMANDOS = {
    "iniciar": cmd_iniciar, "estado": cmd_estado, "capacidades": cmd_capacidades, "agentes": cmd_agentes,
    "tarea": cmd_tarea, "auditar": cmd_auditar, "respaldar": cmd_respaldar, "autorizar": cmd_autorizar,
    "errores": cmd_errores, "idea": cmd_idea, "pieza": cmd_pieza, "publicacion": cmd_publicacion, "lead": cmd_lead,
    "metrica": cmd_metrica, "calendario": cmd_calendario, "fabrica": cmd_fabrica, "web": cmd_web,
    "campana": cmd_campana, "sitio": cmd_sitio, "rutina": cmd_rutina, "radar": cmd_radar, "experimento": cmd_experimento,
}


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    cfg = config.cargar(args.espacio)
    try:
        return COMANDOS[args.comando](cfg, args)
    except Exception as e:  # mensaje humano y rastro en la base
        print(f"No se pudo completar «{args.comando}»: {e}", file=sys.stderr)
        try:
            cx = _cx(cfg)
            db.registrar_error(cx, "cli", type(e).__name__, str(e))
        except Exception:
            pass
        return 1
    finally:
        while _ABIERTAS:
            _ABIERTAS.pop().close()


if __name__ == "__main__":
    sys.exit(main())
