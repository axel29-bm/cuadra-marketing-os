import sqlite3
import unittest

from mos import db, semillas, config
from tests.base import ConBase


class MigracionesYRespaldo(ConBase):
    cargar_semillas = False

    def test_la_migracion_es_idempotente_y_deja_la_version(self):
        self.assertEqual(db.migrar(self.cx), [])
        self.assertEqual(self.cx.execute("PRAGMA user_version").fetchone()[0], db.version_esquema())

    def test_todas_las_tablas_son_strict(self):
        filas = self.cx.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'").fetchall()
        self.assertGreaterEqual(len(filas), 28)
        for f in filas:
            self.assertIn("STRICT", f["sql"], f["name"])

    def test_la_base_usa_wal_y_claves_foraneas(self):
        self.assertEqual(self.cx.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.cx.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_una_base_de_la_version_2_sube_sin_perder_las_rutinas(self):
        from unittest import mock
        cx = db.conectar(self.tmp / "v2.db")
        hasta_v2 = [m for m in db._migraciones() if m[0] <= 2]
        with mock.patch.object(db, "_migraciones", return_value=hasta_v2):
            db.migrar(cx)
        cx.execute("""INSERT INTO rutina (tipo, fecha, iniciada_en, terminada_en, estado)
                      VALUES ('DIARIA', '2026-10-14', '2026-10-14T13:00:00Z', '2026-10-14T13:01:00Z', 'OK')""")
        with self.assertRaises(sqlite3.IntegrityError):
            cx.execute("INSERT INTO rutina (tipo, fecha, iniciada_en) VALUES ('MENSUAL', '2026-10-31', 'x')")
        self.assertEqual(db.migrar(cx), ["0003_experimentos.sql", "0004_rutina_mensual.sql"])
        self.assertEqual(cx.execute("SELECT tipo, estado FROM rutina").fetchall()[0][:], ("DIARIA", "OK"))
        cx.execute("INSERT INTO rutina (tipo, fecha, iniciada_en) VALUES ('MENSUAL', '2026-10-31', 'x')")
        self.assertEqual(cx.execute("PRAGMA foreign_key_check").fetchall(), [])
        cx.close()

    def test_una_base_mas_nueva_que_el_programa_no_se_abre(self):
        self.cx.execute(f"PRAGMA user_version = {db.version_esquema() + 1}")
        with self.assertRaises(db.BaseMasNueva):
            db.migrar(self.cx)

    def test_el_respaldo_queda_verificado_y_se_conservan_los_ultimos(self):
        for _ in range(3):
            ruta = db.respaldar(self.cx, self.cfg.respaldos, conservar=2)
            self.assertTrue(ruta.exists())
        self.assertEqual(len(list(self.cfg.respaldos.glob("mos-*.db"))), 2)
        copia = sqlite3.connect(ruta)
        self.assertEqual(copia.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        copia.close()

    def test_una_transaccion_fallida_no_deja_rastro(self):
        with self.assertRaises(RuntimeError):
            with db.transaccion(self.cx):
                self.cx.execute("INSERT INTO ajuste (clave, valor) VALUES ('x', '1')")
                raise RuntimeError("falla a mitad")
        self.assertIsNone(self.cx.execute("SELECT 1 FROM ajuste WHERE clave = 'x'").fetchone())


class Semillas(ConBase):
    def test_cargar_dos_veces_no_duplica(self):
        antes = {t: self.cx.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ("producto", "capacidad", "fuente", "marca", "audiencia", "prohibicion", "herramienta")}
        semillas.cargar_todo(self.cx, config.RAIZ)
        despues = {t: self.cx.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in antes}
        self.assertEqual(antes, despues)

    def test_cuadra_esta_en_prelanzamiento_sin_precio(self):
        p = self.cx.execute("SELECT * FROM producto WHERE slug = 'cuadra'").fetchone()
        self.assertEqual(p["etapa_comercial"], "PRELANZAMIENTO")
        self.assertEqual(p["precio_definido"], 0)
        self.assertEqual(p["disponible_al_publico"], 0)

    def test_cada_capacidad_tiene_evidencia(self):
        for c in self.cx.execute("SELECT codigo, evidencia FROM capacidad"):
            self.assertTrue(c["evidencia"].strip(), c["codigo"])

    def test_una_noticia_no_puede_quedar_verificada_sin_fuente_primaria(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.cx.execute("""INSERT INTO radar_item (titulo, url, estado_verificacion, es_fuente_primaria, detectado_en)
                               VALUES ('x', 'https://ejemplo.pe/x', 'VERIFICADA', 0, '2026-10-14T00:00:00Z')""")


if __name__ == "__main__":
    unittest.main()
