"""Contrato y motor de los agentes: nada se completa sin pasar la validación, nada gira en círculos."""

import os
import unittest
from unittest import mock

from mos import config, util
from mos.agentes import motor, proveedores
from mos.agentes.contrato import ErrorContrato, validar_esquema
from mos.agentes.registro import AGENTES
from mos.calidad.auditor import Politica
from tests.base import ConBase

POL = {"politica": Politica.desde_carpeta(config.RAIZ / "productos" / "cuadra"), "plantillas": set()}


class Esquema(unittest.TestCase):
    def test_tipos_listas_y_opcionales(self):
        esquema = {"a": str, "b?": int, "c": [{"d": ("X", "Y")}]}
        self.assertEqual(validar_esquema({"a": "hola", "c": [{"d": "X"}]}, esquema), [])
        problemas = validar_esquema({"a": "", "b": True, "c": []}, esquema)
        self.assertEqual(len(problemas), 3)

    def test_once_agentes_con_contrato_y_los_deterministas_con_ejecutor(self):
        self.assertEqual(len(AGENTES), 11)
        for a in AGENTES.values():
            if a.modo == "DETERMINISTA":
                self.assertIsNotNone(a.ejecutor, a.id)
            else:
                self.assertTrue((config.RAIZ / "prompts" / a.prompt).exists(), f"falta el prompt de {a.id}")


class Motor(ConBase):
    def crear_copy(self, **kw):
        entradas = {"pieza": "Post sobre importar compras", "brief": "Mostrar la vista previa fila por fila",
                    "canal": "facebook", "tipo_afirmacion": "CAPTACION"}
        return motor.crear(self.cx, "copywriter", "Copys para el post de importación", entradas, **kw)

    def test_la_misma_tarea_no_se_crea_dos_veces(self):
        self.assertEqual(self.crear_copy(), self.crear_copy())

    def test_las_entradas_se_validan_al_crear(self):
        with self.assertRaises(ErrorContrato):
            motor.crear(self.cx, "copywriter", "x", {"pieza": "x"})

    def test_una_salida_que_promete_de_mas_no_se_completa_y_falla_al_tercer_intento(self):
        codigo = self.crear_copy()
        malo = {"variantes": [{"gancho": "Descarga Cuadra gratis", "copy": "Desde S/ 49", "cta": "Compra ya",
                               "capacidades": []}] * 2}
        estados = [motor.registrar_resultado(self.cx, codigo, malo, POL) for _ in range(3)]
        self.assertEqual(estados, ["EN_CURSO", "EN_CURSO", "FALLIDA"])
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM registro_error").fetchone()[0], 1)

    def test_una_salida_buena_se_completa(self):
        codigo = self.crear_copy()
        bueno = {"variantes": [
            {"gancho": "Antes de guardar, mira qué va a pasar", "copy": "Pegas tu Excel de compras y ves fila por fila "
             "qué va a pasar antes de guardar. Si te equivocas, deshaces la importación entera.",
             "cta": "Quiero participar en la beta", "capacidades": ["CU-REG-03"]},
            {"gancho": "Tu Excel de compras, sin miedo", "copy": "Ves cada fila antes de guardar y puedes deshacer "
             "la importación entera.", "cta": "Pide una demostración", "capacidades": ["CU-REG-03"]}]}
        self.assertEqual(motor.registrar_resultado(self.cx, codigo, bueno, POL), "COMPLETADA")

    def test_los_roles_sensibles_esperan_aprobacion_humana(self):
        codigo = motor.crear(self.cx, "community", "Responder", {"mensajes": [{"canal": "facebook", "texto": "¿Cuánto cuesta?"}]})
        res = {"respuestas": [{"categoria": "INTERES_COMERCIAL", "borrador": "Todavía no tiene precio. ¿Te aviso cuando abramos la beta?",
                               "accion_sugerida": "Invitar a la lista de espera", "requiere_humano": False}]}
        self.assertEqual(motor.registrar_resultado(self.cx, codigo, res, POL), "REQUIERE_APROBACION")
        motor.aprobar(self.cx, codigo, "Didi")
        self.assertEqual(motor.obtener(self.cx, codigo)["estado"], "COMPLETADA")

    def test_una_consulta_tributaria_siempre_pasa_a_una_persona(self):
        codigo = motor.crear(self.cx, "community", "Responder", {"mensajes": [{"canal": "facebook", "texto": "¿Cómo declaro?"}]})
        res = {"respuestas": [{"categoria": "TRIBUTARIA", "borrador": "Te explico.", "accion_sugerida": "Responder",
                               "requiere_humano": False}]}
        self.assertEqual(motor.registrar_resultado(self.cx, codigo, res, POL), "EN_CURSO")

    def test_la_profundidad_de_subtareas_tiene_tope(self):
        padre = motor.crear(self.cx, "director", "Semana", {"periodo": "2026-W42", "estado_del_sistema": {"n": 0}})
        for i in range(3):
            padre = motor.crear(self.cx, "director", f"Sub {i}", {"periodo": "2026-W42", "estado_del_sistema": {"n": i + 1}},
                                padre=padre)
        with self.assertRaises(motor.ErrorTarea):
            motor.crear(self.cx, "director", "Demasiado hondo", {"periodo": "x", "estado_del_sistema": {"n": 9}}, padre=padre)

    def test_una_tarea_vencida_falla_con_motivo_en_vez_de_quedar_colgada(self):
        codigo = self.crear_copy(vence_en_horas=1)
        self.cx.execute("UPDATE tarea SET vence_en = '2000-01-01T00:00:00Z' WHERE codigo = ?", (codigo,))
        self.assertEqual(motor.revisar_vencidas(self.cx), [codigo])
        self.assertEqual(motor.obtener(self.cx, codigo)["estado"], "FALLIDA")

    def test_el_modo_asistido_prepara_un_prompt_autocontenido(self):
        codigo = self.crear_copy()
        self.assertEqual(motor.ejecutar(self.cx, self.cfg, codigo, POL, "Contexto de prueba"), "PREPARADA")
        prompt = (self.cfg.tareas / codigo / "PROMPT.md").read_text(encoding="utf-8")
        self.assertIn("Contexto de prueba", prompt)
        self.assertIn("Formato de salida", prompt)
        self.assertIn("variantes", prompt)

    def test_el_auditor_determinista_se_ejecuta_sin_ia(self):
        from mos import contenido
        p = contenido.crear_pieza(self.cx, "cuadra", formato="post", canal="facebook", titulo="x", tipo_afirmacion="EDUCATIVA")
        contenido.nueva_version(self.cx, p, {"copy": "Cierras el mes y queda cerrado de verdad."}, capacidades=["CU-LIB-05"])
        codigo = motor.crear(self.cx, "auditor", "Revisar", {"pieza": p})
        self.assertEqual(motor.ejecutar(self.cx, self.cfg, codigo), "COMPLETADA")
        self.assertIn(util.de_json(motor.obtener(self.cx, codigo)["resultado"])["resultado"], ("APROBADO", "CON_OBSERVACIONES"))


class Proveedores(ConBase):
    def test_los_datos_personales_no_salen_de_la_pc(self):
        with self.assertRaises(proveedores.ErrorProveedor):
            proveedores.completar(self.cx, self.cfg, "LOCAL", "Escríbele a ana@correo.pe")

    def test_el_modo_externo_esta_apagado_sin_autorizacion(self):
        with mock.patch.dict(os.environ, {"MOS_IA_CLAVE": "x", "MOS_IA_URL": "https://ejemplo.invalid/v1",
                                          "MOS_IA_MODELO": "m"}):
            cfg = config.cargar(self.tmp)
            with self.assertRaises(proveedores.ErrorProveedor) as e:
                proveedores.completar(self.cx, cfg, "EXTERNO", "hola")
            self.assertIn("no está autorizado", str(e.exception))

    def test_el_tope_diario_detiene_las_llamadas(self):
        codigo = motor.crear(self.cx, "director", "x", {"periodo": "p", "estado_del_sistema": {"a": 1}})
        tid = motor.obtener(self.cx, codigo)["id"]
        for _ in range(self.cfg.ia_limite_diario):
            self.cx.execute("INSERT INTO tarea_evento (tarea_id, en, tipo) VALUES (?, ?, 'LLAMADA_IA')", (tid, util.ahora_utc()))
        with self.assertRaises(proveedores.ErrorProveedor) as e:
            proveedores.completar(self.cx, self.cfg, "LOCAL", "hola")
        self.assertIn("tope diario", str(e.exception))

    def test_extrae_json_de_un_bloque_de_codigo(self):
        self.assertEqual(proveedores.extraer_json('Aquí va:\n```json\n{"a": 1}\n```'), {"a": 1})


if __name__ == "__main__":
    unittest.main()
