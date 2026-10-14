"""Campañas escritas en archivos: herencia entre piezas, carga sin duplicar, calendario, paquete y la campaña real."""

from __future__ import annotations

import csv
import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from mos import campanas, canales, config, contenido
from mos.fabrica import render
from tests.base import ConBase

RAIZ = config.RAIZ
CAMPANA_REAL = RAIZ / "campanas" / "lista-espera-beta"

MINIMA = '''
[campana]
slug = "prueba"
producto = "cuadra"
nombre = "Campaña de prueba"
objetivo = "Probar"
hipotesis = "Si pruebo, aprendo"
oferta = "Nada"
cta = "Escríbenos «BETA» por mensaje"
metrica_exito = "Mensajes"
inicio = "2026-10-15"
fin = "2026-10-17"

[[dia]]
fecha = "2026-10-16"
actividad = "Revisión"

[[pieza]]
clave = "A-fb"
fecha = "2026-10-15"
canal = "facebook"
formato = "imagen"
plantilla = "educativo"
formatos = ["cuadrado"]
tipo = "EDUCATIVA"
tema = "Cinco revisiones"
capacidades = ["CU-EMP-03"]
[pieza.contenido]
titular = "5 cosas que revisar"
puntos = ["Correlativos", "Copia de seguridad"]
copy = "Cinco revisiones antes de cerrar el mes."

[[pieza]]
clave = "A-li"
basado_en = "A-fb"
fecha = "2026-10-17"
canal = "linkedin"
tema = "Cinco revisiones (LinkedIn)"
[pieza.contenido]
copy = "Versión para LinkedIn."
'''


def carpeta_con(texto: str) -> Path:
    carpeta = Path(tempfile.mkdtemp(prefix="mos-campana-"))
    (carpeta / "campana.toml").write_text(texto, encoding="utf-8")
    return carpeta


class Lectura(unittest.TestCase):
    def test_una_pieza_basada_en_otra_hereda_y_cambia_solo_lo_suyo(self):
        datos = campanas.leer(carpeta_con(MINIMA))
        li = {p["clave"]: p for p in datos["pieza"]}["A-li"]
        self.assertEqual((li["plantilla"], li["tipo"], li["capacidades"]), ("educativo", "EDUCATIVA", ["CU-EMP-03"]))
        self.assertEqual((li["fecha"], li["canal"]), ("2026-10-17", "linkedin"))
        self.assertEqual(li["contenido"]["titular"], "5 cosas que revisar")
        self.assertEqual(li["contenido"]["copy"], "Versión para LinkedIn.")

    def test_errores_de_escritura_se_explican(self):
        with self.assertRaisesRegex(campanas.ErrorCampana, "no existe"):
            campanas.leer(carpeta_con(MINIMA.replace('basado_en = "A-fb"', 'basado_en = "Z"')))
        with self.assertRaisesRegex(campanas.ErrorCampana, "sí misma"):
            campanas.leer(carpeta_con(MINIMA.replace('basado_en = "A-fb"', 'basado_en = "A-li"')))
        with self.assertRaisesRegex(campanas.ErrorCampana, "repetidas"):
            campanas.leer(carpeta_con(MINIMA.replace('clave = "A-li"', 'clave = "A-fb"')))
        with self.assertRaisesRegex(campanas.ErrorCampana, "No encuentro"):
            campanas.leer(Path(tempfile.mkdtemp()))


class Mover(unittest.TestCase):
    def test_mover_corre_todas_las_fechas_y_nada_mas(self):
        carpeta = carpeta_con(MINIMA)
        self.assertEqual(campanas.mover(carpeta, 7), 5)
        datos = campanas.leer(carpeta)
        self.assertEqual((datos["campana"]["inicio"], datos["campana"]["fin"]), ("2026-10-22", "2026-10-24"))
        self.assertEqual([p["fecha"] for p in datos["pieza"]], ["2026-10-22", "2026-10-24"])
        self.assertEqual(datos["dia"][0]["fecha"], "2026-10-23")
        self.assertEqual(datos["pieza"][0]["contenido"]["titular"], "5 cosas que revisar")


class Carga(ConBase):
    def test_cargar_dos_veces_no_duplica_y_un_cambio_crea_version(self):
        carpeta = carpeta_con(MINIMA)
        primera = campanas.cargar(self.cx, self.cfg, carpeta)
        self.assertEqual(len(primera.creadas), 2)
        segunda = campanas.cargar(self.cx, self.cfg, carpeta)
        self.assertEqual((segunda.creadas, segunda.actualizadas, len(segunda.sin_cambios)), ([], [], 2))
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM pieza_version").fetchone()[0], 2)

        (carpeta / "campana.toml").write_text(MINIMA.replace("Versión para LinkedIn.", "Otra versión."), encoding="utf-8")
        tercera = campanas.cargar(self.cx, self.cfg, carpeta)
        bd = campanas.piezas_de(self.cx, "prueba")
        self.assertEqual(tercera.actualizadas, [bd["A-li"]["codigo"]])
        self.assertEqual((bd["A-fb"]["version_actual"], bd["A-li"]["version_actual"]), (1, 2))
        self.assertEqual(bd["A-li"]["auditoria"], "APROBADO")

    def test_una_pieza_publicada_no_se_toca(self):
        carpeta = carpeta_con(MINIMA)
        campanas.cargar(self.cx, self.cfg, carpeta)
        codigo = campanas.piezas_de(self.cx, "prueba")["A-fb"]["codigo"]
        self.cx.execute("UPDATE pieza SET estado = 'PUBLICADA' WHERE codigo = ?", (codigo,))
        (carpeta / "campana.toml").write_text(MINIMA.replace("5 cosas que revisar", "Otro titular"), encoding="utf-8")
        res = campanas.cargar(self.cx, self.cfg, carpeta)
        self.assertIn(codigo, res.sin_cambios)
        self.assertEqual(campanas.piezas_de(self.cx, "prueba")["A-fb"]["version_actual"], 1)

    def test_calendario_con_dias_de_revision_y_todas_las_columnas(self):
        carpeta = carpeta_con(MINIMA)
        campanas.cargar(self.cx, self.cfg, carpeta)
        datos = campanas.leer(carpeta)
        filas = campanas.filas_calendario(datos, campanas.piezas_de(self.cx, "prueba"))
        self.assertEqual([f["fecha"] for f in filas], ["2026-10-15", "2026-10-16", "2026-10-17"])
        self.assertEqual(filas[1]["formato"], "sin publicación")
        self.assertEqual(filas[0]["aprobacion"], "Lista para tu aprobación")
        tabla = list(csv.DictReader(io.StringIO(campanas.calendario_csv(filas))))
        self.assertEqual(list(tabla[0]), campanas.COLUMNAS)
        md = campanas.calendario_md(datos, filas)
        self.assertIn("### 2026-10-17 · sábado · linkedin", md)
        self.assertIn("Versión para LinkedIn.", md)

    def test_el_paquete_junta_los_archivos_de_la_version_actual_con_su_texto(self):
        carpeta = carpeta_con(MINIMA)
        campanas.cargar(self.cx, self.cfg, carpeta)
        fila = campanas.piezas_de(self.cx, "prueba")["A-fb"]
        salida = self.cfg.salidas / fila["codigo"] / "v1"
        salida.mkdir(parents=True)
        imagen = salida / f"{fila['codigo']}-v1-cuadrado.png"
        imagen.write_bytes(b"png de prueba")
        render._registrar_activo(self.cx, self.cfg, fila["id"], 1, imagen, "imagen", 1080, 1080, None, "1080x1080")
        destino = self.tmp / "paquete"
        campanas.exportar_paquete(self.cx, self.cfg, carpeta, destino)
        self.assertEqual((destino / "2026-10-15-A-fb" / "A-fb-cuadrado.png").read_bytes(), b"png de prueba")
        texto = (destino / "2026-10-15-A-fb" / "texto.md").read_text(encoding="utf-8")
        self.assertIn("Cinco revisiones antes de cerrar el mes.", texto)
        self.assertTrue((destino / "2026-10-17-A-li" / "texto.md").exists())


class CampanaReal(ConBase):
    """La campaña de lanzamiento que se va a publicar: si alguien la edita y rompe una regla, esta prueba lo dice."""

    def setUp(self) -> None:
        super().setUp()
        self.datos = campanas.leer(CAMPANA_REAL)

    def test_cubre_treinta_dias_seguidos_sin_huecos_ni_dias_repetidos(self):
        c = self.datos["campana"]
        fechas = [p["fecha"] for p in self.datos["pieza"]] + [d["fecha"] for d in self.datos["dia"]]
        self.assertEqual(len(fechas), len(set(fechas)), "Hay dos cosas el mismo día")
        inicio = date.fromisoformat(c["inicio"])
        esperadas = {(inicio + timedelta(days=i)).isoformat() for i in range(30)}
        self.assertEqual(set(fechas), esperadas)
        self.assertEqual(c["fin"], max(esperadas))

    def test_cada_pieza_encaja_en_su_plantilla_y_formatos(self):
        try:
            from mos.fabrica import plantillas
        except ImportError:
            self.skipTest("Falta jinja2")
        for p in self.datos["pieza"]:
            with self.subTest(pieza=p["clave"]):
                self.assertEqual(render.validar(RAIZ, p["plantilla"], p["contenido"]), [])
                ficha = plantillas.ficha(RAIZ, p["plantilla"])
                self.assertLessEqual(set(p["formatos"]), set(ficha["formatos"]))
                self.assertIn(p["tipo"], ficha["tipos_afirmacion"])
                for campo in ("tema", "objetivo", "metrica", "verificacion", "audiencia"):
                    self.assertTrue(p.get(campo), f"Falta «{campo}»")
                self.assertTrue(p["contenido"].get("copy"), "Falta el texto para publicar")

    def test_cada_red_acepta_el_tamano_de_sus_piezas(self):
        for p in self.datos["pieza"]:
            aceptados = canales.canal(p["canal"], RAIZ).get("formatos", [])
            for formato in p["formatos"]:
                ancho, alto = render.FORMATOS[formato]
                with self.subTest(pieza=p["clave"], formato=formato):
                    self.assertIn(f"{ancho}x{alto}", aceptados, f"{p['canal']} no lista {ancho}x{alto} en semillas/canales.toml")

    def test_el_auditor_solo_frena_la_noticia_hasta_que_la_revise_un_contador(self):
        res = campanas.cargar(self.cx, self.cfg, CAMPANA_REAL)
        bd = campanas.piezas_de(self.cx, "lista-espera-beta")
        self.assertEqual(len(res.creadas), len(self.datos["pieza"]))
        for p in self.datos["pieza"]:
            fila = bd[p["clave"]]
            with self.subTest(pieza=p["clave"]):
                if p["tipo"] == "NOTICIA":
                    informe = contenido.auditar_pieza(self.cx, RAIZ, fila["codigo"])
                    self.assertEqual({h.regla for h in informe.bloqueantes}, {"revision_profesional"})
                else:
                    self.assertIn(fila["auditoria"], ("APROBADO", "CON_OBSERVACIONES"))

    def test_nada_se_publica_ni_se_aprueba_solo(self):
        campanas.cargar(self.cx, self.cfg, CAMPANA_REAL)
        estados = {f["estado"] for f in campanas.piezas_de(self.cx, "lista-espera-beta").values()}
        self.assertEqual(estados, {"LISTA_PARA_APROBAR", "CORRECCIONES"})   # la noticia, frenada hasta la revisión
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM aprobacion").fetchone()[0], 0)
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM publicacion").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
