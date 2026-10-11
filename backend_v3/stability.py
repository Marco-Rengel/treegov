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

Extension ponderada (Fase 3.2.h): leaf_psi, covariate_csi y report aceptan
pesos por fila. Convencion (diseno v2 §5.3 B4, opcion 1, default): cada
cohorte usa SUS PROPIOS pesos para representar su propia poblacion — la
distribucion de cada cohorte es la suma de pesos por bin, no el conteo de
filas. Con pesos None, comportamiento identico al pre-3.2.

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


def _validated_weights(
    weights: np.ndarray | None, n: int, who: str
) -> np.ndarray | None:
    """Valida un vector de pesos opcional (Fase 3.2.h); None pasa tal cual.

    Exige: 1D, longitud == n, finito, estrictamente positivo. Devuelve el
    array en float64 o None.
    """
    if weights is None:
        return None
    w = np.asarray(weights, dtype=float)
    if w.ndim != 1:
        raise ValueError(f"[stability] {who}: weights debe ser 1D")
    if len(w) != n:
        raise ValueError(
            f"[stability] {who}: weights longitud {len(w)} != {n}"
        )
    if not np.isfinite(w).all():
        raise ValueError(
            f"[stability] {who}: weights contiene valores no finitos"
        )
    if not (w > 0).all():
        raise ValueError(
            f"[stability] {who}: weights deben ser estrictamente positivos"
        )
    return w


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
    expected: np.ndarray, actual: np.ndarray, *, renormalize: bool = False
) -> tuple[float, np.ndarray]:
    """PSI with eps clip; optional canonical renormalization.

    Two modes (see design_decisions.md section 7.4):

      - renormalize=False (default): clip to eps WITHOUT renormalizing.
        Deliberate MRM decision: it preserves the signal of empty OOT
        bins; the scale error is negligible against the 0.10/0.25
        thresholds when bins are non-empty.
      - renormalize=True: after the eps clip, both vectors are
        renormalized to sum 1 (expected /= expected.sum();
        actual /= actual.sum()) BEFORE computing the product
        (act - exp) * log(act / exp). Canonical textbook behavior.

    Returns (psi, per_bin_contributions).
    """
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
    if renormalize:
        # Canonical opt-in mode: rescale both vectors to sum 1 right after
        # the eps clip, BEFORE the contributions (design_decisions.md 7.4).
        exp = exp / exp.sum()
        act = act / act.sum()
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
    """Compute leaf PSI and per-covariate CSI (train as reference).

    Parameters:
        eps: epsilon floor applied to probabilities before the log.
        renormalize: forwarded to psi_index on every internal call. If True,
            both probability vectors are renormalized to sum 1 after the
            eps clip (canonical mode); if False (default), the clip is
            applied without renormalization (deliberate MRM decision, see
            design_decisions.md section 7.4). The default preserves the
            legacy numeric behavior exactly.
        logger: optional logger; defaults to the "stability" logger.
    """

    def __init__(
        self,
        *,
        eps: float = _EPS_DEFAULT,
        renormalize: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        if not isinstance(renormalize, bool):
            raise ValueError(
                f"renormalize debe ser bool (recibido {renormalize!r})"
            )
        self.eps = float(eps)
        self.renormalize = bool(renormalize)
        self._log = logger if logger is not None else get_logger("stability")

    # ------------------------------------------------------------------

    def leaf_psi(
        self,
        model: TreeModel,
        leaf_counts_train: np.ndarray,
        leaf_assign_oot: np.ndarray,
        *,
        leaf_weights_train: np.ndarray | None = None,
        weights_oot: np.ndarray | None = None,
    ) -> PSIReport:
        """PSI sobre la distribucion de hojas del arbol.

        leaf_counts_train: tamanios de las hojas en train (orden node_id).
        leaf_assign_oot: node_id de hoja por fila OOT; -1 = no asignable
        (va a un bin extra "<UNSEEN>" con p_expected=eps).

        Fase 3.2.h (ponderacion): convencion "cada cohorte con sus propios
        pesos" (diseno v2 §5.3 B4, opcion 1). Con `leaf_weights_train`,
        p_exp = masa ponderada por hoja / masa total train. Con
        `weights_oot`, los conteos por hoja pasan a ser sumas de pesos OOT
        (el bin <UNSEEN> acumula la suma de pesos de las filas no
        asignables). Con ambos None, comportamiento identico al pre-3.2.
        """
        w_tr = _validated_weights(
            leaf_weights_train, len(leaf_counts_train), "leaf_psi/train"
        )
        w_oot = _validated_weights(
            weights_oot, len(leaf_assign_oot), "leaf_psi/oot"
        )
        hojas = [nd for nd in model.nodes if nd.is_leaf]
        leaf_ids = [nd.node_id for nd in hojas]
        if w_tr is None:
            n_train = int(leaf_counts_train.sum())
            p_exp = leaf_counts_train.astype(float) / n_train
        else:
            p_exp = w_tr / w_tr.sum()

        n_oot_total = int(leaf_assign_oot.size)
        mask_ok = leaf_assign_oot >= 0
        asignadas = leaf_assign_oot[mask_ok]
        counts = np.zeros(len(hojas), dtype=float)
        if w_oot is None:
            for i, nid in enumerate(leaf_ids):
                counts[i] = float((asignadas == nid).sum())
            n_excluidas = n_oot_total - int(asignadas.size)
            masa_excluidas = float(n_excluidas)
            total_act = float(n_oot_total)
        else:
            for i, nid in enumerate(leaf_ids):
                counts[i] = float(w_oot[mask_ok][asignadas == nid].sum())
            n_excluidas = n_oot_total - int(asignadas.size)
            masa_excluidas = float(w_oot[~mask_ok].sum())
            total_act = float(w_oot.sum())

        etiquetas = [f"leaf_{nid}" for nid in leaf_ids]
        if n_excluidas > 0:
            self._log.info(
                "[stability] PSI: %d filas OOT sin hoja -> bin '<UNSEEN>'",
                n_excluidas,
            )
            etiquetas.append("<UNSEEN>")
            p_exp = np.concatenate([p_exp, [0.0]])
            counts = np.concatenate([counts, [masa_excluidas]])
        p_act = counts / max(total_act, 1)

        psi, contrib = psi_index(p_exp, p_act, renormalize=self.renormalize)
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
        *,
        weights_train: np.ndarray | None = None,
        weights_actual: np.ndarray | None = None,
    ) -> CSIReport:
        """CSI por covariable (train = referencia).

        Continua/ordinal numerico: deciles aprendidos SOLO en train
        (primer y ultimo bin abiertos: -inf / +inf absorven desbordes).
        Nominal u ordinal simbolico: categorias observadas en train;
        las nuevas en OOT se agrupan en <OTHER> con p_expected=eps.

        Fase 3.2.h (ponderacion): convencion "cada cohorte con sus propios
        pesos". La asignacion a bins NO cambia; los conteos por bin pasan
        a ser sumas de pesos cuando hay pesos (el bin <OTHER> acumula la
        suma de pesos de las filas con categoria nueva). Con ambos None,
        comportamiento identico al pre-3.2.
        """
        x_tr = X_train[predictor]
        x_ac = X_actual[predictor]
        n_tr = int(len(x_tr))
        n_ac = int(len(x_ac))
        if n_tr == 0 or n_ac == 0:
            raise ValueError(f"[stability] CSI {predictor!r}: columna vacia")
        w_tr = _validated_weights(weights_train, n_tr, f"csi/{predictor}/train")
        w_ac = _validated_weights(weights_actual, n_ac, f"csi/{predictor}/actual")

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
            if w_tr is None:
                p_exp = np.array(
                    [float((bins_tr == i).sum()) for i in range(len(etiquetas))],
                    dtype=float,
                ) / n_tr
            else:
                p_exp = np.array(
                    [float(w_tr[bins_tr == i].sum()) for i in range(len(etiquetas))],
                    dtype=float,
                ) / w_tr.sum()
            if w_ac is None:
                p_act = np.array(
                    [float((bins_ac == i).sum()) for i in range(len(etiquetas))],
                    dtype=float,
                ) / n_ac
            else:
                p_act = np.array(
                    [float(w_ac[bins_ac == i].sum()) for i in range(len(etiquetas))],
                    dtype=float,
                ) / w_ac.sum()
        else:
            clases_tr = list(dict.fromkeys(x_tr.dropna().tolist()))
            if w_tr is None:
                p_exp = np.array(
                    [float((x_tr == c).sum()) for c in clases_tr], dtype=float
                ) / n_tr
            else:
                p_exp = np.array(
                    [float(w_tr[(x_tr == c).to_numpy()].sum()) for c in clases_tr],
                    dtype=float,
                ) / w_tr.sum()
            p_act_parts = []
            # numpy puro (booleano): evita el dtype mixto Series |= ndarray
            visto = np.zeros(len(x_ac), dtype=bool)
            for c in clases_tr:
                m = (x_ac == c).to_numpy()
                if w_ac is None:
                    p_act_parts.append(float(m.sum()))
                else:
                    p_act_parts.append(float(w_ac[m].sum()))
                visto |= m
            total_act = float(n_ac) if w_ac is None else float(w_ac.sum())
            p_act = np.array(p_act_parts, dtype=float) / total_act
            etiquetas = [str(c) for c in clases_tr]
            n_otros = int((~visto).sum())
            if n_otros > 0:
                self._log.info(
                    "[stability] CSI %r: %d filas con categorias nuevas -> <OTHER>",
                    predictor, n_otros,
                )
                etiquetas.append("<OTHER>")
                p_exp = np.concatenate([p_exp, [0.0]])
                if w_ac is None:
                    masa_otros = float(n_otros)
                else:
                    masa_otros = float(w_ac[~visto].sum())
                p_act = np.concatenate([p_act, [masa_otros / total_act]])

        csi, contrib = psi_index(p_exp, p_act, renormalize=self.renormalize)
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
        *,
        weights_train: np.ndarray | None = None,
        weights_actual: np.ndarray | None = None,
    ) -> tuple[PSIReport, tuple[CSIReport, ...]]:
        """PSI de hojas + CSI de todas las covariables.

        Fase 3.2.h: con `weights_train`/`weights_actual`, propaga la
        ponderacion a leaf_psi (calculando la masa por hoja de train
        internamente) y a cada covariate_csi. Convencion: cada cohorte
        usa sus propios pesos.
        """
        w_tr = _validated_weights(
            weights_train, len(leaf_assign_train), "report/train"
        )
        w_ac = _validated_weights(
            weights_actual, len(leaf_assign_actual), "report/actual"
        )
        hojas = [nd for nd in model.nodes if nd.is_leaf]
        leaf_ids = [nd.node_id for nd in hojas]
        counts = np.array(
            [float((leaf_assign_train == nid).sum()) for nid in leaf_ids]
        )
        if w_tr is None:
            leaf_weights_train = None
        else:
            leaf_weights_train = np.array(
                [float(w_tr[leaf_assign_train == nid].sum()) for nid in leaf_ids]
            )
        psi = self.leaf_psi(
            model, counts, leaf_assign_actual,
            leaf_weights_train=leaf_weights_train,
            weights_oot=w_ac,
        )
        csi = tuple(
            self.covariate_csi(
                X_train, X_actual, name, ptype,
                weights_train=w_tr, weights_actual=w_ac,
            )
            for name, ptype in spec.items()
        )
        return psi, csi
