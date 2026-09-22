"""Imputacion anti-leakage (train-only) - (TreeGov, backend_v3, Paso 8).

Regla MRM de oro: la imputacion (media/moda) se calcula EXCLUSIVAMENTE sobre
el fold de entrenamiento y se aplica tal cual a cualquier otro fold (test /
OOS / OOT). Jamas se calculan estadisticos con datos fuera de train.

Politica:
  - PredictorType.CONTINUOUS -> media de train (requiere dtype numerico).
  - PredictorType.ORDINAL    -> media si numerico; moda si simbolico.
  - PredictorType.NOMINAL    -> moda de train. Empate de frecuencia: si las
    etiquetas son ordenables, la menor (determinista); si no lo son, la
    primera por orden de aparicion (recorrido secuencial de s; el orden
    interno de value_counts no es contractual).

Guardas duras:
  - columna de spec ausente en X_train  -> ValueError
  - columna 100% NaN en train           -> ValueError (no hay con que imputar)
  - columna de la spec ausente en X     -> ValueError (en transform)
  - transform() antes de fit()          -> RuntimeError
  - columnas extra en X no presentes en spec: se dejan intactas (sin imputar;
    la decision de bloquear predictores no especificados es del llamador).
"""

from __future__ import annotations

import logging
from collections.abc import Hashable
from dataclasses import dataclass

import pandas as pd

from .log_config import get_logger
from .types import PredictorType

__all__ = ["ImputationSpec", "TrainOnlyImputer"]


@dataclass(frozen=True)
class ImputationSpec:
    """Reglas de imputacion ajustadas SOLO con train (evidencia auditable)."""

    means: dict[str, float]
    modes: dict[str, Hashable]
    fitted_n: int


class TrainOnlyImputer:
    """Aprende medias/modos de train y los aplica sin recalcular."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._log = logger if logger is not None else get_logger("imputation")
        self._spec: ImputationSpec | None = None

    @property
    def spec(self) -> ImputationSpec:
        """Especificacion ajustada (error si no se ha hecho fit)."""
        if self._spec is None:
            raise RuntimeError("TrainOnlyImputer: transform/spec antes de fit()")
        return self._spec

    def fit(
        self, X_train: pd.DataFrame, spec: dict[str, PredictorType]
    ) -> ImputationSpec:
        """Calcula las reglas de imputacion EXCLUSIVAMENTE sobre X_train."""
        means: dict[str, float] = {}
        modes: dict[str, Hashable] = {}
        for col, ptype in spec.items():
            if col not in X_train.columns:
                raise ValueError(f"[imputer] columna ausente en train: {col!r}")
            if not isinstance(ptype, PredictorType):
                raise TypeError(f"[imputer] PredictorType invalido para {col!r}: {ptype!r}")
            s = X_train[col].dropna()
            if len(s) == 0:
                raise ValueError(
                    f"[imputer] columna {col!r} 100% NaN en train: imputacion imposible"
                )
            if ptype == PredictorType.NOMINAL or not pd.api.types.is_numeric_dtype(s):
                modes[col] = self._mode(s)
            else:
                means[col] = float(s.astype(float).mean())
        self._spec = ImputationSpec(
            means=means, modes=modes, fitted_n=int(len(X_train))
        )
        self._log.info(
            "[imputer] fit sobre train (n=%d): %d medias, %d modas",
            len(X_train), len(means), len(modes),
        )
        return self._spec

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Aplica la spec de train a X (train/test/OOS/OOT indistinto)."""
        spec = self.spec  # RuntimeError si no hay fit
        out = X.copy()
        reglas = [(c, v) for c, v in spec.means.items()] + [
            (c, v) for c, v in spec.modes.items()
        ]
        for col, fill in reglas:
            if col not in out.columns:
                raise ValueError(f"[imputer] columna ausente en transform: {col!r}")
            n_na = int(out[col].isna().sum())
            if n_na:
                out[col] = out[col].fillna(fill)
                self._log.debug(
                    "[imputer] %r: %d valores imputados con %r (de train)",
                    col, n_na, fill,
                )
        return out

    @staticmethod
    def _mode(s: pd.Series) -> Hashable:
        """Moda determinista, vectorizada en C (value_counts), O(N).

        Empate: menor etiqueta ordenable; si las etiquetas no son comparables
        entre si, la primera del empate en el orden de value_counts.
        """
        vc = s.value_counts()
        top = vc.max()
        candidatos = vc[vc == top].index.tolist()
        try:
            return sorted(candidatos)[0]
        except TypeError:
            # etiquetas no comparables: primera por orden de aparicion
            # (el orden interno de value_counts no es contractual)
            cand_set = set(candidatos)
            for v in s:
                if v in cand_set:
                    return v
            raise AssertionError("unreachable")
