"""La landing: textos auditados, nada para publicar mientras falte algo legal, y el formulario guarda el consentimiento."""

from __future__ import annotations

import copy
import io
import json
import re
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock
from wsgiref.util import setup_testing_defaults

from mos import config, leads, sitio
from tests.base import ConBase

RAIZ = config.RAIZ

try:
    import jinja2  # noqa: F401
    JINJA = True
except ImportError:
    JINJA = False

BUENO = {"nombre": "Contadora de Prueba", "email": "Prueba@Example.com", "empresas": "35", "problema": "El SIRE",
         "consentimiento": True, "publicidad": False, "demo": True, "aviso_version": "2026-10-14",
         "origen": {"utm_source": "facebook"}, "sitio_web": ""}


def completo(datos: dict) -> dict:
    """La configuración como quedaría con todo lo legal resuelto."""
    d = copy.deepcopy(datos)
    d["responsable"] |= {"nombre": "Nombre", "documento": "DNI 00000000", "domicilio": "Lima", "correo_derechos": "a@b.pe",
                         "registro_banco": "RNPDP-0000", "flujo_comunicado": True}
    d["publicacion"] |= {"url": "https://cuadra-beta.pages.dev", "receptor": "https://lista.example.workers.dev/api/lista",
                         "aviso_validado": True, "aviso_version": "2026-11-01"}
    return d


class Textos(unittest.TestCase):
    def test_la_landing_real_pasa_el_auditor_sin_bloqueos(self):
        for seccion, informe in sitio.revisar(RAIZ, sitio.leer(RAIZ)):
            with self.subTest(seccion=seccion):
                self.assertEqual(informe.bloqueantes, [], [h.mensaje for h in informe.bloqueantes])

    def test_una_promesa_de_mas_frena_la_landing(self):
        datos = sitio.leer(RAIZ)
        datos["pagina"]["subtitulo"] = "Descárgalo y empieza tu prueba gratis hoy."
        bloqueadas = [s for s, i in sitio.revisar(RAIZ, datos) if i.bloqueantes]
        self.assertEqual(bloqueadas, ["pagina"])

    def test_solo_se_citan_capacidades_que_se_pueden_afirmar(self):
        datos = sitio.leer(RAIZ)
        datos["ya_hace"]["capacidades"].append({"codigo": "CU-SIRE-05", "icono": "check"})
        with self.assertRaisesRegex(sitio.ErrorSitio, "no se puede anunciar"):
            sitio.revisar(RAIZ, datos)
        datos = sitio.leer(RAIZ)
        datos["ya_hace"]["capacidades"].append({"codigo": "CU-SIRE-03", "icono": "check"})
        with self.assertRaisesRegex(sitio.ErrorSitio, "matices"):
            sitio.revisar(RAIZ, datos)


class Publicacion(unittest.TestCase):
    def test_mientras_falte_lo_legal_no_se_puede_publicar(self):
        faltan = sitio.pendientes_para_publicar(sitio.leer(RAIZ))
        self.assertTrue(any("responsable" in f for f in faltan))
        self.assertTrue(any("abogado" in f for f in faltan))
        self.assertTrue(any("transfronterizo" in f for f in faltan))
        self.assertEqual(sitio.pendientes_para_publicar(completo(sitio.leer(RAIZ))), [])

    @unittest.skipUnless(JINJA, "Falta jinja2")
    def test_construir_publicable_se_niega_con_pendientes(self):
        with self.assertRaisesRegex(sitio.ErrorSitio, "Todavía no se puede publicar"):
            sitio.construir(RAIZ, publicable=True)


@unittest.skipUnless(JINJA, "Falta jinja2")
class Construccion(ConBase):
    def test_borrador_sin_formulario_y_sin_nada_de_internet(self):
        res = sitio.construir(RAIZ, self.tmp / "dist")
        nombres = {p.name for p in res.archivos}
        self.assertLessEqual({"index.html", "privacidad.html", "trivia.html", "robots.txt", "_headers", "logo.svg",
                              "Geist-Variable.woff2"}, nombres)
        self.assertNotIn("lista.js", nombres)   # sin receptor publicado no hay formulario
        index = (self.tmp / "dist" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Borrador sin publicar", index)
        self.assertIn('name="robots" content="noindex"', index)
        self.assertIn("Content-Security-Policy", index)
        self.assertIn("Escríbenos «BETA» por mensaje", index)
        self.assertNotRegex(index, r"(src|href)=\"https?://")
        self.assertIn("Disallow: /", (self.tmp / "dist" / "robots.txt").read_text(encoding="utf-8"))
        privacidad = (self.tmp / "dist" / "privacidad.html").read_text(encoding="utf-8")
        self.assertIn('class="pendiente"', privacidad)
        # cada capacidad de «lo que ya hace» aparece con la frase exacta de la matriz
        self.assertIn("Cierras el mes y queda cerrado de verdad.", index)

    def test_con_receptor_el_formulario_tiene_tres_casillas_sin_marcar(self):
        sitio.construir(RAIZ, self.tmp / "dist", receptor="/api/lista")
        index = (self.tmp / "dist" / "index.html").read_text(encoding="utf-8")
        casillas = re.findall(r'<input type="checkbox" name="(\w+)"([^>]*)>', index)
        self.assertEqual([n for n, _ in casillas], ["demo", "consentimiento", "publicidad"])
        self.assertTrue(all("checked" not in resto for _, resto in casillas))
        self.assertIn('data-version="2026-10-14-borrador"', index)
        self.assertTrue((self.tmp / "dist" / "lista.js").exists())

    def test_lista_para_publicar_no_lleva_aviso_de_borrador(self):
        with mock.patch.object(sitio, "leer", return_value=completo(sitio.leer(RAIZ))):
            res = sitio.construir(RAIZ, self.tmp / "dist", publicable=True)
        index = (self.tmp / "dist" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(res.pendientes, [])
        self.assertNotIn("Borrador sin publicar", index)
        self.assertIn("connect-src 'self' https://lista.example.workers.dev", index)
        self.assertNotIn("[COMPLETAR", (self.tmp / "dist" / "privacidad.html").read_text(encoding="utf-8"))


class Envio(unittest.TestCase):
    def test_reglas_del_formulario(self):
        self.assertEqual(sitio.validar_envio(None)[0], "DATOS_INCOMPLETOS")
        self.assertEqual(sitio.validar_envio(BUENO | {"sitio_web": "spam"})[0], "TRAMPA")
        self.assertEqual(sitio.validar_envio(BUENO | {"email": "sin-arroba"})[0], "CORREO_INVALIDO")
        self.assertEqual(sitio.validar_envio(BUENO | {"consentimiento": "true"})[0], "SIN_CONSENTIMIENTO")
        self.assertEqual(sitio.validar_envio(BUENO | {"aviso_version": ""})[0], "DATOS_INCOMPLETOS")
        codigo, limpio = sitio.validar_envio(BUENO | {"empresas": "9999", "nombre": "x" * 200})
        self.assertIsNone(codigo)
        self.assertEqual((limpio["empresas"], len(limpio["nombre"]), limpio["email"]), (None, 80, "prueba@example.com"))


def llamar(app, metodo: str, ruta: str, cuerpo: dict | None = None, host: str = "127.0.0.1:8766"):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else b""
    environ = {"REQUEST_METHOD": metodo, "PATH_INFO": ruta, "HTTP_HOST": host, "CONTENT_LENGTH": str(len(datos)),
               "wsgi.input": io.BytesIO(datos)}
    setup_testing_defaults(environ)
    estado = {}
    cuerpo_respuesta = b"".join(app(environ, lambda s, h: estado.update(s=s)))
    return estado["s"], cuerpo_respuesta


class ReceptorLocal(ConBase):
    def setUp(self) -> None:
        super().setUp()
        (self.tmp / "web").mkdir()
        (self.tmp / "web" / "index.html").write_text("<h1>hola</h1>", encoding="utf-8")
        self.app = sitio.app_local(self.cfg, self.tmp / "web")

    def lead(self):
        return self.cx.execute("SELECT * FROM lead").fetchone()

    def test_una_inscripcion_llega_al_panel_con_su_consentimiento(self):
        estado, cuerpo = llamar(self.app, "POST", "/api/lista", BUENO)
        self.assertEqual((estado, json.loads(cuerpo)), ("200 OK", {"ok": True}))
        lead = self.lead()
        self.assertEqual((lead["email"], lead["consentimiento"], lead["consentimiento_publicidad"]), ("prueba@example.com", 1, 0))
        self.assertEqual(lead["consentimiento_version"], "2026-10-14")
        self.assertIn("utm_source=facebook", lead["consentimiento_medio"])
        self.assertIn("demostración", lead["proxima_accion"])
        llamar(self.app, "POST", "/api/lista", BUENO)
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM lead").fetchone()[0], 1)

    def test_sin_consentimiento_o_con_trampa_no_se_guarda(self):
        estado, cuerpo = llamar(self.app, "POST", "/api/lista", BUENO | {"consentimiento": False})
        self.assertEqual((estado, json.loads(cuerpo)["codigo"]), ("400 Bad Request", "SIN_CONSENTIMIENTO"))
        estado, _ = llamar(self.app, "POST", "/api/lista", BUENO | {"sitio_web": "http://spam"})
        self.assertEqual(estado, "200 OK")
        self.assertIsNone(self.lead())

    def test_solo_en_esta_pc_y_solo_su_carpeta(self):
        self.assertEqual(llamar(self.app, "GET", "/", host="otro.example")[0], "403 Forbidden")
        self.assertEqual(llamar(self.app, "GET", "/")[1], b"<h1>hola</h1>")
        self.assertEqual(llamar(self.app, "GET", "/../../etc/passwd")[0], "404 Not Found")


CABECERA_CSV = "email,nombre,problema,empresas,consentimiento,publicidad,demo,aviso_version,origen,creado_en\r\n"


class ImportarRemoto(ConBase):
    """Un receptor falso en 127.0.0.1 que responde como el de Cloudflare."""

    def importar(self, csv_remoto: str, clave: str = "clave-larga") -> tuple[dict, list[str]]:
        borrados = []

        class Falso(BaseHTTPRequestHandler):
            def do_GET(self):
                ok = self.headers.get("Authorization") == "Bearer clave-larga"
                self.send_response(200 if ok else 401)
                self.end_headers()
                self.wfile.write(csv_remoto.encode() if ok else b"")

            def do_POST(self):
                cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                borrados.extend(cuerpo["emails"])
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "borrados": len(cuerpo["emails"])}).encode())

            def log_message(self, *a):
                pass

        servidor = HTTPServer(("127.0.0.1", 0), Falso)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            conteo = sitio.importar_remoto(self.cx, self.cfg, f"http://127.0.0.1:{servidor.server_port}/api/lista", clave)
        finally:
            servidor.shutdown()
            servidor.server_close()
        return conteo, borrados

    def test_sin_clave_no_pide_nada(self):
        with self.assertRaisesRegex(sitio.ErrorSitio, "MOS_CLAVE_LISTA"):
            self.importar(CABECERA_CSV, clave="")

    def test_trae_las_inscripciones_y_las_borra_del_servidor(self):
        conteo, borrados = self.importar(
            CABECERA_CSV
            + 'a@example.com,Ana,El cierre,12,1,1,0,2026-11-01,"{""utm_source"":""linkedin""}",2026-11-02T10:00:00.000Z\r\n'
            + "b@example.com,Beto,,,1,0,1,2026-11-01,{},2026-11-02T11:00:00.000Z\r\n")
        self.assertEqual(conteo, {"nuevos": 2, "actualizados": 0, "invalidos": 0, "borrados": 2})
        self.assertEqual(sorted(borrados), ["a@example.com", "b@example.com"])
        ana = self.cx.execute("SELECT * FROM lead WHERE email = 'a@example.com'").fetchone()
        self.assertEqual((ana["consentimiento_publicidad"], ana["consentimiento_en"], ana["fuente"]),
                         (1, "2026-11-02T10:00:00.000Z", "landing"))
        beto = self.cx.execute("SELECT * FROM lead WHERE email = 'b@example.com'").fetchone()
        self.assertIn("demostración", beto["proxima_accion"])
        self.assertEqual(leads.ESTADOS[0], beto["estado"])

    def test_si_una_fila_no_entra_no_se_borra_nada_del_servidor(self):
        conteo, borrados = self.importar(
            CABECERA_CSV
            + "a@example.com,Ana,,,1,0,0,2026-11-01,{},2026-11-02T10:00:00.000Z\r\n"
            + "sin-arroba,Beto,,,1,0,0,2026-11-01,{},2026-11-02T11:00:00.000Z\r\n")
        self.assertEqual(conteo, {"nuevos": 1, "actualizados": 0, "invalidos": 1, "borrados": 0})
        self.assertEqual(borrados, [])


if __name__ == "__main__":
    unittest.main()
