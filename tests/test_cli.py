"""La línea de comandos de punta a punta, como la usaría Didi."""

import io
import json
from contextlib import redirect_stdout, redirect_stderr

from mos.__main__ import main
from tests.base import ConBase


class LineaDeComandos(ConBase):
    def correr(self, *args):
        salida, errores = io.StringIO(), io.StringIO()
        with redirect_stdout(salida), redirect_stderr(errores):
            codigo = main(["--espacio", str(self.tmp), *args])
        return codigo, salida.getvalue() + errores.getvalue()

    def test_recorrido_completo_de_una_pieza(self):
        self.assertEqual(self.correr("iniciar")[0], 0)
        codigo, out = self.correr("pieza", "crear", "--formato", "post", "--canal", "facebook", "--titulo", "Cierre",
                                  "--tipo", "CAPTACION", "--fecha", "2026-10-20")
        self.assertEqual(codigo, 0, out)
        archivo = self.tmp / "contenido.json"
        archivo.write_text(json.dumps({"contenido": {"copy": "Cierras el mes y queda cerrado de verdad.",
                                                     "cta": "Pide una demostración"}, "capacidades": ["CU-LIB-05"]}),
                           encoding="utf-8")
        self.assertEqual(self.correr("pieza", "version", "P-0001", "--archivo", str(archivo))[0], 0)
        self.assertEqual(self.correr("pieza", "auditar", "P-0001")[0], 0)
        self.assertEqual(self.correr("pieza", "aprobar", "P-0001")[0], 0)
        codigo, out = self.correr("publicacion", "preparar", "--pieza", "P-0001")
        self.assertEqual(codigo, 0, out)
        self.assertEqual(self.correr("publicacion", "confirmar", "1", "--url", "https://facebook.com/x/1")[0], 0)
        self.assertIn("PUBLICADA", self.correr("publicacion", "listar")[1])

    def test_un_error_se_explica_y_queda_registrado(self):
        codigo, out = self.correr("pieza", "aprobar", "P-9999")
        self.assertEqual(codigo, 1)
        self.assertIn("No existe la pieza", out)
        self.assertIn("ErrorContenido", self.correr("errores")[1])

    def test_auditar_un_texto_suelto(self):
        codigo, out = self.correr("auditar", "--texto", "Cuadra desde S/ 49", "--cta", "Pide una demostración")
        self.assertEqual(codigo, 2)
        self.assertIn("precio", out.lower())

    def test_tarea_asistida_de_punta_a_punta(self):
        entradas = json.dumps({"pieza": "Post", "brief": "Importar compras", "canal": "facebook", "tipo_afirmacion": "CAPTACION"})
        self.correr("tarea", "crear", "--agente", "copywriter", "--objetivo", "Copys", "--entradas", entradas)
        codigo, out = self.correr("tarea", "preparar", "T-0001")
        self.assertEqual(codigo, 0, out)
        (self.tmp / "tareas" / "T-0001" / "resultado.json").write_text(json.dumps({"variantes": [
            {"gancho": "Mira antes de guardar", "copy": "Ves fila por fila qué va a pasar antes de guardar.",
             "cta": "Quiero participar en la beta", "capacidades": ["CU-REG-03"]},
            {"gancho": "Deshaz la importación entera", "copy": "Si te equivocas, deshaces la importación entera.",
             "cta": "Pide una demostración", "capacidades": ["CU-REG-03"]}]}), encoding="utf-8")
        codigo, out = self.correr("tarea", "completar", "T-0001")
        self.assertEqual(codigo, 0, out)
        self.assertIn("completada", out)

    def test_lead_con_consentimiento_y_baja(self):
        self.correr("lead", "registrar", "--email", "ana@ejemplo.pe", "--consentimiento", "--finalidad", "Beta")
        self.assertEqual(self.correr("lead", "baja", "--contacto", "ana@ejemplo.pe")[0], 0)
        self.assertRegex(self.correr("lead", "embudo")[1], r"NO_CONTACTAR\s+1")
