"""Guardia de importaciones de caja blanca (DecisionTree_Modeler, Fase 0).

Bloquea en tiempo de importacion cualquier libreria de "caja negra"
(sklearn / scikit-learn / statsmodels / xgboost / lightgbm / catboost)
mediante un meta-path finder instalado en sys.meta_path, de modo que la
proteccion aplica incluso a imports dinamicos (importlib.import_module,
__import__) y a submodulos (p. ej. sklearn.tree).

Politica del proyecto: matematica auditable exclusivamente con
numpy / pandas / scipy.stats. Formulas explicitas en el codigo.
"""

from __future__ import annotations

import importlib.abc
import sys
from types import ModuleType
from typing import Sequence

_BANNED_ROOTS: frozenset[str] = frozenset(
    {
        "sklearn",
        "scikit-learn",   # nombre de distribucion pip (no importable; defensa)
        "scikit_learn",   # alias defensivo
        "statsmodels",
        "xgboost",
        "lightgbm",
        "catboost",
    }
)

_BLOCK_MESSAGE: str = (
    "Librería prohibida por restricción de caja blanca. "
    "Use numpy/pandas/scipy exclusivamente."
)


class _BlackBoxBlocker(importlib.abc.MetaPathFinder):
    """Meta-path finder que rechaza cualquier modulo cuya raiz este vetada."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> None:
        root = fullname.split(".", 1)[0]
        if root in _BANNED_ROOTS:
            raise ImportError(
                f"{_BLOCK_MESSAGE} [modulo bloqueado: {fullname!r}]"
            )
        return None  # el resto de imports los resuelven los finders normales


def _purge_banned_cache() -> list[str]:
    """Expulsa de sys.modules cualquier modulo vetado previamente cargado."""
    purged = [
        name
        for name in sys.modules
        if name.split(".", 1)[0] in _BANNED_ROOTS
    ]
    for name in purged:
        del sys.modules[name]
    return purged


def install_import_guard() -> None:
    """Instala el guardia una sola vez al arranque del proceso. Idempotente."""
    if any(isinstance(f, _BlackBoxBlocker) for f in sys.meta_path):
        return
    sys.meta_path.insert(0, _BlackBoxBlocker())
    _purge_banned_cache()


def is_installed() -> bool:
    """True si el guardia esta activo en sys.meta_path (util en pruebas)."""
    return any(isinstance(f, _BlackBoxBlocker) for f in sys.meta_path)
