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
    *,
    weights: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Indices posicionales (train, test) con estratificacion exacta.

    Devuelve arrays de enteros disjuntos que cubren 0..N-1. La tasa de cada
    clase en train coincide con la global salvo redondeo entero exacto.

    Modo ponderado (Fase 3.2): si `weights` no es None, el vector se
    VALIDA (1D, longitud = len(y), finito, estrictamente positivo) pero NO
    se usa para repartir filas. La estratificacion es SIEMPRE Hamilton-Hare
    clasico sobre el conteo de filas `n_k` por clase: los pesos viajan con
    cada fila y afectan al modelo, no a la particion. Consecuencia: con
    `weights` declarado, `idx_train` e `idx_test` son identicos a los del
    modo sin pesos (paridad total respecto al pre-3.2); el parametro solo
    permite validar los pesos antes de que el llamador (Session) separe
    los sub-vectores de train/test.

    Check B2 (SOLO cuando `weights` no es None): cada clase observada en
    `y` debe quedar con al menos 2 filas fisicas en train Y al menos 2 en
    test. Es defensa contra fixtures degenerados con pesos declarados. El
    camino sin pesos NO ejecuta B2: invariante C1 (comportamiento
    identico al pre-3.2); ademas, con Hamilton-Hare una clase con
    n_k >= 2 no puede quedar con 0 filas en ninguna particion bajo esta
    convencion.
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

    w: np.ndarray | None = None
    if weights is not None:
        w = np.asarray(weights, dtype=float)
        if w.ndim != 1:
            raise ValueError(
                f"[splitting] weights debe ser 1D: ndim={w.ndim}"
            )
        if len(w) != n_total:
            raise ValueError(
                f"[splitting] weights longitud {len(w)} != len(y) {n_total}"
            )
        if not np.isfinite(w).all():
            raise ValueError("[splitting] weights contiene valores no finitos")
        if not (w > 0).all():
            raise ValueError(
                "[splitting] weights deben ser estrictamente positivos"
            )

    rng = np.random.default_rng(seed)

    n_train_obj = int(round(n_total * train_frac))

    permutadas: list[np.ndarray] = []
    partes: list[np.ndarray] = []
    fracs: list[float] = []
    totals: list[int] = []
    for clase in classes:
        idx_c = np.flatnonzero(yv == clase)
        idx_c = idx_c[rng.permutation(len(idx_c))]
        permutadas.append(idx_c)
        # La cuota es siempre por conteo de filas, con o sin pesos.
        q = len(idx_c) * train_frac
        f = int(np.floor(q))
        partes.append(idx_c[: min(f, len(idx_c))])
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

    # Check B2 (solo modo ponderado): cada clase debe tener >=2 filas
    # fisicas en train y en test. Sin pesos, C1 exige paridad pre-3.2.
    if w is not None:
        for clase in classes:
            n_tr = int(np.sum(yv[idx_train] == clase))
            n_te = int(np.sum(yv[idx_test] == clase))
            if n_tr < 2 or n_te < 2:
                raise ValueError(
                    f"[splitting] check B2: clase {clase!r} queda con "
                    f"{n_tr} filas en train y {n_te} en test "
                    f"(minimo 2 en cada lado)"
                )

    log.info(
        "[splitting] N=%d -> train=%d (%.2f%%) test=%d (seed=%d, clases=%d)",
        n_total, len(idx_train), 100.0 * len(idx_train) / n_total,
        len(idx_test), seed, n_clases,
    )
    return idx_train, idx_test
