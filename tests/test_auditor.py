"""El auditor es la barrera: estas pruebas describen, en palabras de marketing, qué deja pasar y qué no."""

import unittest

from mos import config
from mos.calidad.auditor import Politica, PiezaParaAuditar, auditar

POL = Politica.desde_carpeta(config.RAIZ / "productos" / "cuadra")


def revisar(texto, tipo="CAPTACION", cta="Quiero participar en la beta", capacidades=(), **extra):
    return auditar(PiezaParaAuditar(tipo_afirmacion=tipo, canal="facebook", textos={"copy": texto},
                                    capacidades=list(capacidades), cta=cta, **extra), POL)


def reglas(informe, severidad="BLOQUEANTE"):
    return {h.regla for h in informe.hallazgos if h.severidad == severidad}


class LoQueNoSePuedeDecir(unittest.TestCase):
    def test_un_precio_se_bloquea_mientras_no_este_definido(self):
        self.assertIn("precio", reglas(revisar("Cuadra desde S/ 49 al mes")))

    def test_invitar_a_descargar_se_bloquea_porque_no_hay_instalador(self):
        informe = revisar("Descarga gratis Cuadra hoy")
        self.assertEqual(informe.resultado, "RECHAZADO")
        self.assertIn("afirmacion_no_demostrada", reglas(informe))

    def test_un_llamado_a_comprar_se_bloquea(self):
        self.assertIn("cta", reglas(revisar("Lleva tus empresas en orden", cta="Compra ahora")))

    def test_la_prueba_gratis_no_existe_todavia(self):
        self.assertEqual(revisar("Activa tu prueba gratis de 30 días").resultado, "RECHAZADO")

    def test_cumple_con_sunat_es_una_promesa_sin_firma(self):
        self.assertEqual(revisar("Cuadra cumple con SUNAT").resultado, "RECHAZADO")

    def test_una_pieza_promocional_no_cabe_en_prelanzamiento(self):
        self.assertIn("etapa_comercial", reglas(revisar("Todas tus empresas en una pantalla", tipo="PROMOCIONAL")))

    def test_anunciar_el_envio_del_sire_por_api_se_bloquea(self):
        self.assertIn("capacidad", reglas(revisar("Envía tu SIRE", capacidades=["CU-SIRE-05"])))

    def test_lo_que_solo_se_muestra_en_demo_no_se_promete_en_un_post(self):
        self.assertIn("capacidad", reglas(revisar("Descarga la propuesta del SIRE", capacidades=["CU-SIRE-01"])))

    def test_un_ruc_real_o_un_correo_ajeno_se_bloquean(self):
        self.assertIn("datos_personales", reglas(revisar("Escribe a juan.perez@gmail.com")))
        self.assertIn("datos_personales", reglas(revisar("Empresa con RUC 20123456789")))
        self.assertIn("datos_personales", reglas(revisar("Llámame al 987 654 321")))

    def test_el_ruc_de_la_empresa_de_ejemplo_si_se_puede_mostrar(self):
        self.assertNotIn("datos_personales", reglas(revisar("La empresa de ejemplo tiene RUC 20999999991")))

    def test_una_noticia_sin_fuente_oficial_ni_revision_de_contador_se_bloquea(self):
        informe = revisar("Cambia el cronograma", tipo="NOTICIA", cta="", fuentes=["https://blog.ejemplo.com/x"])
        self.assertTrue({"fuente", "revision_profesional"} <= reglas(informe))

    def test_una_noticia_con_fuente_oficial_fecha_y_revision_pasa(self):
        informe = revisar("La UIT 2026 es S/ 5 500", tipo="NOTICIA", cta="",
                          fuentes=["https://www.sunat.gob.pe/indicestasas/uit.html"],
                          fecha_publicacion_fuente="2025-12-17", revisado_por_contador=True)
        self.assertNotIn("fuente", reglas(informe))
        self.assertNotIn("revision_profesional", reglas(informe))

    def test_un_dominio_que_imita_al_oficial_no_cuenta(self):
        informe = revisar("x", tipo="NOTICIA", cta="", fuentes=["https://sunat.gob.pe.falso.com/x"],
                          fecha_publicacion_fuente="2026-10-01", revisado_por_contador=True)
        self.assertIn("fuente", reglas(informe))


class LoQueSiSePuedeDecir(unittest.TestCase):
    def test_un_mensaje_verificado_y_honesto_pasa(self):
        informe = revisar("Pegas tu Excel de compras y ves fila por fila qué va a pasar antes de guardar. "
                          "Si te equivocas, deshaces la importación entera.", capacidades=["CU-REG-03"])
        self.assertNotEqual(informe.resultado, "RECHAZADO", informe.como_lista())

    def test_contar_el_desarrollo_de_algo_no_disponible_se_permite_con_aviso(self):
        informe = revisar("Estoy trabajando en un asistente que responde con cifras verificadas. Todavía no está disponible.",
                          tipo="DESARROLLO", cta="", capacidades=["CU-IA-01"])
        self.assertNotEqual(informe.resultado, "RECHAZADO", informe.como_lista())

    def test_hablar_de_descargar_la_propuesta_del_sire_no_es_invitar_a_descargar_cuadra(self):
        informe = revisar("Importas la propuesta del SIRE que descargas de SOL.", capacidades=["CU-SIRE-02"])
        self.assertNotIn("afirmacion_no_demostrada", reglas(informe))


class Estilo(unittest.TestCase):
    def test_avisa_frases_de_relleno_y_exageraciones_sin_bloquear(self):
        informe = revisar("En la era digital, el mejor sistema revoluciona tu estudio")
        self.assertTrue({"estilo", "exageracion"} <= reglas(informe, "ADVERTENCIA"))

    def test_avisa_signos_de_apertura_faltantes(self):
        self.assertIn("ortografia", reglas(revisar("Llevas muchas empresas?"), "ADVERTENCIA"))

    def test_el_nombre_mal_escrito_se_avisa_pero_el_verbo_cuadrar_no(self):
        self.assertIn("marca", reglas(revisar("Prueba cuadra en tu estudio"), "ADVERTENCIA"))
        self.assertIn("marca", reglas(revisar("Así funciona CUadra"), "ADVERTENCIA"))
        for texto in ("3 señales de que algo no cuadra en tu serie", "Cuando todo cuadra, cierras tranquilo",
                      "Un formato cuadrado para Instagram"):
            self.assertNotIn("marca", reglas(revisar(texto), "ADVERTENCIA"), texto)

    def test_los_limites_del_canal_bloquean_un_texto_largo(self):
        informe = auditar(PiezaParaAuditar(tipo_afirmacion="EDUCATIVA", canal="instagram", textos={"copy": "a " * 1500},
                                           limites_canal={"copy": 2200}), POL)
        self.assertIn("longitud", reglas(informe))


if __name__ == "__main__":
    unittest.main()
