"""Rutinas: cada paso corre aunque otro falle, el informe no lleva datos de contacto y el panel avisa si dejan de correr."""

from __future__ import annotations

import contextlib
import io
import json
from datetime import date, timedelta
from pathlib import Path

from mos import contenido, leads, metricas, radar_lector, rutina, util
from mos.__main__ import main
from tests.base import ConBase


class Diaria(ConBase):
    def lead(self) -> str:
        uid, _ = leads.registrar(self.cx, "cuadra", fuente="whatsapp", email="contadora@example.com", telefono="999888777",
                                 nombre="Contadora Prueba Uno", consentimiento=True, finalidad="Lista de espera de la beta",
                                 consentimiento_version="2026-10-14", consentimiento_medio="prueba")
        leads.actualizar(self.cx, uid, proxima_accion="Escribirle para la demostración",
                         seguimiento_en=util.hoy_lima().isoformat())
        return uid

    def test_hace_la_copia_lee_el_radar_y_deja_el_informe_sin_datos_de_contacto(self):
        uid = self.lead()
        llamadas = []
        lector = lambda cx: llamadas.append(cx) or [radar_lector.Lectura("sunat-resoluciones", "NUEVAS", 2)]  # noqa: E731
        inf = rutina.diaria(self.cx, self.cfg, lector=lector)
        self.assertEqual((inf.estado, len(llamadas)), ("OK", 1))
        self.assertEqual(len(list(self.cfg.respaldos.glob("mos-*.db"))), 1)
        texto = inf.ruta.read_text(encoding="utf-8")
        for seccion in ("## Copia de seguridad", "## Radar de fuentes oficiales", "## Lo que espera por ti"):
            self.assertIn(seccion, texto)
        self.assertIn("2 novedad(es) nueva(s)", texto)
        self.assertIn(f"Contadora P. · {uid[:8]}", texto)
        self.assertNotIn("contadora@example.com", texto)
        self.assertNotIn("999888777", texto)
        self.assertNotIn("Uno", texto)
        fila = self.cx.execute("SELECT * FROM rutina").fetchone()
        self.assertEqual((fila["tipo"], fila["estado"]), ("DIARIA", "OK"))
        self.assertEqual(Path(self.cfg.espacio / fila["informe"]), inf.ruta)

    def test_si_un_paso_falla_los_demas_siguen_y_queda_el_error(self):
        def roto(cx):
            raise RuntimeError("sin conexión")
        inf = rutina.diaria(self.cx, self.cfg, lector=roto)
        self.assertEqual(inf.estado, "CON_FALLOS")
        self.assertEqual(inf.pasos["respaldo"], "OK")
        self.assertEqual(inf.pasos["pendientes"], "OK")
        self.assertTrue(inf.pasos["radar"].startswith("FALLO"))
        self.assertIn("No se pudo completar", inf.ruta.read_text(encoding="utf-8"))
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM registro_error WHERE modulo = 'rutina'").fetchone()[0], 1)

    def test_sin_radar(self):
        inf = rutina.diaria(self.cx, self.cfg, leer_radar=False)
        self.assertEqual((inf.estado, inf.pasos["radar"]), ("OK", "OMITIDO"))


class Semanal(ConBase):
    def test_separa_lo_medido_de_lo_estimado_y_dice_cuando_no_hay_datos(self):
        hasta = date(2026, 10, 25)
        inf = rutina.semanal(self.cx, self.cfg, hasta=hasta)
        texto = inf.ruta.read_text(encoding="utf-8")
        self.assertIn("Sin métricas registradas esta semana", texto)
        self.assertIn("Ningún interesado nuevo esta semana", texto)
        self.assertIn("La rutina diaria corrió 0 de 7 días", texto)
        contenido.crear_campana(self.cx, "cuadra", slug="prueba", nombre="Prueba", objetivo="Medir", hipotesis="Ninguna",
                                oferta="Ninguna", cta="Escríbenos", metrica_exito="alcance")
        metricas.registrar(self.cx, "alcance", 1500, "2026-10-22", naturaleza="MEDIDA", campana="prueba")
        metricas.registrar(self.cx, "alcance", 900, "2026-10-23", naturaleza="ESTIMADA", campana="prueba")
        texto = rutina.semanal(self.cx, self.cfg, hasta=hasta).ruta.read_text(encoding="utf-8")
        self.assertIn("**Medido (lo que dice cada red)**", texto)
        self.assertIn("**Estimado (no es un dato medido)**", texto)
        self.assertIn("Resumen semanal del 19/10 al 25/10/2026", texto)


class Mensual(ConBase):
    def test_revisa_experimentos_piezas_para_reutilizar_y_herramientas_viejas(self):
        from pathlib import Path
        from mos import campanas, experimentos
        carpeta = Path(__file__).resolve().parent.parent / "campanas" / "lista-espera-beta"
        campanas.cargar(self.cx, self.cfg, carpeta)
        experimentos.cargar(self.cx, carpeta)
        experimentos.cancelar(self.cx, "EXP-05", "La landing no se publicó")
        inf = rutina.mensual(self.cx, self.cfg, mes="2026-10")
        texto = inf.ruta.read_text(encoding="utf-8")
        self.assertEqual((inf.estado, inf.fecha), ("OK", "2026-10-31"))
        self.assertIn("Revisión mensual de 10/2026", texto)
        self.assertIn("Sin datos medidos todavía", texto)
        self.assertIn("| Cancelado: La landing no se publicó |", texto)
        self.assertIn("Ninguna pieza con interesados o guardados medidos", texto)
        self.assertIn("Todas las herramientas en uso se verificaron", texto)
        texto = rutina.mensual(self.cx, self.cfg, mes="2027-02").ruta.read_text(encoding="utf-8")
        self.assertIn("Los planes gratuitos cambian", texto)
        self.assertEqual(rutina.ultimas(self.cx)["MENSUAL"]["fecha"], "2027-02-28")


class Alertas(ConBase):
    def test_avisa_si_la_rutina_dejo_de_correr_o_fallo(self):
        self.assertEqual(rutina.alertas(self.cx), [])   # nunca se usó: no molesta
        rutina.diaria(self.cx, self.cfg, leer_radar=False)
        hoy = util.hoy_lima()
        self.assertEqual(rutina.alertas(self.cx, hoy), [])
        avisos = rutina.alertas(self.cx, hoy + timedelta(days=4))
        self.assertEqual(len(avisos), 1)
        self.assertIn("no corre desde hace 4 días", avisos[0])
        self.cx.execute("UPDATE rutina SET estado = 'CON_FALLOS', detalle = ?", (json.dumps({"respaldo": "OK", "radar": "FALLO: x"}),))
        self.assertIn("tuvo fallos en: radar", rutina.alertas(self.cx, hoy)[0])

    def test_programar_deja_los_scripts_y_solo_muestra_los_comandos(self):
        comandos = rutina.preparar_programacion(self.cfg)
        self.assertTrue(comandos[0].startswith('schtasks /Create /TN "Marketing OS diaria" /SC DAILY'))
        self.assertIn("/D SUN", comandos[1])
        self.assertIn("/SC MONTHLY /D 1", comandos[2])
        self.assertEqual([c.split('"')[1] for c in comandos[3:]],
                         ["Marketing OS diaria", "Marketing OS semanal", "Marketing OS mensual"])
        self.assertTrue(all(c.startswith("schtasks /Delete") for c in comandos[3:]))
        script = (self.cfg.espacio / "rutina-diaria.cmd").read_text(encoding="utf-8")
        self.assertIn("-m mos rutina diaria", script)
        self.assertIn(f'set "MOS_ESPACIO={self.cfg.espacio}"', script)
        self.assertIn(str(self.cfg.espacio / "rutina-diaria.cmd"), comandos[0])


class LineaDeComandos(ConBase):
    def test_rutina_y_radar_por_consola(self):
        espacio = str(self.tmp)
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            self.assertEqual(main(["--espacio", espacio, "rutina", "diaria", "--sin-radar"]), 0)
            self.assertEqual(main(["--espacio", espacio, "rutina", "estado"]), 0)
            self.assertEqual(main(["--espacio", espacio, "radar", "pendientes"]), 0)
            self.assertEqual(main(["--espacio", espacio, "radar", "fuentes"]), 0)
            self.assertEqual(main(["--espacio", espacio, "rutina", "programar"]), 0)
        texto = salida.getvalue()
        self.assertIn("todo bien", texto)
        self.assertIn("elperuano-normas-sitemap", texto)
        self.assertIn("schtasks /Create", texto)
