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

  * Extension multiclase (Fase 3.5.a): compute_oos_metrics acepta p 2D de
    shape (n, K) segun el contrato D15 (ver el docstring de la funcion).
    Para K > 2 generaliza: AUC/Gini de Hand & Till 2001 (media aritmetica
    de los AUC por par, calculados con la misma formula directa de pares
    del binario; decision D1), KS worst-case por par (minimo de los KS
    por par; decision D4), Brier multiclase con factor 1/2 (decisiones
    D6/D12) y BSS frente al climatologico, PR-AUC micro-average sobre el
    problema pooled (decision D7; Davis & Goadrich 2006), K curvas ROC
    one-vs-rest expuestas en roc_per_class (decisiones D8/D17), y
    Hosmer-Lemeshow bloqueado por diseno con WARNING (decisiones D5/D16;
    Fagerland, Hosmer & Bofin 2012, evaluado y rechazado). La composicion
    ponderada sigue el patron de la Fase 3.2.g (decision D10; Heeringa,
    West & Berglund 2010, §5.3).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy.stats import chi2 as _chi2_dist

from .log_config import get_logger
from .tree_builder import TreeModel

__all__ = ["OOSMetrics", "predict_pd", "predict_leaf_assignment", "compute_oos_metrics"]

_HL_EPS = 1e-15


@dataclass(frozen=True)
class OOSMetrics:
    """Metricas OOS inmutables. None = no computable (documentado en log).

    hl_stat/hl_df/hl_p son None en el camino multiclase (K > 2): HL es
    binary-only por diseno (decisiones D5/D16). hl_groups se mantiene int
    porque refleja el parametro n_groups del llamador.

    Campos multiclase (Fase 3.5.a, decision D17), con default vacio para
    no romper constructores pre-3.5:
      - ks_pairs: tupla (i, j, ks) por par i < j, ordenada por i y luego j.
      - auc_pairs: tupla (i, j, auc) con el mismo orden.
      - roc_per_class: tupla de K curvas ROC one-vs-rest, cada una con la
        misma estructura de puntos (fpr, tpr, threshold) que roc_points.
    El modo 1D los deja vacios; el modo 2D los puebla (para K=2 con una
    unica tupla (0, 1, valor) en ks_pairs/auc_pairs y dos curvas en
    roc_per_class).
    """

    n_test: int
    n_events: int
    auc: float | None
    gini: float | None
    ks: float | None
    pr_auc: float | None
    hl_stat: float | None
    hl_df: int | None
    hl_p: float | None
    hl_groups: int
    brier: float
    brier_ref: float
    brier_skill: float
    roc_points: tuple[tuple[float, float, float], ...]
    ks_pairs: tuple[tuple[int, int, float], ...] = ()
    auc_pairs: tuple[tuple[int, int, float], ...] = ()
    roc_per_class: tuple[tuple[tuple[float, float, float], ...], ...] = ()


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


# ---------------------------------------------------------------------------
# Helpers privados (Fase 3.5.a): kernels reutilizables del barrido de
# umbrales descendentes. Ninguno valida entradas; el llamador lo hace.
# ---------------------------------------------------------------------------


def _roc_curve(scores: np.ndarray, ind: np.ndarray, w: np.ndarray):
    """ROC (fpr, tpr, threshold) por umbrales descendentes.

    Bloques de empate cubiertos completos (acumulados al final de cada
    bloque de scores iguales), inicio implicito en (0, 0, +inf) y cierre
    en (1, 1, -inf) si el ultimo bloque no alcanza (1, 1). Con pesos, los
    acumulados son masa ponderada. Misma construccion que el ROC binario
    clasico.
    """
    orden = np.argsort(-scores, kind="mergesort")
    ys = ind[orden]
    ps = scores[orden]
    ws = w[orden]
    finales = np.flatnonzero(np.r_[ps[1:] != ps[:-1], True])
    tp_w = np.cumsum(ys * ws)
    fp_w = np.cumsum((1 - ys) * ws)
    tp_t = tp_w[finales]
    fp_t = fp_w[finales]
    thr_t = ps[finales]
    w_bad = float(tp_t[-1]) if len(tp_t) else 0.0    # masa total de positivos
    w_good = float(fp_t[-1]) if len(fp_t) else 0.0   # masa total de negativos
    roc = [(0.0, 0.0, math.inf)]
    roc.extend(
        (float(fp_t[i] / w_good) if w_good else 0.0,
         float(tp_t[i] / w_bad) if w_bad else 0.0,
         float(thr_t[i]))
        for i in range(len(finales))
    )
    if not (roc[-1][0] == 1.0 and roc[-1][1] == 1.0):
        roc.append((1.0, 1.0, float("-inf")))
    return tuple(roc)


def _pair_auc_ks(scores: np.ndarray, ind: np.ndarray, w: np.ndarray):
    """(auc, ks) del kernel binario sobre (scores, indicador 0/1, pesos).

    AUC por formula directa de pares con medio-credito en empates
    (concordantes=1, empates=0.5, discordantes=0; normalizado por las
    masas positiva y negativa). KS = max |F_pos - F_neg| sobre las CDFs
    empiricas de la acumulacion descendente por bloques de empate.
    Devuelve (None, None) si alguna de las dos masas es cero.
    """
    orden = np.argsort(-scores, kind="mergesort")
    ys = ind[orden]
    ps = scores[orden]
    ws = w[orden]
    finales = np.flatnonzero(np.r_[ps[1:] != ps[:-1], True])
    tp_w = np.cumsum(ys * ws)
    fp_w = np.cumsum((1 - ys) * ws)
    tp_t = tp_w[finales]
    fp_t = fp_w[finales]
    w_bad = float(tp_t[-1]) if len(tp_t) else 0.0
    w_good = float(fp_t[-1]) if len(fp_t) else 0.0
    if w_bad == 0.0 or w_good == 0.0:
        return None, None
    w_bad_block = tp_t - np.concatenate([[0.0], tp_t[:-1]])
    w_good_block = fp_t - np.concatenate([[0.0], fp_t[:-1]])
    tp_prev = np.concatenate([[0.0], tp_t[:-1]])
    contrib = tp_prev * w_good_block + 0.5 * w_bad_block * w_good_block
    auc = float(np.sum(contrib) / (w_bad * w_good))
    f_bad = tp_t / w_bad
    f_good = fp_t / w_good
    ks = float(np.max(np.abs(f_bad - f_good)))
    return auc, ks


def _pr_auc(scores: np.ndarray, ind: np.ndarray, w: np.ndarray):
    """Average Precision escalonado (Davis & Goadrich 2006), sin trapezoide.

    AP = sum_i (R_i - R_{i-1}) * P_i sobre bloques de empate cubiertos
    completos en el orden descendente. Es un ratio: invariante a la
    escala global de los pesos. None si la masa positiva es cero.
    """
    orden = np.argsort(-scores, kind="mergesort")
    ys = ind[orden]
    ps = scores[orden]
    ws = w[orden]
    finales = np.flatnonzero(np.r_[ps[1:] != ps[:-1], True])
    tp_w = np.cumsum(ys * ws)
    fp_w = np.cumsum((1 - ys) * ws)
    tp_t = tp_w[finales]
    fp_t = fp_w[finales]
    w_bad = float(tp_t[-1]) if len(tp_t) else 0.0
    if w_bad == 0.0:
        return None
    recall = tp_t / w_bad
    precision = tp_t / (tp_t + fp_t)
    recall_prev = np.concatenate([[0.0], recall[:-1]])
    return float(np.sum((recall - recall_prev) * precision))


def _binary_metrics(
    pv: np.ndarray, yv: np.ndarray, n_groups: int, w: np.ndarray
) -> OOSMetrics:
    """Camino binario clasico (logica pre-3.5, intacta).

    pv e yv son vectores 1D de igual longitud; w es el vector de pesos ya
    validado (unos en modo no ponderado). Devuelve OOSMetrics con los
    tres campos multiclase (ks_pairs, auc_pairs, roc_per_class) en su
    default vacio.
    """
    log = get_logger("validation")
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


def compute_oos_metrics(
    p: np.ndarray, y: np.ndarray, *, n_groups: int = 10,
    weights: np.ndarray | None = None,
) -> OOSMetrics:
    """Todas las metricas sobre (p, y) de test. Determinista.

    CONTRATO de la entrada p (decision D15). La entrada p acepta dos
    formas. La forma 1D es el camino binario clásico: y codificada 0/1 y
    p[i] la probabilidad del evento (índice 0 del vector canónico
    pd_final de cada hoja). La forma 2D tiene shape (n, K). Con K=2,
    compute_oos_metrics reduce internamente a la columna 0 y ejecuta el
    camino binario (shortcut de paridad exigido por D12 y D14). La
    etiqueta c corresponde a la columna c de p; para K=2, el contrato es
    uniforme con K mayor que 2: columna c equivale a etiqueta c, y el
    shortcut invierte y internamente (y_bin = 1 - y_2d) antes de ejecutar
    el binario clásico cuya convención es y=1 equivale a columna 0. Un
    llamador que hoy pase 1D y migre a 2D con K=2 debe pasar
    y_2d = 1 - y_1d. Con K mayor que 2, la forma 2D es obligatoria y y
    debe ser un vector 1D de etiquetas en {0, 1, ..., K-1}; el llamador
    es responsable de reordenar las clases al orden canónico antes de
    llamar.

    Campos segun la forma de p:
      - Modo 1D: ks_pairs, auc_pairs y roc_per_class quedan vacios.
      - Modo 2D con K=2: se pueblan con el par unico (0, 1) y las dos
        curvas one-vs-rest; el resto de campos se calcula sobre el
        binario clasico (columna 0, y_bin).
      - Modo 2D con K>2: auc/gini son la media de Hand & Till 2001 sobre
        los pares (decision D1), ks es el minimo por par (D4), brier usa
        el factor 1/2 (D6/D12) y bss el climatologico, pr_auc es el
        micro-average pooled (D7/D14), roc_per_class expone las K curvas
        one-vs-rest (D8/D17) y hl_stat/hl_df/hl_p son None con WARNING
        (D5/D16; Fagerland, Hosmer & Bofin 2012). Las validaciones de
        n_groups (>= 3 y n_groups * 5 <= N) se saltan para K > 2 porque
        HL no se computa; se mantienen integras para K=2 en ambos modos.
      - roc_points en el modo 2D con K>2 se puebla con la curva
        one-vs-rest de la clase 0 (la clase de interes), para que un
        consumidor que lea roc_points sin saber de multiclase obtenga
        una curva analoga a la del binario. El payload binario de
        roc_points no cambia en ningun caso para K=2.
      - n_events cuenta las observaciones de la clase de interes
        (etiqueta 0; en el binario clasico, y == 1).

    Fase 3.2.g: `weights` (keyword-only, default None) activa el modo
    ponderado: cada formula acumula masa ponderada en lugar de contar
    filas (Heeringa, West & Berglund 2010, §5.5). Con `weights=None`,
    los resultados son identicos bit a bit al comportamiento pre-3.2.

    Nota de paridad K=2 (Fase 3.5.a): para K=2 con weights None o
    uniformes, el resultado es idéntico bit a bit al pre-3.5, salvo por
    los tres campos nuevos (ks_pairs, auc_pairs, roc_per_class) que el
    modo 1D deja vacíos y el modo 2D con K=2 puebla.
    """
    log = get_logger("validation")
    pv = np.asarray(p, dtype=float)
    yv = np.asarray(y, dtype=int)
    if pv.ndim == 1:
        n_pre = int(pv.size)
    elif pv.ndim == 2:
        n_pre = int(pv.shape[0])
    else:
        raise ValueError(
            f"[validation] p debe ser 1D o 2D: ndim={pv.ndim}"
        )
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

    # ---- Dispatch por la forma de p (decision D15) ----
    if pv.ndim == 1:
        return _binary_metrics(pv, yv, n_groups, w)

    # ---- p 2D: validaciones comunes ----
    K = int(pv.shape[1])
    if K < 2:
        raise ValueError(
            f"[validation] p 2D exige K >= 2 columnas: shape={pv.shape}"
        )
    if yv.ndim != 1 or yv.shape[0] != n_pre:
        raise ValueError(
            "[validation] y debe ser un vector 1D de longitud len(p)"
        )
    if n_pre == 0:
        raise ValueError("[validation] test vacio")
    if ((yv < 0) | (yv >= K)).any():
        raise ValueError(
            f"[validation] etiquetas de y fuera de {{0, 1, ..., {K - 1}}}"
        )

    if K == 2:
        # Shortcut de paridad (D12/D14): columna 0 + y invertida al
        # binario clasico; resultado bit a bit identico al modo 1D.
        y_bin = 1 - yv
        base = _binary_metrics(pv[:, 0], y_bin, n_groups, w)
        roc_ovr1 = _roc_curve(pv[:, 1], yv, w)
        return replace(
            base,
            ks_pairs=((0, 1, base.ks),),
            auc_pairs=((0, 1, base.auc),),
            roc_per_class=(base.roc_points, roc_ovr1),
        )

    # ---- Camino multiclase (K > 2) ----
    n = n_pre
    w_tot = float(w.sum())
    # matriz indicatriz Y_ik = 1 si y[i] == k
    Y = np.zeros((n, K), dtype=float)
    Y[np.arange(n), yv] = 1.0
    class_mass = (w[:, None] * Y).sum(axis=0)

    # ---- Metricas por par (i, j), i < j (Hand & Till 2001; D1, D4) ----
    auc_pairs: list[tuple[int, int, float]] = []
    ks_pairs: list[tuple[int, int, float]] = []
    for i in range(K):
        for j in range(i + 1, K):
            m = (yv == i) | (yv == j)
            ind_ij = (yv[m] == i).astype(int)
            # A_ij: score = columna i, positivo = y==i, negativo = y==j
            a_ij, ks_ij = _pair_auc_ks(pv[m, i], ind_ij, w[m])
            # A_ji: score = columna j, positivo = y==j, negativo = y==i
            a_ji, ks_ji = _pair_auc_ks(pv[m, j], 1 - ind_ij, w[m])
            if a_ij is not None and a_ji is not None:
                auc_pairs.append((i, j, 0.5 * (a_ij + a_ji)))
            if ks_ij is not None and ks_ji is not None:
                ks_pairs.append((i, j, 0.5 * (ks_ij + ks_ji)))

    if (class_mass <= 0.0).any():
        log.warning(
            "[validation] una sola clase presente tras el filtro (masa "
            "cero en alguna clase): auc/gini no computables -> None"
        )
        auc = gini = None
    else:
        # M = media aritmetica de los auc_pair sobre los K*(K-1)/2 pares
        m_ht = float(np.mean([v for _, _, v in auc_pairs]))
        auc = m_ht
        gini = 2.0 * m_ht - 1.0
    ks = float(min(v for _, _, v in ks_pairs)) if ks_pairs else None

    # ---- Brier multiclase (factor 1/2; D6/D12) + BSS climatologico ----
    brier = float((w[:, None] * (Y - pv) ** 2).sum() / (2.0 * w_tot))
    pi_k = class_mass / w_tot
    brier_ref = 0.5 * float(np.sum(pi_k * (1.0 - pi_k)))
    if brier_ref == 0.0:
        log.warning(
            "[validation] brier_ref = 0 (una sola clase presente): "
            "brier_skill -> NaN"
        )
        brier_skill = float("nan")
    else:
        brier_skill = float(1.0 - brier / brier_ref)

    # ---- PR-AUC micro-average pooled (D7) ----
    # Problema pooled de N*K pares (i, k): positivo si y[i] == k, score
    # p[i, k], peso w[i]. Integracion stepwise identica a la del binario.
    pr_auc = _pr_auc(
        pv.reshape(-1), Y.reshape(-1).astype(int), np.repeat(w, K)
    )

    # ---- ROC one-vs-rest por clase (D8/D17) ----
    roc_per_class = tuple(
        _roc_curve(pv[:, k], (yv == k).astype(int), w) for k in range(K)
    )
    # roc_points: curva one-vs-rest de la clase 0 (clase de interes),
    # analoga a la del binario para consumidores que ignoran el multiclase.
    roc_points = roc_per_class[0]

    # ---- Hosmer-Lemeshow bloqueado por diseno (D5/D16) ----
    log.warning(
        "[validation] Hosmer-Lemeshow es binary-only por diseno: en "
        "multiclase (K=%d) hl_stat/hl_df/hl_p -> None (extension "
        "multinomial de Fagerland, Hosmer & Bofin 2012 evaluada y "
        "rechazada)", K,
    )

    return OOSMetrics(
        n_test=n, n_events=int((yv == 0).sum()),
        auc=auc, gini=gini, ks=ks, pr_auc=pr_auc,
        hl_stat=None, hl_df=None, hl_p=None, hl_groups=n_groups,
        brier=brier, brier_ref=brier_ref, brier_skill=brier_skill,
        roc_points=roc_points,
        ks_pairs=tuple(ks_pairs), auc_pairs=tuple(auc_pairs),
        roc_per_class=roc_per_class,
    )
