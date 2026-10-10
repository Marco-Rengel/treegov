"""Validacion fuera de muestra (OOS) de arboles (TreeGov, backend_v3, Fase 1.2).

Metricas con formulas explicitas y cita bibliografica (caja blanca; solo
numpy/pandas/scipy.stats):

  * AUC por Wilcoxon-Mann-Whitney con rango promedio (mid-ranks) en empates:
        r_i : rango medio de p_i ;  R1 = sum_{y_i=1} r_i
        U   = R1 - n1 (n1 + 1) / 2 ;  AUC = U / (n1 n0)
        Gini = 2 * AUC - 1
    (Hanley & McNeil 1982; convencion del proyecto.)

  * KS = max_s |F_bad(s) - F_good(s)|  sobre las curvas acumuladas ordenadas
    por el score.

  * Hosmer-Lemeshow (Hosmer & Lemeshow 1980), sobre G grupos del score
    ordenado (conteo equitativo):
        pi_g = (1/N_g) sum_{i in g} p_i
        H    = sum_g (O_g - N_g pi_g)^2 / [N_g pi_g (1 - pi_g)]
        H ~ chi2(G - 2)
    Guarda: n_groups * 5 > N -> ValueError (cada grupo debe caber >=5 obs);
    pi_g extremo se recorta a [1e-15, 1 - 1e-15] (documentado).

  * Brier Score + Brier Skill Score (Brier 1950):
        BS = (1/N) sum (p_i - y_i)^2 ;  BS_ref = y_bar (1 - y_bar)
        BSS = 1 - BS / BS_ref
    Si y es constante (n0 o n1 = 0): auc/gini/ks/pr_auc -> None y WARNING
    (no computables); BSS -> NaN (BS_ref = 0). Jamas se lanza excepcion
    por ello: la alerta queda en el log.

  * ROC (fpr, tpr, threshold) por umbrales descendentes, punto a punto, con
    inicio implicito en (0, 0, +inf) y cierre en (1, 1, -inf).
  * PR-AUC como Average Precision escalonado (Davis & Goadrich 2006, ICML):
        AP = sum_i (R_i - R_{i-1}) * P_i     (sin trapezoide)

  * Extension ponderada (Fase 3.2.g): compute_oos_metrics acepta `weights`
    keyword-only. Con pesos, cada formula acumula masa ponderada en lugar
    de contar filas (Heeringa, West & Berglund 2010, §5.5). El AUC se
    calcula por formula directa de pares con medio-credito en empates,
    numericamente equivalente al mid-rank cuando los pesos son uniformes.
    Con weights=None, resultados identicos al pre-3.2.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import chi2 as _chi2_dist

from .log_config import get_logger
from .tree_builder import TreeModel

__all__ = ["OOSMetrics", "predict_pd", "predict_leaf_assignment", "compute_oos_metrics"]

_HL_EPS = 1e-15


@dataclass(frozen=True)
class OOSMetrics:
    """Metricas OOS inmutables. None = no computable (documentado en log)."""

    n_test: int
    n_events: int
    auc: float | None
    gini: float | None
    ks: float | None
    pr_auc: float | None
    hl_stat: float
    hl_df: int
    hl_p: float
    hl_groups: int
    brier: float
    brier_ref: float
    brier_skill: float
    roc_points: tuple[tuple[float, float, float], ...]


def predict_leaf_assignment(
    model: TreeModel, X: pd.DataFrame, *, unseen_policy: str = "error"
) -> np.ndarray:
    """Asigna a cada fila el node_id de su hoja.

    unseen_policy:
      - "error"    (default): ValueError si alguna fila no puede enrutarse
                   (NaN residual o categoria no vista en train).
      - "majority": las filas sin ruta se asignan a la hoja mas poblada del
                   arbol (empate -> menor node_id; determinista).
      - "exclude" : las filas sin ruta quedan con -1 (el llamador decide).
    """
    if unseen_policy not in ("error", "majority", "exclude"):
        raise ValueError(f"[validation] unseen_policy invalida: {unseen_policy!r}")
    if not model.nodes:
        raise ValueError("[validation] modelo vacio")
    n_rows = int(len(X))
    asign = np.full(n_rows, -1, dtype=int)
    cola: list[tuple[int, np.ndarray]] = [(model.root_id, np.arange(n_rows))]
    while cola:
        nid, idx = cola.pop()
        nd = model.nodes[nid]
        if nd.is_leaf:
            asign[idx] = nid
            continue
        cfg = nd.split
        assert cfg is not None
        col = X[cfg.predictor]
        if cfg.threshold is not None:
            vals = col.iloc[idx].to_numpy(dtype=float)
            valido = ~pd.isna(vals)  # NaN -> sin ruta
            izq = valido & (vals <= float(cfg.threshold))
            der = valido & (vals > float(cfg.threshold))
            cola.append((nd.child_ids[0], idx[izq]))
            cola.append((nd.child_ids[1], idx[der]))
        else:
            etiquetas = col.iloc[idx]
            asignadas = np.zeros(len(idx), dtype=bool)
            for rama, cid in zip(cfg.branches or (), nd.child_ids):
                mask = etiquetas.isin(list(rama)).to_numpy()
                asignadas |= mask
                cola.append((cid, idx[mask]))
            # categorias no vistas o NaN quedan sin ruta (se resuelven abajo)

    sin_ruta = np.flatnonzero(asign < 0)
    if sin_ruta.size:
        if unseen_policy == "majority":
            hojas = [nd for nd in model.nodes if nd.is_leaf]
            destino = max(hojas, key=lambda h: (-h.n, h.node_id))
            asign[sin_ruta] = destino.node_id
            get_logger("validation").info(
                "[validation] %d filas sin ruta -> hoja mayoritaria id=%d",
                int(sin_ruta.size), destino.node_id,
            )
        elif unseen_policy == "error":
            raise ValueError(
                f"[validation] {sin_ruta.size} filas sin hoja asignada "
                "(routing incompleto; use unseen_policy='majority'/'exclude')"
            )
        # "exclude": quedan en -1
    return asign


def predict_pd(
    model: TreeModel, X: pd.DataFrame, *, unseen_policy: str = "error"
) -> np.ndarray:
    """Devuelve una matriz (n_rows, K) con el vector pd_final por fila.

    La columna c corresponde a la clase model.class_labels[c] (orden
    canonico: indice 0 = target_class). Las filas excluidas por politica
    (asign < 0) quedan con np.nan en las K columnas. For K=2 with
    target_class=1, column 0 is numerically identical to the pre-3.1
    scalar PD (parity invariant §10.1).

    X_test se asume imputado con TrainOnlyImputer ajustado SOLO sobre train
    (politica anti-leakage); la politica ante valores no vistos es visible
    via 'unseen_policy' (default conservador: error).
    """
    asign = predict_leaf_assignment(model, X, unseen_policy=unseen_policy)
    n_classes = len(model.class_labels)
    out = np.full((len(X), n_classes), np.nan, dtype=float)
    ok = asign >= 0
    for nid in {int(a) for a in asign[ok]}:
        out[asign == nid] = model.nodes[nid].pd_final
    return out


def compute_oos_metrics(
    p: np.ndarray, y: np.ndarray, *, n_groups: int = 10,
    weights: np.ndarray | None = None,
) -> OOSMetrics:
    """Todas las metricas sobre (p, y) de test. Determinista.

    Fase 3.2.g: `weights` (keyword-only, default None) activa el modo
    ponderado: cada formula acumula masa ponderada en lugar de contar
    filas (Heeringa, West & Berglund 2010, §5.5). Con `weights=None`,
    los resultados son identicos bit a bit al comportamiento pre-3.2.
    """
    log = get_logger("validation")
    pv = np.asarray(p, dtype=float)
    yv = np.asarray(y, dtype=int)
    n_pre = int(pv.size)
    if weights is not None:
        w = np.asarray(weights, dtype=float)
        if w.ndim != 1:
            raise ValueError(
                f"[validation] weights debe ser 1D: ndim={w.ndim}"
            )
        if len(w) != n_pre:
            raise ValueError(
                f"[validation] weights longitud {len(w)} != len(p) {n_pre}"
            )
        if not np.isfinite(w).all():
            raise ValueError(
                "[validation] weights contiene valores no finitos"
            )
        if not (w > 0).all():
            raise ValueError(
                "[validation] weights deben ser estrictamente positivos"
            )
    else:
        w = np.ones(n_pre, dtype=float)
    if pv.ndim != 1:
        raise ValueError(
            "[validation] compute_oos_metrics recibio una matriz 2D (K "
            "clases). Las metricas multiclase estan planificadas para la "
            "Fase 3.5."
        )
    if pv.shape != yv.shape:
        raise ValueError("[validation] p e y deben ser vectores de igual longitud")
    n = int(pv.size)
    if n == 0:
        raise ValueError("[validation] test vacio")
    if n_groups < 3:
        raise ValueError(
            f"[validation] Hosmer-Lemeshow exige n_groups >= 3 (gl = G - 2); "
            f"n_groups={n_groups}"
        )
    if n_groups * 5 > n:
        raise ValueError(
            f"[validation] n_groups={n_groups} exige >= {5 * n_groups} obs; "
            f"N test = {n}"
        )

    # orden descendente por score (estable ante empates)
    orden = np.argsort(-pv, kind="mergesort")
    ys = yv[orden]
    ps = pv[orden]
    ws = w[orden]
    n1 = int(ys.sum())
    n0 = n - n1

    # ---- ROC por umbrales unicos descendentes (incluye (0,0,+inf)) ----
    # El umbral t cubre TODO el grupo de empate (score >= t): los acumulados
    # se toman al FINAL de cada bloque de valores iguales, no al inicio.
    # Con pesos, los acumulados son MASA ponderada (no conteos).
    finales = np.flatnonzero(np.r_[ps[1:] != ps[:-1], True])
    tp_w = np.cumsum(ys * ws)
    fp_w = np.cumsum((1 - ys) * ws)
    tp_t = tp_w[finales]
    fp_t = fp_w[finales]
    thr_t = ps[finales]
    w_bad = float(tp_t[-1]) if len(tp_t) else 0.0    # masa total de bads
    w_good = float(fp_t[-1]) if len(fp_t) else 0.0   # masa total de goods
    roc = [(0.0, 0.0, math.inf)]
    roc.extend(
        (float(fp_t[i] / w_good) if w_good else 0.0,
         float(tp_t[i] / w_bad) if w_bad else 0.0,
         float(thr_t[i]))
        for i in range(len(finales))
    )
    if not (roc[-1][0] == 1.0 and roc[-1][1] == 1.0):
        roc.append((1.0, 1.0, float("-inf")))
    roc_points = tuple(roc)

    if n1 == 0 or n0 == 0:
        log.warning(
            "[validation] una sola clase en test (n1=%d, n0=%d): auc/gini/ks/"
            "pr_auc no computables -> None", n1, n0,
        )
        auc = gini = ks = pr_auc = None
    else:
        # AUC ponderado: formula directa de pares con medio-credito en
        # empates (concordantes=1, empates=0.5, discordantes=0). Con pesos
        # uniformes es numericamente equivalente al mid-rank de
        # Wilcoxon-Mann-Whitney (misma suma de pares).
        w_bad_block = tp_t - np.concatenate([[0.0], tp_t[:-1]])
        w_good_block = fp_t - np.concatenate([[0.0], fp_t[:-1]])
        tp_prev = np.concatenate([[0.0], tp_t[:-1]])
        contrib = tp_prev * w_good_block + 0.5 * w_bad_block * w_good_block
        auc = float(np.sum(contrib) / (w_bad * w_good))
        gini = 2.0 * auc - 1.0

        # KS: sobre la acumulacion descendente (masa ponderada)
        f_bad = tp_t / w_bad
        f_good = fp_t / w_good
        ks = float(np.max(np.abs(f_bad - f_good)))

        # PR-AUC (average precision, escalonado; Davis & Goadrich 2006)
        recall = tp_t / w_bad
        precision = tp_t / (tp_t + fp_t)
        recall_prev = np.concatenate([[0.0], recall[:-1]])
        pr_auc = float(np.sum((recall - recall_prev) * precision))

    # ---- Hosmer-Lemeshow (grupos equitativos por score) ----
    # Grupos por posicion en el orden descendente (criterio actual); dentro
    # de cada grupo se acumula masa ponderada.
    bordes = np.floor(np.arange(1, n_groups) * n / n_groups).astype(int)
    hl_h = 0.0
    for g in range(n_groups):
        ini = 0 if g == 0 else bordes[g - 1]
        fin = n if g == n_groups - 1 else bordes[g]
        sub_p = ps[ini:fin]
        sub_y = ys[ini:fin]
        sub_w = ws[ini:fin]
        n_g_w = max(float(sub_w.sum()), _HL_EPS)
        pi_g = float((sub_w * sub_p).sum() / n_g_w)
        pi_g = min(max(pi_g, _HL_EPS), 1.0 - _HL_EPS)
        o_g = float((sub_w * sub_y).sum())
        hl_h += (o_g - n_g_w * pi_g) ** 2 / (n_g_w * pi_g * (1.0 - pi_g))
    hl_df = n_groups - 2
    hl_p = float(_chi2_dist.sf(hl_h, hl_df))

    # ---- Brier (ponderado) ----
    w_tot = float(w.sum())
    bs = float((w * (pv - yv) ** 2).sum() / w_tot)
    y_bar = float((w * yv).sum() / w_tot)
    bs_ref = y_bar * (1.0 - y_bar)
    bss = float("nan") if bs_ref == 0.0 else 1.0 - bs / bs_ref

    return OOSMetrics(
        n_test=n, n_events=n1,
        auc=auc, gini=gini, ks=ks, pr_auc=pr_auc,
        hl_stat=float(hl_h), hl_df=hl_df, hl_p=hl_p, hl_groups=n_groups,
        brier=bs, brier_ref=bs_ref, brier_skill=bss,
        roc_points=roc_points,
    )
