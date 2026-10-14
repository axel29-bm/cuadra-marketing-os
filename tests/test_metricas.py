"""Métricas: lo medido no se mezcla con lo estimado y registrar dos veces no duplica."""

from mos import contenido, metricas
from tests.base import ConBase


class Metricas(ConBase):
    def publicada(self, n):
        p = contenido.crear_pieza(self.cx, "cuadra", formato="post", canal="facebook", titulo=f"P{n}",
                                  tipo_afirmacion="EDUCATIVA")
        contenido.nueva_version(self.cx, p, {"copy": f"Cierras el mes y queda cerrado de verdad ({n})."},
                                capacidades=["CU-LIB-05"])
        contenido.auditar_pieza(self.cx, self.cfg.raiz, p)
        contenido.decidir(self.cx, p, "APROBADA", "Didi")
        pub = contenido.preparar_publicacion(self.cx, p)
        contenido.confirmar_publicacion(self.cx, pub, url=f"https://facebook.com/x/{n}", publicada_en="2026-10-05T15:00:00Z")
        return pub

    def test_registrar_dos_veces_reemplaza(self):
        pub = self.publicada(1)
        metricas.registrar(self.cx, "alcance", 100, "2026-10-06", publicacion_id=pub)
        metricas.registrar(self.cx, "alcance", 120, "2026-10-06", publicacion_id=pub)
        self.assertEqual(self.cx.execute("SELECT COUNT(*), MAX(valor) FROM metrica").fetchone()[:], (1, 120))

    def test_medido_y_estimado_van_separados(self):
        pub = self.publicada(1)
        metricas.registrar(self.cx, "alcance", 300, "2026-10-06", publicacion_id=pub)
        metricas.registrar(self.cx, "alcance", 999, "2026-10-06", publicacion_id=pub, naturaleza="ESTIMADA")
        r = metricas.resumen(self.cx, "2026-10-01", "2026-10-31")
        self.assertEqual(r["medido"]["facebook"]["alcance"], 300)
        self.assertEqual(r["estimado"]["facebook"]["alcance"], 999)

    def test_sin_datos_suficientes_no_se_recomienda_nada_concreto(self):
        self.publicada(1)
        recs = metricas.recomendaciones(self.cx, "2026-10-01", "2026-10-31")
        self.assertEqual([r["decision"] for r in recs], ["INVESTIGAR"])

    def test_recomienda_repetir_lo_que_trajo_interesados(self):
        pubs = [self.publicada(i) for i in range(4)]
        for i, pub in enumerate(pubs):
            metricas.registrar(self.cx, "alcance", 1000, "2026-10-06", publicacion_id=pub)
            metricas.registrar(self.cx, "reacciones", [10, 20, 30, 90][i], "2026-10-06", publicacion_id=pub)
        metricas.registrar(self.cx, "leads", 2, "2026-10-06", publicacion_id=pubs[0])
        decisiones = {r.get("pieza"): r["decision"] for r in metricas.recomendaciones(self.cx, "2026-10-01", "2026-10-31")}
        self.assertEqual(decisiones["P-0001"], "CONTINUAR")
        self.assertEqual(decisiones["P-0004"], "CONTINUAR")

    def test_una_metrica_inventada_no_existe(self):
        with self.assertRaises(metricas.ErrorMetrica):
            metricas.registrar(self.cx, "felicidad", 10, "2026-10-06", campana=None, publicacion_id=1)
