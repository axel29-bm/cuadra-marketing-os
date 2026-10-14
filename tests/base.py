"""Base común de las pruebas: cada prueba usa su propio espacio temporal y la configuración real del repositorio."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from mos import config, db, semillas


class ConBase(unittest.TestCase):
    """Crea una base nueva, la migra y carga las semillas reales (productos, matriz, fuentes, herramientas)."""

    cargar_semillas = True

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mos-prueba-"))
        self.cfg = config.cargar(self.tmp)
        self.cx = db.conectar(self.cfg.base)
        db.migrar(self.cx)
        if self.cargar_semillas:
            semillas.cargar_todo(self.cx, config.RAIZ)

    def tearDown(self) -> None:
        self.cx.close()
        shutil.rmtree(self.tmp, ignore_errors=True)
