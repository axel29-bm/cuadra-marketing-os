"""El lector del radar: respeta robots.txt, no inventa novedades en la primera lectura y nunca verifica nada solo."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mos import radar_lector, util
from tests.base import ConBase

AHORA = datetime(2026, 10, 20, 13, 0, tzinfo=timezone.utc)

INDICE_1 = """<html><head><title>Resoluciones 2026</title><style>.x{}</style></head><body>
<a href="/legislacion/superin/2026/123-2026.pdf">123-2026/SUNAT</a>
<a href="/legislacion/superin/2026/124-2026.pdf">124-2026/SUNAT</a>
<a href="https://otro-sitio.example/spam">Fuera del sitio</a>
<a href="http://www.sunat.gob.pe/inseguro">Sin https</a>
</body></html>"""
INDICE_2 = INDICE_1.replace("</body>", '<a href="/legislacion/superin/2026/125-2026.pdf">125-2026/SUNAT · SIRE</a></body>')

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://busquedas.elperuano.pe/dispositivo/NL/2420001-1</loc><lastmod>2026-10-19</lastmod></url>
  <url><loc>https://busquedas.elperuano.pe/normaslegales/resolucion-de-superintendencia-sunat-sire-2420002-1/</loc><lastmod>2026-10-19</lastmod></url>
  <url><loc>https://busquedas.elperuano.pe/normaslegales/designan-director-de-hospital-2420003-1/</loc><lastmod>2026-10-19</lastmod></url>
  <url><loc>https://busquedas.elperuano.pe/normaslegales/norma-vieja-de-sunat-2000000-1/</loc><lastmod>2025-01-10</lastmod></url>
</urlset>"""
NORMA_OPACA = '<html><head><meta property="og:title" content="Decreto Supremo que aprueba el valor de la UIT - Economía y Finanzas"></head></html>'


class Red:
    """Internet de mentira: un diccionario de direcciones y lo que devuelven, con registro de lo pedido."""

    def __init__(self, paginas: dict[str, bytes | str | Exception]):
        self.paginas = paginas
        self.pedidas: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.pedidas.append(url)
        r = self.paginas.get(url, radar_lector.NoEncontrado(url))
        if isinstance(r, Exception):
            raise r
        return r.encode("utf-8") if isinstance(r, str) else r


class Lector(ConBase):
    def setUp(self) -> None:
        super().setUp()
        self.cx.execute("UPDATE fuente SET activa = 0")

    def fuente(self, slug: str, url: str, metodo: str = "HTML", filtro: list[str] | None = None, rss: str | None = None,
               frecuencia: int = 24) -> None:
        self.cx.execute("""INSERT INTO fuente (slug, tipo, titulo, url, rss_url, metodo, frecuencia_horas, filtro)
                           VALUES (?, 'OFICIAL', ?, ?, ?, ?, ?, ?)""",
                        (slug, slug.title(), url, rss, metodo, frecuencia, util.a_json(filtro or [])))

    def leer(self, red: Red, ahora: datetime = AHORA, **kw) -> dict[str, radar_lector.Lectura]:
        return {r.fuente: r for r in radar_lector.leer_fuentes(self.cx, ahora=ahora, bajar=red, pausa=0, **kw)}

    def items(self) -> list:
        return self.cx.execute("SELECT * FROM radar_item ORDER BY id").fetchall()

    # ------------------------------------------------------------------------------------------ HTML

    def test_la_primera_lectura_es_punto_de_partida_y_luego_solo_entra_lo_nuevo(self):
        url = "https://www.sunat.gob.pe/legislacion/superin/2026/indices/indcor.htm"
        self.fuente("prueba-sunat-resoluciones", url)
        red = Red({"https://www.sunat.gob.pe/robots.txt": "User-agent: *\nDisallow: /cl-ti-itmenu/\n", url: INDICE_1})
        self.assertEqual(self.leer(red)["prueba-sunat-resoluciones"].estado, "PUNTO_DE_PARTIDA")
        self.assertEqual(self.items(), [])
        red.paginas[url] = INDICE_2
        r = self.leer(red, AHORA + timedelta(days=1))["prueba-sunat-resoluciones"]
        self.assertEqual((r.estado, r.nuevas), ("NUEVAS", 1))
        item = self.items()[0]
        self.assertEqual(item["url"], "https://www.sunat.gob.pe/legislacion/superin/2026/125-2026.pdf")
        self.assertEqual(item["titulo"], "125-2026/SUNAT · SIRE")
        self.assertEqual((item["estado_verificacion"], item["es_fuente_primaria"]), ("SIN_VERIFICAR", 1))
        # leer de nuevo la misma página no duplica nada
        self.assertEqual(self.leer(red, AHORA + timedelta(days=2))["prueba-sunat-resoluciones"].estado, "SIN_NOVEDADES")
        self.assertEqual(len(self.items()), 1)

    def test_si_cambia_el_texto_sin_enlaces_nuevos_se_anota_el_cambio(self):
        url = "https://www.sunat.gob.pe/indicestasas/uit.html"
        self.fuente("prueba-sunat-uit", url, frecuencia=168)
        red = Red({url: "<p>UIT 2026: S/ 5 500</p>"})
        self.leer(red)
        red.paginas[url] = "<p>UIT 2027: S/ 5 700</p>"
        self.leer(red, AHORA + timedelta(days=8))
        item = self.items()[0]
        self.assertTrue(item["url"].startswith(url + "#cambio-"))
        self.assertIn("Cambió la página", item["titulo"])

    def test_respeta_la_frecuencia_de_cada_fuente(self):
        url = "https://www.sunat.gob.pe/mensajes/mensajes-SUNAT.html"
        self.fuente("prueba-sunat-comunicados", url)
        red = Red({url: INDICE_1})
        self.leer(red)
        pedidas = len(red.pedidas)
        self.assertEqual(self.leer(red, AHORA + timedelta(hours=3))["prueba-sunat-comunicados"].estado, "NO_TOCA")
        self.assertEqual(len(red.pedidas), pedidas)
        self.assertEqual(self.leer(red, AHORA + timedelta(hours=3), forzar=True)["prueba-sunat-comunicados"].estado, "SIN_NOVEDADES")

    def test_robots_txt_manda(self):
        url = "https://www.sunat.gob.pe/legislacion/superin/2026/indices/indcor.htm"
        self.fuente("prueba-sunat-resoluciones", url)
        red = Red({"https://www.sunat.gob.pe/robots.txt": "User-agent: *\nDisallow: /legislacion/\n", url: INDICE_1})
        r = self.leer(red)["prueba-sunat-resoluciones"]
        self.assertEqual(r.estado, "BLOQUEADA")
        self.assertNotIn(url, red.pedidas)
        self.assertIn("robots.txt", self.cx.execute("SELECT ultimo_error FROM fuente WHERE slug = 'prueba-sunat-resoluciones'").fetchone()[0])

    def test_un_error_queda_registrado_y_no_detiene_las_demas(self):
        caida = "https://www.mef.gob.pe/es/decretos"
        buena = "https://www.sunat.gob.pe/salaprensa/lima/index.html"
        self.fuente("mef-decretos", caida)
        self.fuente("sunat-prensa", buena)
        red = Red({caida: radar_lector.ErrorLectura("respondió 503"), buena: INDICE_1})
        r = self.leer(red)
        self.assertEqual((r["mef-decretos"].estado, r["sunat-prensa"].estado), ("ERROR", "PUNTO_DE_PARTIDA"))
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM registro_error WHERE modulo = 'radar'").fetchone()[0], 1)

    def test_una_fuente_manual_nunca_se_descarga(self):
        self.fuente("whatsapp", "https://whatsapp.com/channel/x", metodo="MANUAL")
        red = Red({})
        self.assertEqual(self.leer(red), {})
        self.assertEqual(red.pedidas, [])

    # --------------------------------------------------------------------------------------- sitemap

    def test_sitemap_filtra_por_tema_y_fecha_y_lee_el_titulo_si_la_direccion_no_dice_nada(self):
        self.fuente("elperuano", "https://busquedas.elperuano.pe/", metodo="SITEMAP",
                    rss="https://busquedas.elperuano.pe/sitemap/normas.xml", filtro=["sunat", "economia y finanzas"])
        red = Red({"https://busquedas.elperuano.pe/sitemap/normas.xml": SITEMAP,
                   "https://busquedas.elperuano.pe/dispositivo/NL/2420001-1": NORMA_OPACA})
        r = self.leer(red)["elperuano"]
        self.assertEqual((r.estado, r.nuevas), ("NUEVAS", 2))
        titulos = {i["titulo"] for i in self.items()}
        self.assertEqual(titulos, {"Decreto Supremo que aprueba el valor de la UIT - Economía y Finanzas",
                                   "Resolucion de superintendencia sunat sire 2420002 1"})
        self.assertEqual({i["fecha_publicacion"] for i in self.items()}, {"2026-10-19"})
        # La del hospital no pasa el filtro y la de 2025 es vieja: no se abren ni entran
        self.assertNotIn("https://busquedas.elperuano.pe/normaslegales/designan-director-de-hospital-2420003-1/", red.pedidas)
        self.leer(red, AHORA + timedelta(days=1))
        self.assertEqual(len(self.items()), 2)

    def test_indice_de_sitemaps(self):
        indice = """<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://busquedas.elperuano.pe/sitemap/2026-09.xml</loc><lastmod>2026-09-30</lastmod></sitemap>
          <sitemap><loc>https://busquedas.elperuano.pe/sitemap/2026-10.xml</loc><lastmod>2026-10-19</lastmod></sitemap>
          <sitemap><loc>https://otro.example/sitemap.xml</loc><lastmod>2026-10-20</lastmod></sitemap>
        </sitemapindex>"""
        self.fuente("elperuano", "https://busquedas.elperuano.pe/", metodo="SITEMAP",
                    rss="https://busquedas.elperuano.pe/sitemap.xml", filtro=["sunat"])
        red = Red({"https://busquedas.elperuano.pe/sitemap.xml": indice,
                   "https://busquedas.elperuano.pe/sitemap/2026-10.xml": SITEMAP,
                   "https://busquedas.elperuano.pe/sitemap/2026-09.xml": "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'/>"})
        self.assertEqual(self.leer(red)["elperuano"].nuevas, 1)
        self.assertNotIn("https://otro.example/sitemap.xml", red.pedidas)

    def test_un_xml_roto_es_un_error_explicado(self):
        self.fuente("elperuano", "https://busquedas.elperuano.pe/", metodo="SITEMAP", rss="https://busquedas.elperuano.pe/s.xml")
        r = self.leer(Red({"https://busquedas.elperuano.pe/s.xml": "<urlset><url>"}))["elperuano"]
        self.assertEqual(r.estado, "ERROR")
        self.assertIn("XML", r.detalle)


class Fuentes(ConBase):
    def test_las_fuentes_reales_tienen_filtro_y_metodo_valido(self):
        filas = {f["slug"]: f for f in self.cx.execute("SELECT * FROM fuente")}
        self.assertIn("sunat", util.de_json(filas["elperuano-normas-sitemap"]["filtro"]))
        for f in filas.values():
            if f["metodo"] in radar_lector.AUTOMATICOS:
                self.assertTrue(f["url"].startswith("https://") or f["metodo"] == "SITEMAP", f["slug"])
