"""La fábrica de piezas: plantillas, validación de textos, HTML sin dependencias externas y exportación real."""

from __future__ import annotations

import os
import re
import struct
import unittest

from mos import config, contenido
from mos.fabrica import plantillas, render
from tests.base import ConBase

RAIZ = config.RAIZ


def _navegador_disponible() -> bool:
    if os.environ.get("MOS_SIN_NAVEGADOR"):
        return False
    try:
        with render.Navegador():
            return True
    except Exception:
        return False


try:
    import jinja2  # noqa: F401
    JINJA = True
except ImportError:
    JINJA = False

NAVEGADOR = JINJA and _navegador_disponible()
FFMPEG = bool(os.environ.get("MOS_FFMPEG") or __import__("shutil").which("ffmpeg"))


def medidas_png(ruta) -> tuple[int, int]:
    cabecera = ruta.read_bytes()[:24]
    return struct.unpack(">II", cabecera[16:24])


@unittest.skipUnless(JINJA, "Falta jinja2 (python -m pip install -r requirements.txt)")
class Plantillas(unittest.TestCase):
    def test_estan_las_diez_plantillas_pedidas(self):
        self.assertEqual(plantillas.disponibles(RAIZ), {"promocion", "beneficio", "educativo", "noticia", "carrusel", "trivia",
                                                        "meme", "lanzamiento", "invitacion-demo", "motion"})

    def test_cada_ejemplo_cumple_su_plantilla_y_se_compone_en_todos_sus_formatos(self):
        for nombre in plantillas.disponibles(RAIZ):
            ficha = plantillas.ficha(RAIZ, nombre)
            with self.subTest(plantilla=nombre):
                self.assertEqual(render.validar(RAIZ, nombre, ficha["ejemplo"]), [])
                for formato in ficha["formatos"]:
                    for pagina in range(render.paginas(RAIZ, nombre, ficha["ejemplo"])):
                        html = render.componer(RAIZ, nombre, ficha["ejemplo"], formato=formato, marca="cuadra", pagina=pagina)
                        # todo va incrustado: ni fuentes ni imágenes ni scripts de Internet
                        self.assertNotRegex(html, r"(src|href)=\"https?://|url\(['\"]?https?://|<script[^>]+src=")
                        self.assertIn("window.__listo", html)

    def test_la_promocion_solo_admite_piezas_promocionales(self):
        self.assertEqual(plantillas.ficha(RAIZ, "promocion")["tipos_afirmacion"], ["PROMOCIONAL"])


class Validacion(unittest.TestCase):
    def test_falta_un_campo_obligatorio(self):
        problemas = render.validar(RAIZ, "educativo", {"puntos": ["uno", "dos"]})
        self.assertTrue(any("titular: falta" in p for p in problemas))

    def test_un_texto_demasiado_largo_se_rechaza_sin_contar_los_asteriscos(self):
        self.assertEqual(render.validar(RAIZ, "educativo", {"titular": "*" + "a" * 80 + "*", "puntos": ["a", "b"]}), [])
        problemas = render.validar(RAIZ, "educativo", {"titular": "a" * 81, "puntos": ["a", "b"]})
        self.assertTrue(any("81 caracteres" in p for p in problemas))

    def test_listas_laminas_e_iconos(self):
        self.assertTrue(render.validar(RAIZ, "educativo", {"titular": "x", "puntos": ["solo uno"]}))
        problemas = render.validar(RAIZ, "carrusel", {"laminas": [{"tipo": "portada", "titulo": "a"}, {"tipo": "otro", "titulo": "b"},
                                                                  {"tipo": "paso", "titulo": "c", "icono": "no-existe"}]})
        self.assertTrue(any("laminas[2].tipo" in p for p in problemas))
        self.assertTrue(any("laminas[3].icono" in p for p in problemas))

    def test_una_captura_que_no_existe_se_rechaza(self):
        problemas = render.validar(RAIZ, "beneficio", {"titular": "x", "captura": "no-existe.png"})
        self.assertTrue(any("no encuentro la captura" in p for p in problemas))


@unittest.skipUnless(JINJA, "Falta jinja2 (python -m pip install -r requirements.txt)")
class Html(unittest.TestCase):
    def test_los_textos_se_escapan_y_los_asteriscos_resaltan(self):
        datos = {"titular": "<b>Hola</b> *resaltado*", "puntos": ["a & b", "c"]}
        html = render.componer(RAIZ, "educativo", datos, formato="vertical", marca="cuadra")
        self.assertIn("&lt;b&gt;Hola&lt;/b&gt; <mark>resaltado</mark>", html)
        self.assertIn("a &amp; b", html)

    def test_un_formato_que_la_plantilla_no_tiene(self):
        with self.assertRaises(render.ErrorFabrica):
            render.componer(RAIZ, "meme", plantillas.ficha(RAIZ, "meme")["ejemplo"], formato="horizontal")


class Guion(unittest.TestCase):
    def test_guion_subtitulos_y_teleprompter(self):
        datos = {"escenas": [{"pantalla": "Uno", "locucion": "Primera frase.", "segundos": 3},
                             {"pantalla": "Dos", "segundos": 2},
                             {"pantalla": "Tres", "locucion": "Tercera frase.", "segundos": 4}]}
        paquete = render.paquete_guion(datos, "Prueba")
        srt = paquete["subtitulos.srt"]
        self.assertIn("1\n00:00:00,000 --> 00:00:03,000\nPrimera frase.", srt)
        self.assertIn("2\n00:00:05,000 --> 00:00:09,000\nTercera frase.", srt)
        self.assertIn("Duración total: 9 segundos", paquete["guion.md"])
        self.assertIn("Tercera frase.", paquete["teleprompter.html"])


@unittest.skipUnless(NAVEGADOR, "Sin navegador para renderizar (instala requirements.txt y Chromium o Edge)")
class Exportacion(ConBase):
    def test_una_imagen_por_formato_con_su_medida_exacta(self):
        ficha = plantillas.ficha(RAIZ, "educativo")
        res = render.exportar(RAIZ, "educativo", ficha["ejemplo"], self.tmp / "x", "edu", formatos=["vertical", "cuadrado"],
                              marca="cuadra")
        self.assertEqual([p.name for p in res.archivos], ["edu-vertical.png", "edu-cuadrado.png"])
        self.assertEqual(medidas_png(res.archivos[0]), (1080, 1350))
        self.assertEqual(medidas_png(res.archivos[1]), (1080, 1080))
        self.assertEqual(res.avisos, [])

    def test_un_texto_que_no_cabe_se_avisa(self):
        datos = {"titular": "x" * 80, "puntos": ["uno", "dos"]}     # una sola «palabra» de 80 letras no se puede partir
        res = render.exportar(RAIZ, "educativo", datos, self.tmp / "x", "largo", formatos=["cuadrado"], marca="cuadra")
        self.assertTrue(res.archivos[0].exists())
        self.assertTrue(any("no cabe" in a for a in res.avisos), res.avisos)

    def test_carrusel_en_png_y_pdf_y_trivia_interactiva(self):
        ficha = plantillas.ficha(RAIZ, "carrusel")
        res = render.exportar(RAIZ, "carrusel", ficha["ejemplo"], self.tmp / "c", "car", formatos=["vertical"], marca="cuadra")
        nombres = [p.name for p in res.archivos]
        self.assertEqual(len([n for n in nombres if n.endswith(".png")]), len(ficha["ejemplo"]["laminas"]))
        pdf = (self.tmp / "c" / "car-vertical.pdf").read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(len(re.findall(rb"/Type\s*/Page[^s]", pdf)), len(ficha["ejemplo"]["laminas"]))
        trivia = render.exportar(RAIZ, "trivia", plantillas.ficha(RAIZ, "trivia")["ejemplo"], self.tmp / "t", "tri",
                                 formatos=["cuadrado"], marca="cuadra")
        html = (self.tmp / "t" / "tri-interactivo.html").read_text(encoding="utf-8")
        self.assertIn("const correcta = 2", html)
        self.assertEqual(len([p for p in trivia.archivos if p.suffix == ".png"]), 2)

    def test_exportar_una_pieza_registra_sus_archivos(self):
        codigo = contenido.crear_pieza(self.cx, "cuadra", formato="post", canal="instagram", titulo="Cierre",
                                       tipo_afirmacion="EDUCATIVA", plantilla="educativo")
        datos = dict(plantillas.ficha(RAIZ, "educativo")["ejemplo"])
        contenido.nueva_version(self.cx, codigo, datos, capacidades=[])
        res = render.exportar_pieza(self.cx, self.cfg, codigo, formatos=["vertical"])
        fila = self.cx.execute("SELECT * FROM activo WHERE pieza_id = (SELECT id FROM pieza WHERE codigo = ?)", (codigo,)).fetchone()
        self.assertEqual(fila["formato"], "1080x1350")
        self.assertEqual(fila["origen"], "RENDER")
        self.assertEqual(fila["version"], 1)
        self.assertTrue((self.cfg.espacio / fila["ruta"]).exists())
        render.exportar_pieza(self.cx, self.cfg, codigo, formatos=["vertical"])   # repetir no duplica
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM activo").fetchone()[0], len(res.archivos))
        # si el archivo cambió (plantilla corregida y render forzado), el registro se pone al día en vez de duplicarse
        ruta = self.cfg.espacio / fila["ruta"]
        ruta.write_bytes(b"otra imagen")
        render._registrar_activo(self.cx, self.cfg, fila["pieza_id"], 1, ruta, "imagen", 1080, 1350, None, "1080x1350")
        filas = self.cx.execute("SELECT sha256 FROM activo WHERE ruta = ?", (fila["ruta"],)).fetchall()
        self.assertEqual(len(filas), 1)
        self.assertNotEqual(filas[0]["sha256"], fila["sha256"])

    def test_la_misma_imagen_para_varios_canales_se_renderiza_una_sola_vez(self):
        ejemplo = plantillas.ficha(RAIZ, "educativo")["ejemplo"]
        cache: dict = {}
        a = render.exportar(RAIZ, "educativo", ejemplo, self.tmp / "a", "fb", formatos=["cuadrado"], marca="cuadra", cache=cache)
        # mismo texto visible, otro copy del post: se copia sin abrir el navegador (un objeto vacío fallaría si se usara)
        b = render.exportar(RAIZ, "educativo", ejemplo | {"copy": "Texto para LinkedIn"}, self.tmp / "b", "li",
                            formatos=["cuadrado"], marca="cuadra", cache=cache, navegador=object())
        self.assertEqual([p.name for p in b.archivos], ["li-cuadrado.png"])
        self.assertEqual(b.archivos[0].read_bytes(), a.archivos[0].read_bytes())
        c = render.exportar(RAIZ, "educativo", ejemplo | {"titular": "Otro titular"}, self.tmp / "c", "ig",
                            formatos=["cuadrado"], marca="cuadra", cache=cache)
        self.assertNotEqual(c.archivos[0].read_bytes(), a.archivos[0].read_bytes())

    def test_una_pieza_sin_plantilla_no_se_renderiza(self):
        codigo = contenido.crear_pieza(self.cx, "cuadra", formato="post", canal="facebook", titulo="Sin plantilla",
                                       tipo_afirmacion="EDUCATIVA")
        contenido.nueva_version(self.cx, codigo, {"copy": "Hola"})
        with self.assertRaises(render.ErrorFabrica):
            render.exportar_pieza(self.cx, self.cfg, codigo)

    @unittest.skipUnless(FFMPEG, "Sin FFmpeg")
    def test_video_corto_con_guion(self):
        datos = {"cierre_titular": "Fin", "cta": "Únete a la lista de espera",
                 "escenas": [{"pantalla": "Uno", "locucion": "Hola.", "segundos": 2}, {"pantalla": "Dos", "segundos": 2}]}
        res = render.exportar(RAIZ, "motion", datos, self.tmp / "v", "vid", formatos=["cuadrado"], marca="cuadra")
        nombres = sorted(p.name for p in res.archivos)
        self.assertEqual(nombres, ["vid-cuadrado-portada.png", "vid-cuadrado.mp4", "vid-guion.md", "vid-subtitulos.srt",
                                   "vid-teleprompter.html"])
        mp4 = (self.tmp / "v" / "vid-cuadrado.mp4").read_bytes()
        self.assertEqual(mp4[4:8], b"ftyp")
        self.assertEqual(res.duraciones_ms["vid-cuadrado.mp4"], 7500)
