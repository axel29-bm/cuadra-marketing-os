"""El panel web local: seguridad básica, que cada página se muestre y el recorrido de una pieza con clics."""

from __future__ import annotations

import io
import re
from urllib.parse import urlencode, urlsplit

from mos import leads
from mos.web import app as web
from tests.base import ConBase


class Cliente:
    """Llama a la aplicación WSGI sin abrir un puerto."""

    def __init__(self, aplicacion):
        self.app = aplicacion

    def pedir(self, metodo: str, ruta: str, datos: dict | None = None, host: str = "127.0.0.1:8765",
              token: bool = True) -> tuple[int, dict, str]:
        partes = urlsplit(ruta)
        cuerpo = b""
        if metodo == "POST":
            datos = dict(datos or {})
            if token:
                datos.setdefault("_token", web.TOKEN)
            cuerpo = urlencode(datos).encode("utf-8")
        environ = {"REQUEST_METHOD": metodo, "PATH_INFO": partes.path, "QUERY_STRING": partes.query,
                   "HTTP_HOST": host, "CONTENT_LENGTH": str(len(cuerpo)), "wsgi.input": io.BytesIO(cuerpo),
                   "CONTENT_TYPE": "application/x-www-form-urlencoded"}
        estado: dict = {}

        def start_response(status, cabeceras):
            estado["codigo"] = int(status.split()[0])
            estado["cabeceras"] = dict(cabeceras)

        salida = b"".join(self.app(environ, start_response))
        return estado["codigo"], estado["cabeceras"], salida.decode("utf-8", "replace")

    def get(self, ruta: str, **kw):
        return self.pedir("GET", ruta, **kw)

    def post(self, ruta: str, datos: dict | None = None, **kw):
        return self.pedir("POST", ruta, datos, **kw)


class PanelWeb(ConBase):
    def setUp(self) -> None:
        super().setUp()
        self.web = Cliente(web.crear_app(self.cfg))

    def test_solo_atiende_desde_esta_pc(self):
        codigo, _, cuerpo = self.web.get("/", host="atacante.example:8765")
        self.assertEqual(codigo, 403)
        self.assertIn("Solo se atiende desde esta PC", cuerpo)
        self.assertEqual(self.web.get("/", host="localhost:8765")[0], 200)

    def test_un_formulario_sin_token_se_rechaza(self):
        codigo, _, _ = self.web.post("/ideas", {"idea_central": "x"}, token=False)
        self.assertEqual(codigo, 403)
        codigo, _, _ = self.web.post("/ideas", {"idea_central": "x", "_token": "otro"}, token=False)
        self.assertEqual(codigo, 403)

    def test_todas_las_paginas_se_muestran(self):
        for ruta in ("/", "/aprobaciones", "/calendario", "/calendario?mes=2026-12", "/tareas", "/ideas", "/campanas",
                     "/piezas", "/publicaciones", "/leads", "/metricas", "/radar", "/productos", "/productos/cuadra",
                     "/productos/cuadra?uso=NO_ANUNCIAR", "/herramientas", "/herramientas?decision=ADOPTAR", "/errores",
                     "/estilo.css"):
            with self.subTest(ruta=ruta):
                codigo, _, cuerpo = self.web.get(ruta)
                self.assertEqual(codigo, 200, cuerpo[:600])
        self.assertEqual(self.web.get("/no-existe")[0], 404)
        self.assertIn("No existe el producto", self.web.get("/productos/otro")[2])

    def test_no_sirve_la_base_ni_archivos_fuera_de_su_carpeta(self):
        self.assertEqual(self.web.get("/archivos/mos.db")[0], 404)
        self.assertEqual(self.web.get("/archivos/../../etc/passwd")[0], 404)
        self.assertEqual(self.web.get("/marcas/cuadra/logo.svg")[0], 200)

    def test_los_textos_se_escapan(self):
        self.web.post("/radar", {"titulo": "<script>alert(1)</script>", "url": "https://www.sunat.gob.pe/x"})
        cuerpo = self.web.get("/radar")[2]
        self.assertNotIn("<script>alert(1)</script>", cuerpo)
        self.assertIn("&lt;script&gt;", cuerpo)

    def test_recorrido_de_una_pieza_con_clics(self):
        codigo, cab, _ = self.web.post("/piezas", {"producto": "cuadra", "titulo": "Cierre de mes", "formato": "post",
                                                   "canal": "facebook", "tipo": "CAPTACION", "fecha": "2026-10-20"})
        self.assertEqual(codigo, 303)
        self.assertTrue(cab["Location"].startswith("/piezas/P-0001"))
        _, cab, _ = self.web.post("/piezas/P-0001/version", {
            "gancho": "¿Cierras el mes y vuelves a abrirlo?", "copy": "Cierras el mes y queda cerrado de verdad.",
            "cta": "Pide una demostración", "capacidades": "CU-LIB-05", "volver": "/piezas/P-0001"})
        self.assertIn("ok=", cab["Location"])
        self.assertIn("/piezas/P-0001", self.web.get("/aprobaciones")[2])
        _, cab, _ = self.web.post("/piezas/P-0001/decidir", {"decision": "APROBADA", "volver": "/piezas/P-0001"})
        self.assertIn("ok=", cab["Location"])
        _, cab, _ = self.web.post("/piezas/P-0001/publicacion", {"canal": "facebook", "fecha": "2026-10-20"})
        self.assertIn("/publicaciones", cab["Location"])
        _, cab, _ = self.web.post("/publicaciones/1/confirmar", {"url": "https://facebook.com/x/1"})
        self.assertIn("ok=", cab["Location"])
        self.assertIn("publicada", self.web.get("/publicaciones")[2])

    def test_una_pieza_con_precio_no_se_puede_aprobar(self):
        self.web.post("/piezas", {"producto": "cuadra", "titulo": "Oferta", "formato": "post", "canal": "facebook",
                                  "tipo": "CAPTACION"})
        _, cab, _ = self.web.post("/piezas/P-0001/version", {"copy": "Solo S/ 99 al mes.", "cta": "Pide una demostración",
                                                             "volver": "/piezas/P-0001"})
        self.assertIn("error=", cab["Location"])
        _, cab, _ = self.web.post("/piezas/P-0001/decidir", {"decision": "APROBADA", "volver": "/piezas/P-0001"})
        self.assertIn("error=", cab["Location"])
        self.assertIn("rechazado", self.web.get("/piezas/P-0001")[2])

    def test_los_contactos_se_muestran_enmascarados(self):
        leads.registrar(self.cx, "cuadra", fuente="whatsapp", email="ana.perez@ejemplo.pe", telefono="987654321",
                        nombre="Ana", consentimiento=True, finalidad="Responder su consulta")
        cuerpo = self.web.get("/leads")[2]
        self.assertNotIn("ana.perez@ejemplo.pe", cuerpo)
        self.assertNotIn("987654321", cuerpo)
        self.assertIn("a***@ejemplo.pe", cuerpo)

    def test_derechos_de_la_persona_desde_el_panel(self):
        leads.registrar(self.cx, "cuadra", fuente="whatsapp", email="ana@ejemplo.pe", consentimiento=True,
                        consentimiento_publicidad=True, finalidad="Responder su consulta")
        _, cab, _ = self.web.post("/leads/derechos", {"contacto": "ana@ejemplo.pe", "accion": "suprimir"})
        self.assertIn("error=", cab["Location"])      # falta confirmar
        _, cab, _ = self.web.post("/leads/derechos", {"contacto": "ana@ejemplo.pe", "accion": "suprimir", "confirmo": "1"})
        self.assertIn("ok=", cab["Location"])
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM lead").fetchone()[0], 0)

    def test_una_idea_se_puntua_y_se_selecciona(self):
        _, cab, _ = self.web.post("/ideas", {"producto": "cuadra", "idea_central": "Checklist de cierre mensual",
                                             "problema": "Se olvidan pasos del cierre", "formato": "carrusel",
                                             "canal": "facebook", "etapa_embudo": "ATENCION", "objetivo": "Guardados",
                                             "relevancia": "5", "atencion": "4", "valor_comercial": "3", "coste": "1",
                                             "esfuerzo": "2"})
        self.assertIn("ok=", cab["Location"])
        cuerpo = self.web.get("/ideas")[2]
        self.assertRegex(cuerpo, r"<b title=\"[^\"]+\">\d+</b>")
        _, cab, _ = self.web.post("/ideas/I-0001/estado", {"estado": "SELECCIONADA", "volver": "/ideas"})
        self.assertIn("ok=", cab["Location"])

    def test_una_tarea_asistida_se_prepara_y_se_completa_pegando_la_respuesta(self):
        _, cab, _ = self.web.post("/tareas", {"agente": "analista", "objetivo": "Resumen de la semana", "entradas": "{}"})
        self.assertEqual(self.web.get(cab["Location"])[0], 200)
        codigo_tarea = re.search(r"T-\d+", cab["Location"]).group(0)
        _, cab, _ = self.web.post(f"/tareas/{codigo_tarea}/ejecutar", {"volver": f"/tareas/{codigo_tarea}"})
        self.assertIn("ok=", cab["Location"])
        estado = self.cx.execute("SELECT estado FROM tarea WHERE codigo = ?", (codigo_tarea,)).fetchone()[0]
        self.assertIn(estado, ("COMPLETADA", "REQUIERE_APROBACION"))

    def test_un_error_inesperado_queda_registrado(self):
        original = web.RUTAS[:]
        try:
            def rompe(req):
                raise RuntimeError("fallo de prueba")
            web.RUTAS.insert(0, ("GET", re.compile("^/rompe$"), rompe))
            codigo, _, cuerpo = self.web.get("/rompe")
            self.assertEqual(codigo, 500)
            self.assertIn("fallo de prueba", cuerpo)
        finally:
            web.RUTAS[:] = original
        self.assertIn("fallo de prueba", self.web.get("/errores")[2])
