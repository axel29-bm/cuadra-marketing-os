"""Rutas y ajustes. Nada secreto vive aquí: los secretos solo se leen de variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    raiz: Path
    espacio: Path            # datos vivos: base, salidas, tareas, respaldos (fuera de git)
    modo_ia: str             # ASISTIDO | LOCAL | EXTERNO
    ia_url: str | None
    ia_modelo: str | None
    ia_limite_diario: int
    puerto_web: int

    @property
    def base(self) -> Path:
        return self.espacio / "mos.db"

    @property
    def salidas(self) -> Path:
        return self.espacio / "salidas"

    @property
    def tareas(self) -> Path:
        return self.espacio / "tareas"

    @property
    def respaldos(self) -> Path:
        return self.espacio / "respaldos"

    @property
    def registros(self) -> Path:
        return self.espacio / "registros"


def cargar(espacio: str | os.PathLike | None = None) -> Config:
    esp = Path(espacio or os.environ.get("MOS_ESPACIO") or (RAIZ / "espacio")).resolve()
    modo = os.environ.get("MOS_IA_MODO", "ASISTIDO").upper()
    if modo not in {"ASISTIDO", "LOCAL", "EXTERNO"}:
        raise ValueError(f"MOS_IA_MODO no válido: {modo}. Usa ASISTIDO, LOCAL o EXTERNO.")
    return Config(
        raiz=RAIZ,
        espacio=esp,
        modo_ia=modo,
        ia_url=os.environ.get("MOS_IA_URL"),
        ia_modelo=os.environ.get("MOS_IA_MODELO"),
        ia_limite_diario=int(os.environ.get("MOS_IA_LIMITE_DIARIO", "40")),
        puerto_web=int(os.environ.get("MOS_PUERTO", "8765")),
    )


def clave_ia_externa() -> str | None:
    """La clave del proveedor externo solo existe en el entorno, nunca en archivos del repositorio."""
    return os.environ.get("MOS_IA_CLAVE")
