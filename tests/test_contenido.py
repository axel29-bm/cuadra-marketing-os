"""Recorrido de una pieza: idea → versión → auditoría → aprobación → paquete → publicada con prueba."""

import sqlite3
import unittest
from datetime import date

from mos import contenido
from mos.contenido import ErrorContenido
from tests.base import ConBase

BUENO = {"gancho": "Antes de guardar, mira qué va a pasar",
         "copy": "Pegas tu Excel de compras y ves fila por fila qué va a pasar antes de guardar.",
         "cta": "Quiero participar en la beta"}


class Ideas(unittest.TestCase):
    def test_la_puntuacion_se_explica_factor_por_factor(self):
        puntos, detalle = contenido.puntuar_idea(5, 4, 5, 1, 2)
        self.assertEqual(puntos, round(30 + 25 + 20 * 0.75 + 15 * 0.75 + 10))
        self.assertIn("valor comercial 5/5", detalle["explicacion"])

    def test_una_oportunidad_cercana_suma_y_una_vencida_resta(self):
        hoy = date(2026, 10, 14)
        base, _ = contenido.puntuar_idea(3, 3, 3, 3, 3, hoy=hoy)
        cerca, _ = contenido.puntuar_idea(3, 3, 3, 3, 3, fecha_oportunidad="2026-10-20", hoy=hoy)
        pasada, _ = contenido.puntuar_idea(3, 3, 3, 3, 3, fecha_oportunidad="2026-10-01", hoy=hoy)
        self.assertEqual((cerca - base, pasada - base), (5, -10))

    def test_valores_fuera_de_rango_se_rechazan(self):
        with self.assertRaises(ErrorContenido):
            contenido.puntuar_idea(6, 3, 3, 3, 3)


class Flujo(ConBase):
    def pieza(self, tipo="CAPTACION", canal="facebook"):
        return contenido.crear_pieza(self.cx, "cuadra", formato="post", canal=canal, titulo="Importar compras",
                                     tipo_afirmacion=tipo, fecha_prevista="2026-10-20")

    def test_la_idea_se_guarda_con_su_puntuacion_y_pasa_a_produccion(self):
        i = contenido.crear_idea(self.cx, "cuadra", problema="Miedo a importar mal", idea_central="Vista previa",
                                 formato="carrusel", canal="facebook", etapa_embudo="INTERES", objetivo="Lista de espera",
                                 relevancia=5, atencion=4, valor_comercial=5, coste=1, esfuerzo=2,
                                 audiencia="contador-multiempresa")
        contenido.crear_pieza(self.cx, "cuadra", formato="carrusel", canal="facebook", titulo="x",
                              tipo_afirmacion="CAPTACION", idea=i)
        self.assertEqual(self.cx.execute("SELECT estado FROM idea WHERE codigo = ?", (i,)).fetchone()[0], "EN_PRODUCCION")

    def test_no_se_aprueba_sin_pasar_por_el_auditor(self):
        p = self.pieza()
        contenido.nueva_version(self.cx, p, BUENO, capacidades=["CU-REG-03"])
        with self.assertRaises(ErrorContenido):
            contenido.decidir(self.cx, p, "APROBADA", "Didi")

    def test_no_se_aprueba_una_version_con_bloqueos(self):
        p = self.pieza()
        contenido.nueva_version(self.cx, p, {"copy": "Descárgalo gratis", "cta": "Descarga ya"})
        self.assertEqual(contenido.auditar_pieza(self.cx, self.cfg.raiz, p).resultado, "RECHAZADO")
        self.assertEqual(contenido.obtener_pieza(self.cx, p)["estado"], "CORRECCIONES")
        with self.assertRaises(ErrorContenido):
            contenido.decidir(self.cx, p, "APROBADA", "Didi")

    def test_cambiar_el_texto_anula_la_aprobacion(self):
        p = self.pieza()
        contenido.nueva_version(self.cx, p, BUENO, capacidades=["CU-REG-03"])
        contenido.auditar_pieza(self.cx, self.cfg.raiz, p)
        contenido.decidir(self.cx, p, "APROBADA", "Didi")
        self.assertIsNotNone(contenido.aprobacion_vigente(self.cx, contenido.obtener_pieza(self.cx, p)))
        contenido.nueva_version(self.cx, p, BUENO | {"copy": "Otro texto"}, capacidades=["CU-REG-03"])
        self.assertIsNone(contenido.aprobacion_vigente(self.cx, contenido.obtener_pieza(self.cx, p)))
        with self.assertRaises(ErrorContenido):
            contenido.preparar_publicacion(self.cx, p)

    def test_publicada_solo_con_prueba(self):
        p = self.pieza()
        contenido.nueva_version(self.cx, p, BUENO, capacidades=["CU-REG-03"])
        contenido.auditar_pieza(self.cx, self.cfg.raiz, p)
        contenido.decidir(self.cx, p, "APROBADA", "Didi")
        pub = contenido.preparar_publicacion(self.cx, p, archivos=["salidas/x.png"])
        with self.assertRaises(ErrorContenido):
            contenido.confirmar_publicacion(self.cx, pub)
        with self.assertRaises(sqlite3.IntegrityError):  # la base también lo impide
            self.cx.execute("UPDATE publicacion SET estado = 'PUBLICADA' WHERE id = ?", (pub,))
        contenido.confirmar_publicacion(self.cx, pub, url="https://www.facebook.com/ejemplo/posts/1")
        self.assertEqual(contenido.obtener_pieza(self.cx, p)["estado"], "PUBLICADA")

    def test_publicar_por_api_exige_autorizacion(self):
        p = self.pieza()
        contenido.nueva_version(self.cx, p, BUENO, capacidades=["CU-REG-03"])
        contenido.auditar_pieza(self.cx, self.cfg.raiz, p)
        contenido.decidir(self.cx, p, "APROBADA", "Didi")
        with self.assertRaises(ErrorContenido):
            contenido.preparar_publicacion(self.cx, p, metodo="API_OFICIAL")

    def test_un_fallo_de_publicacion_queda_registrado_con_su_error(self):
        p = self.pieza()
        contenido.nueva_version(self.cx, p, BUENO, capacidades=["CU-REG-03"])
        contenido.auditar_pieza(self.cx, self.cfg.raiz, p)
        contenido.decidir(self.cx, p, "APROBADA", "Didi")
        pub = contenido.preparar_publicacion(self.cx, p)
        contenido.registrar_fallo(self.cx, pub, "La red rechazó el vídeo por duración")
        self.assertEqual(self.cx.execute("SELECT estado FROM publicacion WHERE id = ?", (pub,)).fetchone()[0], "FALLIDA")
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM registro_error").fetchone()[0], 1)

    def test_el_limite_del_canal_se_aplica_al_copy(self):
        p = self.pieza(canal="instagram")
        contenido.nueva_version(self.cx, p, {"copy": "Cierras el mes. " * 200, "cta": "Pide una demostración"},
                                capacidades=["CU-LIB-05"])
        informe = contenido.auditar_pieza(self.cx, self.cfg.raiz, p)
        self.assertIn("longitud", {h.regla for h in informe.bloqueantes})

    def test_los_textos_anidados_de_una_plantilla_tambien_se_auditan(self):
        p = self.pieza()
        contenido.nueva_version(self.cx, p, {"copy": "Mira esto", "cta": "Pide una demostración",
                                              "laminas": [{"titulo": "Paso 1"}, {"titulo": "Desde S/ 29"}]})
        self.assertIn("precio", {h.regla for h in contenido.auditar_pieza(self.cx, self.cfg.raiz, p).bloqueantes})

    def test_calendario_ordenado_por_fecha(self):
        self.pieza()
        filas = contenido.calendario(self.cx, "2026-10-01", "2026-10-31")
        self.assertEqual(len(filas), 1)


if __name__ == "__main__":
    unittest.main()
