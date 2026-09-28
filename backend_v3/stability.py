"""Monitoreo de estabilidad poblacional y de atributos (TreeGov, Fase 1.3).

PSI (Population Stability Index) sobre las hojas del arbol y CSI
(Characteristic Stability Index) por covariable, contra la cohorte OOT.

Formulas explicitas (todas las probabilidades con clip epsilon antes del
log; ver nota en psi_index):

    PSI = sum_k (p_actual,k - p_expected,k) * ln(p_actual,k / p_expected,k)

    (dos formas equivalentes: divergencia KL simetrica KL(a||e)+KL(e||a))

    Gini Drop = (Gini_train - Gini_X) / Gini_train   (X in {OOS, OOT})

Semaforos Basel/EBA:  PSI/CSI < 0.10 -> STABLE;  [0.10, 0.25) -> MODERATE;
>= 0.25 -> UNSTABLE.  Gini Drop: > 0.20 -> preventivo; > 0.40 -> critico.

La referencia ("expected") es SIEMPRE la particion train (la poblacion de
desarrollo, por definicion). Los bins de CSI de variables continuas son los
deciles APRENDIDOS SOLO EN TRAIN (con borde inferior -inf y superior +inf:
el primer y ultimo decil absorben valores fuera del rango de train).
Categorias nominales: las observadas en train; las nuevas en OOT se agrupan
en <OTHER> con p_expected = eps (la novedad se registra con ese rango).

Citas:
  Siddiqi, N. (2006). Credit Risk Scorecards: Developing and Implementing
    Intelligent Credit Scoring. Wiley. (PSI/CSI como herramienta de
    monitoreo de scorecards.)
  Convencion Basel/EBA para los umbrales del semaforo.

Dependencias: numpy, pandas, stdlib. Reutiliza validation.predict_*.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from typing import TYPE_CHECKING

from .log_config import get_logger
from .tree_builder import TreeModel
from .types import PredictorType

if TYPE_CHECKING:
    from .validation import OOSMetrics

__all__ = [
    "PSIReport",
    "CSIReport",
    "GiniDropReport",
    "OOTReport",
    "StabilityMonitor",
    "psi_index",
    "traffic_light",
    "gini_drop_alert",
]

_EPS_DEFAULT: float = 1e-4


def traffic_light(value: float) -> str:
    """Semaforo Basel/EBA: <0.10 STABLE; <0.25 MODERATE; >=0.25 UNSTABLE.
    NaN -> "UNDETERMINED" (no se clasifica)."""
    if not value == value:  # NaN -> no se clasifica
        return "UNDETERMINED"
    if value < 0.10:
        return "STABLE"
    if value < 0.25:
        return "MODERATE"
    return "UNSTABLE"


def gini_drop_alert(drop: float | None) -> str:
    """Semaforo del Gini Drop. None o NaN -> "UNDETERMINED" (jamás se
    reporta como 'NONE': una degradacion indefinida no es ausencia de
    alerta, es ausencia de confianza).

    Umbrales: drop > 0.40 -> "CRITICAL"; drop > 0.20 -> "WARNING";
    en caso contrario -> "NONE".
    """
    if drop is None or drop != drop:  # None o NaN
        return "UNDETERMINED"
    if drop > 0.40:
        return "CRITICAL"
    if drop > 0.20:
        return "WARNING"
    return "NONE"


def psi_index(
    expected: np.ndarray, actual: np.ndarray
) -> tuple[float, np.ndarray]:
    """PSI con clip epsilon=SIN renormalizar (decision MRM deliberada)."""
    exp = np.asarray(expected, dtype=float)
    act = np.asarray(actual, dtype=float)
    if exp.shape != act.shape:
        raise ValueError(
            f"[stability] vectores de longitud distinta: {exp.shape} vs {act.shape}"
        )
    # Decision: NO renormalizacion tras el clip para PRESERVAR la senal de
    # los bins vacios en OOT; el error de escala es despreciable frente a
    # los umbrales 0.10/0.25 cuando los bins no estan vacios.
    exp = np.clip(exp, _EPS_DEFAULT, None)
    act = np.clip(act, _EPS_DEFAULT, None)
    contrib = (act - exp) * np.log(act / exp)
    return float(contrib.sum()), contrib


@dataclass(frozen=True)
class PSIReport:
    psi: float
    flag: str
    per_bin: tuple[tuple[str, float, float, float], ...]  # (etiqueta, p_exp, p_act, contrib)


@dataclass(frozen=True)
class CSIReport:
    predictor: str
    csi: float
    flag: str
    per_bin: tuple[tuple[str, float, float, float], ...]


@dataclass(frozen=True)
class GiniDropReport:
    """Gini Drop OOS/OOT.

    Si compute_oos_metrics() en la cohorte X devuelve Gini=None (cohorte
    monoclase), drop_X queda None y el semaforo es "NONE".
    Si gini_train == 0 (modelo sin poder discriminante), ambos drops quedan
    None (division por cero evitada; se loggea WARNING).
    """

    gini_train: float
    gini_oos: float | None
    gini_oot: float | None
    drop_oos: float | None
    drop_oot: float | None
    alert_oos: str
    alert_oot: str
    temporal_verified: bool    # False -> "OOS, not OOT" en la narrativa


@dataclass(frozen=True)
class OOTReport:
    """Bundle de evaluacion de la cohorte OOT (Fase 1.3).

    metrics es None si la cohorte enrutable fue demasiado pequena para las
    metricas (WARNING en log); n_excluded cubre las filas invisibles para
    el arbol (categorias/valores no vistos en train).
    """

    metrics: "OOSMetrics | None"    # metricas sobre filas enrutables; None si demasiado pocas
    drop: GiniDropReport
    psi: PSIReport
    csi: tuple[CSIReport, ...]
    n_oot: int
    n_excluded: int


class StabilityMonitor:
    """Calcula PSI de hojas y CSI por covariable (train como referencia)."""

    def __init__(
        self, *, eps: float = _EPS_DEFAULT, logger: logging.Logger | None = None
    ) -> None:
        self.eps = float(eps)
        self._log = logger if logger is not None else get_logger("stability")

    # ------------------------------------------------------------------

    def leaf_psi(
        self,
        model: TreeModel,
        leaf_counts_train: np.ndarray,
        leaf_assign_oot: np.ndarray,
    ) -> PSIReport:
        """PSI sobre la distribucion de hojas del arbol.

        leaf_counts_train: tamanios de las hojas en train (orden node_id).
        leaf_assign_oot: node_id de hoja por fila OOT; -1 = no asignable
        (va a un bin extra "<UNSEEN>" con p_expected=eps).
        """
        hojas = [nd for nd in model.nodes if nd.is_leaf]
        leaf_ids = [nd.node_id for nd in hojas]
        n_train = int(leaf_counts_train.sum())
        p_exp = leaf_counts_train.astype(float) / n_train

        n_oot_total = int(leaf_assign_oot.size)
        asignadas = leaf_assign_oot[leaf_assign_oot >= 0]
        counts = np.zeros(len(hojas), dtype=float)
        for i, nid in enumerate(leaf_ids):
            counts[i] = float((asignadas == nid).sum())
        n_excluidas = n_oot_total - int(asignadas.size)

        etiquetas = [f"leaf_{nid}" for nid in leaf_ids]
        if n_excluidas > 0:
            self._log.info(
                "[stability] PSI: %d filas OOT sin hoja -> bin '<UNSEEN>'",
                n_excluidas,
            )
            etiquetas.append("<UNSEEN>")
            p_exp = np.concatenate([p_exp, [0.0]])
            counts = np.concatenate([counts, [float(n_excluidas)]])
        p_act = counts / max(n_oot_total, 1)

        psi, contrib = psi_index(p_exp, p_act)
        per_bin = tuple(
            (etiquetas[i], float(p_exp[i]), float(p_act[i]), float(contrib[i]))
            for i in range(len(etiquetas))
        )
        reporte = PSIReport(psi=psi, flag=traffic_light(psi), per_bin=per_bin)
        self._log.info(
            "[stability] PSI hojas: %.6g (%s) sobre %d hojas",
            psi, reporte.flag, len(hojas),
        )
        return reporte

    # ------------------------------------------------------------------

    def covariate_csi(
        self,
        X_train: pd.DataFrame,
        X_actual: pd.DataFrame,
        predictor: str,
        ptype: PredictorType,
    ) -> CSIReport:
        """CSI por covariable (train = referencia).

        Continua/ordinal numerico: deciles aprendidos SOLO en train
        (primer y ultimo bin abiertos: -inf / +inf absorven desbordes).
        Nominal u ordinal simbolico: categorias observadas en train;
        las nuevas en OOT se agrupan en <OTHER> con p_expected=eps.
        """
        x_tr = X_train[predictor]
        x_ac = X_actual[predictor]
        n_tr = int(len(x_tr))
        n_ac = int(len(x_ac))
        if n_tr == 0 or n_ac == 0:
            raise ValueError(f"[stability] CSI {predictor!r}: columna vacia")

        if ptype in (PredictorType.CONTINUOUS, PredictorType.ORDINAL) and \
                pd.api.types.is_numeric_dtype(x_tr):
            qs = np.quantile(x_tr.to_numpy(dtype=float),
                             np.linspace(0.0, 1.0, 11))
            bordes = np.unique(qs)
            bordes[0] = -np.inf
            bordes[-1] = np.inf
            etiquetas = [f"D{i}" for i in range(len(bordes) - 1)]
            bins_tr = np.digitize(x_tr.to_numpy(dtype=float), bordes[1:-1])
            bins_ac = np.digitize(x_ac.to_numpy(dtype=float), bordes[1:-1])
            p_exp = np.array(
                [float((bins_tr == i).sum()) for i in range(len(etiquetas))],
                dtype=float,
            ) / n_tr
            p_act = np.array(
                [float((bins_ac == i).sum()) for i in range(len(etiquetas))],
                dtype=float,
            ) / n_ac
        else:
            clases_tr = list(dict.fromkeys(x_tr.dropna().tolist()))
            p_exp = np.array(
                [float((x_tr == c).sum()) for c in clases_tr], dtype=float
            ) / n_tr
            p_act_parts = []
            # numpy puro (booleano): evita el dtype mixto Series |= ndarray
            visto = np.zeros(len(x_ac), dtype=bool)
            for c in clases_tr:
                m = (x_ac == c).to_numpy()
                p_act_parts.append(float(m.sum()))
                visto |= m
            p_act = np.array(p_act_parts, dtype=float) / n_ac
            etiquetas = [str(c) for c in clases_tr]
            n_otros = int((~visto).sum())
            if n_otros > 0:
                self._log.info(
                    "[stability] CSI %r: %d filas con categorias nuevas -> <OTHER>",
                    predictor, n_otros,
                )
                etiquetas.append("<OTHER>")
                p_exp = np.concatenate([p_exp, [0.0]])
                p_act = np.concatenate([p_act, [n_otros / n_ac]])

        csi, contrib = psi_index(p_exp, p_act)
        per_bin = tuple(
            (etiquetas[i], float(p_exp[i]), float(p_act[i]), float(contrib[i]))
            for i in range(len(etiquetas))
        )
        return CSIReport(predictor=predictor, csi=csi, flag=traffic_light(csi),
                         per_bin=per_bin)

    # ------------------------------------------------------------------

    def report(
        self,
        model: TreeModel,
        X_train: pd.DataFrame,
        X_actual: pd.DataFrame,
        leaf_assign_train: np.ndarray,
        leaf_assign_actual: np.ndarray,
        spec: dict[str, PredictorType],
    ) -> tuple[PSIReport, tuple[CSIReport, ...]]:
        """PSI de hojas + CSI de todas las covariables."""
        hojas = [nd for nd in model.nodes if nd.is_leaf]
        leaf_ids = [nd.node_id for nd in hojas]
        counts = np.array(
            [float((leaf_assign_train == nid).sum()) for nid in leaf_ids]
        )
        psi = self.leaf_psi(model, counts, leaf_assign_actual)
        csi = tuple(
            self.covariate_csi(X_train, X_actual, name, ptype)
            for name, ptype in spec.items()
        )
        return psi, csi
