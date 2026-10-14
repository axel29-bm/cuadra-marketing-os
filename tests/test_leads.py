"""Leads: sin duplicados, con consentimiento probado, baja respetada y supresión real."""

import csv

from mos import leads
from mos.leads import ErrorLead
from tests.base import ConBase

FIN = "Avisarte de la beta privada de Cuadra"


class Leads(ConBase):
    def nuevo(self, **kw):
        datos = dict(fuente="landing", email="Ana@Ejemplo.pe", consentimiento=True, finalidad=FIN,
                     consentimiento_version="aviso-v1")
        datos.update(kw)
        return leads.registrar(self.cx, "cuadra", **datos)

    def test_registrar_dos_veces_no_duplica(self):
        uid1, nuevo1 = self.nuevo()
        uid2, nuevo2 = self.nuevo(email="ana@ejemplo.pe ", telefono="987654321")
        self.assertEqual((uid1, nuevo1, nuevo2), (uid2, True, False))
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM lead").fetchone()[0], 1)
        self.assertEqual(self.cx.execute("SELECT telefono FROM lead").fetchone()[0], "+51987654321")

    def test_el_mismo_telefono_con_otro_formato_es_la_misma_persona(self):
        self.nuevo(email=None, telefono="+51 987 654 321")
        _, nuevo = self.nuevo(email=None, telefono="987-654-321")
        self.assertFalse(nuevo)

    def test_sin_contacto_o_sin_finalidad_no_entra(self):
        with self.assertRaises(ErrorLead):
            self.nuevo(email=None)
        with self.assertRaises(ErrorLead):
            self.nuevo(finalidad="")

    def test_la_publicidad_necesita_su_propio_consentimiento(self):
        with self.assertRaises(ErrorLead):
            self.nuevo(consentimiento=False, consentimiento_publicidad=True, finalidad="")
        self.nuevo()
        self.assertEqual(self.cx.execute("SELECT consentimiento_publicidad FROM lead").fetchone()[0], 0)

    def test_la_baja_se_respeta_aunque_se_reimporte_una_lista(self):
        self.nuevo(consentimiento_publicidad=True)
        leads.dar_de_baja(self.cx, "ana@ejemplo.pe")
        self.nuevo(consentimiento_publicidad=True)
        fila = self.cx.execute("SELECT estado, consentimiento_publicidad FROM lead").fetchone()
        self.assertEqual((fila["estado"], fila["consentimiento_publicidad"]), ("NO_CONTACTAR", 0))

    def test_suprimir_borra_los_datos_y_el_historial(self):
        self.nuevo()
        self.assertEqual(leads.suprimir(self.cx, "ana@ejemplo.pe"), 1)
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM lead").fetchone()[0], 0)
        self.assertEqual(self.cx.execute("SELECT COUNT(*) FROM lead_evento").fetchone()[0], 0)
        auditoria = " ".join(r[0] for r in self.cx.execute("SELECT detalle FROM auditoria"))
        self.assertNotIn("ana@ejemplo.pe", auditoria)

    def test_el_titular_puede_pedir_todos_sus_datos(self):
        self.nuevo(nombre="Ana")
        datos = leads.exportar_titular(self.cx, "ana@ejemplo.pe")
        self.assertEqual(datos["registros"][0]["datos"]["nombre"], "Ana")
        self.assertTrue(datos["registros"][0]["historial"])

    def test_seguimientos_vencidos_sin_datos_de_contacto(self):
        uid, _ = self.nuevo()
        leads.actualizar(self.cx, uid, seguimiento_en="2026-10-01", proxima_accion="Escribir")
        s = leads.seguimientos(self.cx, "2026-10-14")
        self.assertEqual(len(s), 1)
        self.assertNotIn("email", s[0])

    def test_importar_csv_salta_a_quien_no_dio_consentimiento(self):
        ruta = self.tmp / "form.csv"
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nombre", "email", "telefono", "consentimiento", "publicidad"])
            w.writerow(["Ana", "ana@ejemplo.pe", "", "Sí", "no"])
            w.writerow(["Beto", "beto@ejemplo.pe", "", "", ""])
            w.writerow(["Ana otra vez", "ANA@ejemplo.pe", "", "si", "si"])
            w.writerow(["Malo", "no-es-correo", "", "si", ""])
        conteo = leads.importar_csv(self.cx, ruta, "cuadra", "tally", finalidad=FIN, consentimiento_version="aviso-v1")
        self.assertEqual(conteo, {"nuevos": 1, "actualizados": 1, "sin_consentimiento": 1, "invalidos": 1})

    def test_exportar_csv(self):
        self.nuevo()
        self.assertEqual(leads.exportar_csv(self.cx, self.tmp / "s" / "leads.csv"), 1)
