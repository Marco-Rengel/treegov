"""Inferencia de tipos de predictor (TreeGov, backend_v3, Fase 1).

Heuristica explicita y auditable (constante MAX_ORDINAL_CATS):

    dtype no numerico            -> NOMINAL
    numerico, n_distinct <= 20   -> ORDINAL
    numerico, n_distinct >  20   -> CONTINUOUS

Nota MRM: una variable discreta con mas de 20 valores (p. ej. edad) se
clasifica CONTINUOUS por decision deliberada: se usa en umbrales/QDA.
Toda inferencia queda registrada en el log, columna a columna.

Extraido del orquestador (treegov.py) en la Fase 1.
"""

from __future__ import annotations

import logging

import pandas as pd

from .log_config import get_logger
from .types import PredictorType

__all__ = ["MAX_ORDINAL_CATS", "infer_spec"]

MAX_ORDINAL_CATS: int = 20


def _infer_column(s: pd.Series) -> PredictorType:
    """Heuristica por columna (extraida en Fase 2.1 para reuso en
    Session.describe_dataset sin duplicar la regla)."""
    if not pd.api.types.is_numeric_dtype(s):
        return PredictorType.NOMINAL
    if int(s.nunique(dropna=True)) <= MAX_ORDINAL_CATS:
        return PredictorType.ORDINAL
    return PredictorType.CONTINUOUS


def infer_spec(
    df: pd.DataFrame,
    target: str,
    log: logging.Logger | None = None,
) -> dict[str, PredictorType]:
    """Infiere {columna: PredictorType} excluyendo el target."""
    if log is None:
        log = get_logger("profiling")
    if target not in df.columns:
        raise ValueError(f"[profiling] target ausente: {target!r}")
    spec: dict[str, PredictorType] = {}
    for col in df.columns:
        if col == target:
            continue
        s = df[col]
        ptype = _infer_column(s)
        spec[col] = ptype
        log.info(
            "[profiling] %-24s dtype=%-8s n_distinct=%-5d -> %s",
            col, str(s.dtype), int(s.nunique(dropna=True)), ptype.name,
        )
    if not spec:
        raise ValueError("[profiling] el dataset no tiene predictores")
    return spec
