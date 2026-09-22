"""Particion train/test estratificada exacta (TreeGov, backend_v3, Fase 1).

Metodo de Hamilton-Hare (largest remainder) por estrato: cuotas ideales
Q_k = n_k * train_frac, asignacion base floor(Q_k), y el resto
R = round(N*frac) - sum(floors) se reparte (+1 por estrato) a las clases
con mayor fraccion residual (empate -> menor orden de clase: determinista).

Extraido del orquestador (treegov.py) en la Fase 1 para poder reutilizarlo
dentro del flujo transaccional (session_state.py). Determinista con
np.random.default_rng(seed).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .log_config import get_logger

__all__ = ["stratified_split"]


def stratified_split(
    y: pd.Series,
    train_frac: float,
    seed: int,
    log: logging.Logger | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Indices posicionales (train, test) con estratificacion exacta.

    Devuelve arrays de enteros disjuntos que cubren 0..N-1. La tasa de cada
    clase en train coincide con la global salvo redondeo entero exacto.
    """
    if log is None:
        log = get_logger("splitting")
    if isinstance(train_frac, bool) or not isinstance(
        train_frac, (int, float, np.integer, np.floating)
    ):
        raise ValueError(
            f"[splitting] train_frac debe ser numerico: {train_frac!r}"
        )
    if not (0.0 < float(train_frac) < 1.0):
        raise ValueError(f"[splitting] train_frac fuera de (0,1): {train_frac!r}")
    if not isinstance(seed, (int, np.integer)) or isinstance(seed, bool):
        raise ValueError(f"[splitting] seed debe ser entera: {seed!r}")

    yv = pd.Series(y).to_numpy()
    classes = np.unique(yv)
    n_clases = len(classes)
    n_total = len(yv)
    if n_total == 0:
        raise ValueError("[splitting] y vacio")
    n_train_obj = int(round(n_total * train_frac))
    rng = np.random.default_rng(seed)

    permutadas: list[np.ndarray] = []
    partes: list[np.ndarray] = []
    fracs: list[float] = []
    totals: list[int] = []
    for clase in classes:
        idx_c = np.flatnonzero(yv == clase)
        idx_c = idx_c[rng.permutation(len(idx_c))]
        permutadas.append(idx_c)
        q = len(idx_c) * train_frac
        f = int(np.floor(q))
        partes.append(idx_c[:f])
        fracs.append(q - f)
        totals.append(len(idx_c))

    r = n_train_obj - sum(len(p) for p in partes)
    if not (0 <= r <= n_clases):
        raise ValueError(
            f"[splitting] resto de estratificacion invalido: r={r}, "
            f"n_clases={n_clases}"
        )
    # +1 a las r mayores fracciones residuales (determinista por orden de
    # clase); la extension es siempre un SUPERCONJUNTO del floor asignado.
    orden = sorted(range(n_clases), key=lambda i: (-fracs[i], i))
    for i in orden[:r]:
        partes[i] = permutadas[i][: min(len(partes[i]) + 1, totals[i])]

    idx_train = np.sort(np.concatenate(partes))
    mask = np.zeros(n_total, dtype=bool)
    mask[idx_train] = True
    idx_test = np.flatnonzero(~mask)
    log.info(
        "[splitting] N=%d -> train=%d (%.2f%%) test=%d (seed=%d, clases=%d)",
        n_total, len(idx_train), 100.0 * len(idx_train) / n_total,
        len(idx_test), seed, n_clases,
    )
    return idx_train, idx_test
