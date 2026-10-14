"""Fase 6: el CSV de cada red entra sin inventar datos, los experimentos se calculan solo con lo medido y la métrica norte cuenta bien."""

from __future__ import annotations

from pathlib import Path

from mos import campanas, contenido, experimentos, leads, metricas
from tests.base import ConBase

CAMPANA = Path(__file__).resolve().parent.parent / "campanas" / "lista-espera-beta"


class ConCampana(ConBase):
    def setUp(self) -> None:
        super().setUp()
        campanas.cargar(self.cx, self.cfg, CAMPANA)
        self.piezas = campanas.piezas_de(self.cx, "lista-espera-beta")

    def publicar(self, clave: str, url: str, id_externo: str | None = None) -> int:
        """Pasa la pieza por el auditor, la aprueba y la confirma con su enlace, como haría Didi."""
        codigo = self.piezas[clave]["codigo"]
        contenido.auditar_pieza(self.cx, self.cfg.raiz, codigo)
        contenido.decidir(self.cx, codigo, "APROBADA", "Didi")
        pid = contenido.preparar_publicacion(self.cx, codigo)
        contenido.confirmar_publicacion(self.cx, pid, url=url, id_externo=id_externo)
        return pid


class ImportarCsv(ConCampana):
    def test_reconoce_columnas_de_la_red_y_enlaza_por_url_o_por_id(self):
        p1 = self.publicar("C02-ig", "https://www.instagram.com/p/AAA111/")
        p2 = self.publicar("C06-ig", "https://www.instagram.com/p/BBB222/", id_externo="1790001")
        ruta = self.tmp / "instagram.csv"
        ruta.write_text(
            "Id. de la publicación;Enlace permanente;Descripción;Alcance;Me gusta;Guardados;Comentarios;Tasa\n"
            "Identificador;Enlace;Texto;Cuentas;Total;Total;Total;%\n"
            "999;https://www.instagram.com/p/AAA111/?igsh=xyz;Texto;1.234;56;7;3;4,5\n"
            "1790001;;Texto;800;20;12;1;2,5\n"
            "555;https://www.instagram.com/p/OTRA/;Texto;10;1;0;0;10\n", encoding="utf-8")
        r = metricas.importar_csv(self.cx, ruta, fecha="2026-10-25", revisar=True)
        self.assertEqual((r.filas, r.emparejadas, r.metricas, r.sin_publicacion), (4, 2, 8, 1))
        self.assertEqual(r.reconocidas["Alcance"], "alcance")
        self.assertEqual(r.reconocidas["Me gusta"], "reacciones")
        self.assertIn("Tasa", r.ignoradas)
        self.assertEqual(r.ejemplos_sin_publicacion, ["https://www.instagram.com/p/OTRA/"])
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM metrica").fetchone()[0], 0)   # revisar no guarda
        metricas.importar_csv(self.cx, ruta, fecha="2026-10-25")
        valores = dict(self.cx.execute("SELECT publicacion_id || ':' || nombre, valor FROM metrica").fetchall())
        self.assertEqual(valores[f"{p1}:alcance"], 1234)
        self.assertEqual(valores[f"{p2}:guardados"], 12)
        metricas.importar_csv(self.cx, ruta, fecha="2026-10-25")       # dos veces el mismo día no duplica
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM metrica").fetchone()[0], 8)

    def test_sin_columna_de_enlace_explica_que_hacer(self):
        ruta = self.tmp / "raro.csv"
        ruta.write_text("Cosa,Alcance\nx,10\n", encoding="utf-8")
        with self.assertRaisesRegex(metricas.ErrorMetrica, "metricas-csv.toml"):
            metricas.importar_csv(self.cx, ruta)

    def test_un_decimal_no_se_convierte_en_un_entero_falso(self):
        self.publicar("C02-ig", "https://www.instagram.com/p/AAA111/")
        ruta = self.tmp / "planilla.csv"
        ruta.write_text("url,alcance,guardados\nhttps://www.instagram.com/p/AAA111,12.5,3\n", encoding="utf-8")
        r = metricas.importar_csv(self.cx, ruta)
        self.assertEqual((r.metricas, r.no_leidas), (1, 1))
        self.assertIsNone(self.cx.execute("SELECT 1 FROM metrica WHERE nombre = 'alcance'").fetchone())

    def test_la_planilla_propia_puede_traer_la_fecha_de_cada_medicion(self):
        pub = self.publicar("C02-ig", "https://www.instagram.com/p/AAA111/")
        ruta = self.tmp / "planilla.csv"
        ruta.write_text("url,fecha,alcance\n"
                        "https://www.instagram.com/p/AAA111,2026-10-20,100\n"
                        "https://www.instagram.com/p/AAA111,2026-10-27,180\n"
                        "https://www.instagram.com/p/AAA111,27/10/2026,999\n", encoding="utf-8")
        r = metricas.importar_csv(self.cx, ruta, fecha="2026-11-01")
        self.assertEqual((r.metricas, r.fecha_invalida), (2, 1))
        filas = self.cx.execute("SELECT fecha, valor FROM metrica WHERE publicacion_id = ? ORDER BY fecha", (pub,)).fetchall()
        self.assertEqual([tuple(f) for f in filas], [("2026-10-20", 100), ("2026-10-27", 180)])


class Experimentos(ConCampana):
    def medir(self, pub: int, **valores: int) -> None:
        for nombre, valor in valores.items():
            metricas.registrar(self.cx, nombre, valor, "2026-11-14", publicacion_id=pub)

    def test_los_experimentos_de_la_campana_se_cargan_sin_duplicar_y_sin_pisar_la_decision(self):
        self.assertEqual(experimentos.cargar(self.cx, CAMPANA), (5, 0))
        experimentos.cancelar(self.cx, "EXP-02", "No hubo captura a tiempo")
        self.assertEqual(experimentos.cargar(self.cx, CAMPANA), (0, 5))
        fila = experimentos.obtener(self.cx, "EXP-02")
        self.assertEqual((fila["estado"], fila["resultado"]), ("CANCELADO", "Cancelado: No hubo captura a tiempo"))

    def test_cada_grupo_nombra_piezas_que_existen(self):
        for x in experimentos.leer(CAMPANA):
            for grupo in (x.get("grupos") or {}).values():
                with self.subTest(experimento=x["codigo"]):
                    self.assertLessEqual(set(grupo), set(self.piezas))

    def test_el_resultado_usa_solo_lo_medido_y_avisa_cuando_es_un_indicio(self):
        experimentos.cargar(self.cx, CAMPANA)
        r = experimentos.calcular(self.cx, "EXP-02")
        self.assertIn("Sin datos medidos", r.lectura)
        con_captura = self.publicar("C17-ig", "https://www.instagram.com/p/C17/")
        con_icono = self.publicar("C06-ig", "https://www.instagram.com/p/C06/")
        self.medir(con_captura, alcance=1000, guardados=30, conversaciones=10)    # 4 %
        self.medir(con_icono, alcance=1000, guardados=20)                         # 2 %
        metricas.registrar(self.cx, "guardados", 900, "2026-11-14", naturaleza="ESTIMADA", publicacion_id=con_icono)
        r = experimentos.calcular(self.cx, "EXP-02")
        self.assertEqual((r.grupos["A"].tasa_bp, r.grupos["B"].tasa_bp), (400, 200))   # lo estimado no entra
        self.assertAlmostEqual(r.razon, 2.0)
        self.assertIn("«Con captura real» queda 2.00 veces por encima", r.lectura)
        self.assertTrue(r.provisional)
        self.assertIn("indicio", r.lectura)

    def test_cerrar_pide_decision_y_resultado(self):
        experimentos.cargar(self.cx, CAMPANA)
        with self.assertRaises(experimentos.ErrorExperimento):
            experimentos.cerrar(self.cx, "EXP-01", "GANAR", "x")
        with self.assertRaises(experimentos.ErrorExperimento):
            experimentos.cerrar(self.cx, "EXP-01", "CONTINUAR", " ")
        experimentos.empezar(self.cx, "EXP-01")
        experimentos.cerrar(self.cx, "EXP-01", "CONTINUAR", "Oficio 1,6 veces Producto real con 9 publicaciones.")
        fila = experimentos.obtener(self.cx, "EXP-01")
        self.assertEqual((fila["estado"], fila["decision"]), ("TERMINADO", "CONTINUAR"))
        with self.assertRaises(experimentos.ErrorExperimento):
            experimentos.empezar(self.cx, "EXP-01")


class MetricaNorte(ConCampana):
    def test_cuenta_solo_consentimiento_sin_baja(self):
        def registrar(email: str, consentimiento: bool = True) -> None:
            leads.registrar(self.cx, "cuadra", fuente="whatsapp", email=email, campana="lista-espera-beta",
                            consentimiento=consentimiento, finalidad="lista de espera" if consentimiento else "",
                            consentimiento_version="v1", consentimiento_medio="prueba")
        registrar("a@example.com")
        registrar("b@example.com")
        registrar("c@example.com", consentimiento=False)
        self.assertEqual(leads.metrica_norte(self.cx, campana="lista-espera-beta"), 2)
        leads.dar_de_baja(self.cx, "b@example.com")
        self.assertEqual(leads.metrica_norte(self.cx, campana="lista-espera-beta"), 1)
        leads.suprimir(self.cx, "a@example.com")
        self.assertEqual(leads.metrica_norte(self.cx, producto="cuadra"), 0)


class LineaDeComandos(ConCampana):
    def test_cargar_ver_y_cerrar_desde_la_consola(self):
        import contextlib
        import io

        from mos.__main__ import main
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--espacio", str(self.tmp), "experimento", "cargar", str(CAMPANA)]), 0)
            self.assertEqual(main(["--espacio", str(self.tmp), "experimento", "resultado", "EXP-01"]), 0)
            self.assertEqual(main(["--espacio", str(self.tmp), "experimento", "empezar", "EXP-01"]), 0)
            self.assertEqual(main(["--espacio", str(self.tmp), "experimento", "cerrar", "EXP-01"]), 2)        # sin decisión no se cierra
            self.assertEqual(main(["--espacio", str(self.tmp), "experimento", "cerrar", "EXP-01", "--decision", "INVESTIGAR",
                                   "--resultado", "Muy pocos datos para leer nada."]), 0)
        texto = salida.getvalue()
        self.assertIn("Sin datos medidos todavía", texto)
        self.assertIn("EXP-01: en curso.", texto)
        self.assertEqual(experimentos.obtener(self.cx, "EXP-01")["decision"], "INVESTIGAR")


class Panel(ConCampana):
    def test_la_pagina_de_metricas_muestra_los_experimentos_y_su_lectura(self):
        from tests.test_web import Cliente
        from mos.web import app as web
        experimentos.cargar(self.cx, CAMPANA)
        experimentos.cancelar(self.cx, "EXP-05", "La landing no se publicó")
        codigo, _, cuerpo = Cliente(web.crear_app(self.cfg)).get("/metricas")
        self.assertEqual(codigo, 200, cuerpo[:600])
        self.assertIn("EXP-01", cuerpo)
        self.assertIn("Sin datos medidos todavía", cuerpo)
        self.assertIn("Cancelado: La landing no se publicó", cuerpo)
