"""Estado de sesion transaccional con estado cero (TreeGov, backend_v3, Fase 1).

Maquina de estados del flujo analitico completo:

    EMPTY -> DATA_LOADED -> SPEC_FIXED -> PARTITIONED -> TRAINED

Reglas duras:
  - ESTADO CERO: SessionState() es el unico estado inicial valido; todos los
    artefactos son None explicitos y event_log inicia con
    ("init/state=EMPTY",). Consultarlo jamas lanza excepcion.
  - ATOMICIDAD: cada transicion calcula TODO antes de reemplazar el estado
    interno; si algo falla, el estado previo queda intacto y la excepcion
    se propaga (nunca un estado intermedio "a medias").
  - INMUTABILIDAD: SessionState es frozen; cada transicion produce un objeto
    nuevo (dataclasses.replace); la bitacora event_log es append-only por
    construccion (tuple += 1 elemento).
  - Bitacora doble (requisito P4): un evento en MEMORIA (event_log, sin
    timestamps -> determinista para tests) y otro en el archivo de log con
    prefijo "treegov.session" (el archivo lleva el timestamp ISO 8601).

Dependencias permitidas: numpy, pandas y los modulos propios de backend_v3.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, replace
from enum import Enum, auto

import numpy as np
import pandas as pd

from .imputation import TrainOnlyImputer
from .log_config import get_logger
from .pruning import Pruner
from .profiling import infer_spec
from .splitting import stratified_split
from .stability import OOTReport
from .tree_builder import TreeBuilder, TreeModel
from .types import PredictorType, TargetType
from .validation import (
    OOSMetrics, compute_oos_metrics, predict_leaf_assignment, predict_pd,
)

__all__ = ["FlowState", "SessionState", "Session"]


class FlowState(Enum):
    """Estados del pipeline transaccional de TreeGov."""

    EMPTY = auto()
    DATA_LOADED = auto()
    SPEC_FIXED = auto()
    PARTITIONED = auto()
    TRAINED = auto()
    OOT_LOADED = auto()      # cohorte temporal posterior cargada (Fase 1.3)
    OOT_EVALUATED = auto()   # metricas OOT + PSI/CSI + Gini Drop calculadas


@dataclass(frozen=True)
class SessionState:
    """Snapshot inmutable de la sesion. Estado cero: todos los artefactos None.

    Todos los campos son hashables e inmutables por construccion: el spec se
    almacena como tuple[(columna, PredictorType), ...] (orden del dict de
    origen, que es determinista) y los indices como tuplas de int.
    """

    state: FlowState = FlowState.EMPTY
    csv_path: str | None = None
    n_rows: int | None = None
    n_cols: int | None = None
    target: str | None = None
    target_classes: tuple = ()
    spec: tuple[tuple[str, PredictorType], ...] | None = None
    train_idx: tuple[int, ...] | None = None
    test_idx: tuple[int, ...] | None = None
    train_frac: float | None = None
    seed: int | None = None
    tree: TreeModel | None = None
    pruned_tree: TreeModel | None = None     # Fase 1.2: poda (reindexado)
    prune_alpha: float | None = None
    oos_metrics: OOSMetrics | None = None    # Fase 1.2: evaluacion del test
    n_oot: int | None = None                 # Fase 1.3: tama~no cohorte OOT
    temporal_verified: bool | None = None    # Fase 1.3: time_col confirmado
    oot_report: OOTReport | None = None      # Fase 1.3: metricas OOT + PSI/CSI
    oot_source: str | None = None            # origen declarado ('external-file')
    event_log: tuple[str, ...] = ("init/state=EMPTY",)


class Session:
    """Orquestador transaccional de la sesion (envoltorio de SessionState).

    Los datos pesados (DataFrame, matrices) se mantienen como cache interno
    NO exportado en el estado inmutable; el estado solo guarda metadatos e
    indices posicionales, todos hashables/deterministas.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._log = logger if logger is not None else get_logger("session")
        self._state = SessionState()
        self._df: pd.DataFrame | None = None
        self._X_train = None
        self._X_test = None
        self._y_train = None
        self._y_test = None
        self._imputer: TrainOnlyImputer | None = None  # fit solo-train (1.3 OOT)
        self._X_oot = None
        self._y_oot = None

    @property
    def state(self) -> SessionState:
        """Estado actual (inmutable)."""
        return self._state

    # ------------------------------------------------------------------
    # transiciones
    # ------------------------------------------------------------------

    def load_dataset(self, csv_path: str) -> SessionState:
        """EMPTY -> DATA_LOADED (lectura del CSV en modo solo lectura)."""
        self._require(FlowState.EMPTY, "load_dataset")
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(f"[session] dataset inexistente: {csv_path}")
        df = pd.read_csv(csv_path)
        if df.shape[0] == 0 or df.shape[1] == 0:
            raise ValueError(f"[session] dataset vacio: shape={df.shape}")
        self._df = df
        return self._commit(
            FlowState.DATA_LOADED,
            evento=f"load_dataset:{os.path.basename(csv_path)}"
                   f"|filas={df.shape[0]}|cols={df.shape[1]}",
            csv_path=csv_path, n_rows=df.shape[0], n_cols=df.shape[1],
        )

    def fix_spec(
        self, target: str, spec: dict[str, PredictorType] | None = None
    ) -> SessionState:
        """DATA_LOADED -> SPEC_FIXED. Target EXCLUSIVAMENTE binario (Fase 1).

        Si spec es None, se infiere con profiling.infer_spec.
        """
        self._require(FlowState.DATA_LOADED, "fix_spec")
        assert self._df is not None
        if target not in self._df.columns:
            raise ValueError(f"[session] target ausente: {target!r}")
        if not self._df[target].notna().all():
            raise ValueError(f"[session] target {target!r} contiene NaN")
        valores = sorted(pd.unique(self._df[target].dropna()))
        if len(valores) != 2:
            raise ValueError(
                f"[session] target {target!r} no binario: {len(valores)} clases"
            )
        if set(valores) != {0, 1}:
            raise ValueError(
                f"[session] target {target!r} debe estar codificado 0/1 "
                f"(evento=1); valores: {valores!r}"
            )
        if spec is None:
            spec = infer_spec(self._df, target, self._log)
        if not spec:
            raise ValueError("[session] spec vacio")
        return self._commit(
            FlowState.SPEC_FIXED,
            evento=f"fix_spec:{target}|predictores={len(spec)}",
            target=target, target_classes=tuple(int(v) for v in valores),
            spec=tuple(spec.items()),
        )

    def partition(self, train_frac: float = 0.7, seed: int = 42) -> SessionState:
        """SPEC_FIXED -> PARTITIONED (Hamilton-Hare + imputer SOLO train)."""
        self._require(FlowState.SPEC_FIXED, "partition")
        assert self._df is not None
        st = self._state
        assert st.target is not None and st.spec is not None
        spec_d = dict(st.spec)  # tuple inmutable -> dict para el imputer
        idx_tr, idx_te = stratified_split(
            self._df[st.target], train_frac, seed, self._log
        )
        X = self._df[[c for c in self._df.columns if c != st.target]]
        X_train = X.iloc[idx_tr].reset_index(drop=True)
        X_test = X.iloc[idx_te].reset_index(drop=True)
        y_train = self._df[st.target].iloc[idx_tr].astype(int).reset_index(drop=True)

        imp = TrainOnlyImputer(logger=get_logger("imputation"))
        imp.fit(X_train, spec_d)               # SOLO train
        self._X_train = imp.transform(X_train)
        self._X_test = imp.transform(X_test)   # aplica reglas de train
        self._y_train = y_train
        self._y_test = self._df[st.target].iloc[idx_te].astype(int).to_numpy()
        self._imputer = imp                    # retenido: lo usa load_oot (1.3)
        return self._commit(
            FlowState.PARTITIONED,
            evento=f"partition:frac={train_frac}|seed={seed}"
                   f"|train={len(idx_tr)}|test={len(idx_te)}",
            train_idx=tuple(int(i) for i in idx_tr),
            test_idx=tuple(int(i) for i in idx_te),
            train_frac=float(train_frac), seed=int(seed),
        )

    def train(
        self,
        engine,
        *,
        target_type: TargetType = TargetType.BINARY,
        max_depth: int = 4,
        min_child_size: int = 50,
        pd_floor: float = 0.0003,
    ) -> SessionState:
        """PARTITIONED -> TRAINED (TreeBuilder sobre train imputado)."""
        self._require(FlowState.PARTITIONED, "train")
        st = self._state
        assert st.spec is not None
        assert self._X_train is not None and self._y_train is not None
        builder = TreeBuilder(
            engine, target_type=target_type, max_depth=max_depth,
            min_child_size=min_child_size, pd_floor=pd_floor,
            seed=st.seed, logger=get_logger("builder"),
        )
        modelo = builder.build(self._X_train, self._y_train, dict(st.spec))
        return self._commit(
            FlowState.TRAINED,
            evento=f"train:{modelo.method}|nodos={len(modelo.nodes)}"
                   f"|fp={modelo.params_fingerprint}",
            tree=modelo,
        )

    def evaluate_oos(self, *, n_groups: int = 10) -> SessionState:
        """TRAINED -> TRAINED con oos_metrics rellenado (no cambia FlowState).

        X_test se asume imputado con TrainOnlyImputer (hecho en partition);
        el assert de filas sin hoja en predict_pd es defensa, no el caso
        esperado. Nunca toca datos de train.
        """
        self._require(FlowState.TRAINED, "evaluate_oos")
        st = self._state
        assert st.tree is not None
        assert self._X_test is not None and self._y_test is not None
        p = predict_pd(st.tree, self._X_test)
        metrics = compute_oos_metrics(p, self._y_test, n_groups=n_groups)
        return self._commit(
            st.state,
            evento=(
                f"evaluate_oos:gini="
                f"{'nan' if metrics.gini is None else format(metrics.gini, '.4g')}"
                f"|ks={'nan' if metrics.ks is None else format(metrics.ks, '.4g')}"
                f"|brier={metrics.brier:.6g}"
            ),
            oos_metrics=metrics,
        )

    def prune(self, alpha: float) -> SessionState:
        """TRAINED -> TRAINED con pruned_tree (poda coste-complejidad).

        Siempre parte del arbol ORIGINAL (idempotencia; la poda no apila).
        """
        self._require(FlowState.TRAINED, "prune")
        st = self._state
        assert st.tree is not None
        pruned = Pruner(logger=get_logger("pruning")).prune(st.tree, alpha)
        return self._commit(
            st.state,
            evento=f"prune:alpha={alpha:.6g}|nodos={len(st.tree.nodes)}"
                   f"->{len(pruned.nodes)}",
            pruned_tree=pruned, prune_alpha=float(alpha),
        )

    def load_oot(self, csv_path: str, *, time_col: str | None = None) -> SessionState:
        """TRAINED -> OOT_LOADED: ingesta de la cohorte temporal posterior.

        Gobernanza: el archivo es EXTERNO e independiente; la temporalidad
        se certifica solo si time_col existe en ambos datasets (si no,
        temporal_verified=False con WARNING explicito: es OOS, no OOT).
        La imputacion usa las reglas de train (anti-leakage estricto).
        """
        self._require(FlowState.TRAINED, "load_oot")
        st = self._state
        assert st.spec is not None and st.target is not None
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(f"[session] OOT inexistente: {csv_path}")
        df_oot = pd.read_csv(csv_path)
        if df_oot.shape[0] == 0:
            raise ValueError(f"[session] OOT vacio: {csv_path}")

        spec_keys = set(dict(st.spec).keys())
        esperadas = spec_keys | {st.target} | ({time_col} if time_col else set())
        got_keys = set(df_oot.columns)
        if got_keys != esperadas:
            raise ValueError(
                f"[session] columnas OOT difieren de spec+target: "
                f"faltan={sorted(esperadas - got_keys)} sobran={sorted(got_keys - esperadas)}"
            )
        if not df_oot[st.target].notna().all():
            raise ValueError(f"[session] target OOT con NaN: {st.target!r}")
        valores = sorted(pd.unique(df_oot[st.target]))
        if set(valores) != {0, 1}:
            raise ValueError(
                f"[session] target OOT fuera de 0/1: {valores!r}"
            )

        if self._imputer is None:
            raise RuntimeError(
                "[session] load_oot sin imputer: partition() no ejecutado"
            )
        # time_col es metadato temporal, NUNCA predictor: el X de OOT lleva
        # exactamente las columnas del spec (orden del spec, no alfabetico).
        spec_order = list(dict(st.spec).keys())
        X_oot = df_oot[spec_order]
        self._X_oot = self._imputer.transform(X_oot)
        self._y_oot = df_oot[st.target].astype(int).to_numpy()

        temporal_ok = False
        if time_col is not None:
            if time_col in self._df.columns and time_col in df_oot.columns:
                t_train_max = pd.to_datetime(self._df[time_col]).max()
                t_oot_min = pd.to_datetime(df_oot[time_col]).min()
                if not (t_oot_min > t_train_max):
                    raise ValueError(
                        f"[session] fuga temporal: OOT comienza {t_oot_min} "
                        f"<= maximo train {t_train_max}"
                    )
                temporal_ok = True
            else:
                self._log.warning(
                    "[session] time_col=%r no disponible en train/OOT: sin "
                    "verificacion temporal (OOS, not OOT)", time_col,
                )
        else:
            self._log.warning(
                "[session] load_oot sin time_col: cohorte no verificada "
                "temporalmente (OOS, not OOT)"
            )
        return self._commit(
            FlowState.OOT_LOADED,
            evento=f"load_oot:{os.path.basename(csv_path)}|n={len(df_oot)}"
                   f"|temporal_verified={temporal_ok}",
            n_oot=int(len(df_oot)), temporal_verified=temporal_ok,
            oot_source="external-file",
        )

    def evaluate_oot(self, *, n_groups: int = 10) -> SessionState:
        """OOT_LOADED -> OOT_EVALUATED: metricas OOT + Gini Drop + PSI/CSI.

        unseen_policy="exclude" (transparencia MRM): las filas no enrutables
        cuentan en n_excluded y forman su propio bin en PSI.
        """
        self._require(FlowState.OOT_LOADED, "evaluate_oot")
        from .stability import GiniDropReport, StabilityMonitor, gini_drop_alert

        st = self._state
        assert st.tree is not None and st.spec is not None
        assert self._X_oot is not None and self._y_oot is not None

        model = st.tree
        spec_d = dict(st.spec)

        asign_oot = predict_leaf_assignment(
            model, self._X_oot, unseen_policy="exclude"
        )
        validas = asign_oot >= 0
        n_val = int(validas.sum())
        n_exc = int((~validas).sum())

        # metricas OOT sobre las filas enrutables
        if n_val >= 15:
            p_val = np.array(
                [model.nodes[int(a)].pd_final for a in asign_oot[validas]]
            )
            g_eff = n_groups if n_val >= 5 * n_groups else max(3, n_val // 5)
            metrics = compute_oos_metrics(p_val, self._y_oot[validas],
                                          n_groups=g_eff)
        else:
            self._log.warning(
                "[session] OOT enrutable demasiado pequeno (%d): sin metricas",
                n_val,
            )
            metrics = None
        gini_oot = None if metrics is None else metrics.gini

        # Gini train / oos (oos desde state si existe; si no, al vuelo)
        asign_tr = predict_leaf_assignment(
            model, self._X_train, unseen_policy="error"
        )
        p_tr = np.array([model.nodes[int(a)].pd_final for a in asign_tr])
        n_tr = int(len(p_tr))
        g_eff_tr = min(5, max(3, n_tr // 5))
        m_tr = compute_oos_metrics(p_tr, self._y_train.to_numpy(),
                                   n_groups=g_eff_tr)
        gini_train = m_tr.gini if m_tr.gini is not None else float("nan")

        if st.oos_metrics is not None:
            gini_oos = st.oos_metrics.gini
        else:
            asign_te = predict_leaf_assignment(
                model, self._X_test, unseen_policy="error"
            )
            p_te = np.array([model.nodes[int(a)].pd_final for a in asign_te])
            n_te_eff = max(3, int(len(p_te)) // 5)
            gini_oos = compute_oos_metrics(
                p_te, self._y_test, n_groups=n_te_eff
            ).gini

        def _drop(g):
            # None, NaN o Gini_train == 0 -> indefinido (NUNCA se reporta
            # silenciosamente como 'sin alerta': gini_drop_alert -> INDETERMINADO)
            if (gini_train is None or gini_train != gini_train
                    or gini_train == 0 or g is None):
                self._log.warning(
                    "[session] Gini Drop indefinido (train=%s, X=%s)", gini_train, g
                )
                return None
            return float((gini_train - g) / gini_train)

        drop_oos = _drop(gini_oos)
        drop_oot = _drop(gini_oot)
        drop_report = GiniDropReport(
            gini_train=float(gini_train),
            gini_oos=gini_oos, gini_oot=gini_oot,
            drop_oos=drop_oos, drop_oot=drop_oot,
            alert_oos=gini_drop_alert(drop_oos),
            alert_oot=gini_drop_alert(drop_oot),
            temporal_verified=bool(st.temporal_verified),
        )

        monitor = StabilityMonitor(logger=get_logger("stability"))
        psi, csi = monitor.report(
            model, self._X_train, self._X_oot, asign_tr, asign_oot, spec_d
        )

        reporte = OOTReport(
            metrics=metrics, drop=drop_report, psi=psi, csi=csi,
            n_oot=int(st.n_oot or 0), n_excluded=n_exc,
        )
        narrativa = "OOT" if st.temporal_verified else "OOS-no-verificado"
        return self._commit(
            FlowState.OOT_EVALUATED,
            evento=(
                f"evaluate_oot:{narrativa}|n={n_val}|excluidas={n_exc}"
                f"|drop_oot={'nan' if drop_oot is None else format(drop_oot, '.4g')}"
                f"|psi={psi.psi:.4g}({psi.flag})"
            ),
            oot_report=reporte,
        )

    # ------------------------------------------------------------------

    def _require(self, esperado: FlowState, accion: str) -> None:
        if self._state.state is not esperado:
            raise ValueError(
                f"[session] transicion ilegal '{accion}' en estado "
                f"{self._state.state.name} (requiere {esperado.name})"
            )

    def _commit(self, nuevo: FlowState, evento: str, **campos) -> SessionState:
        """Transicion atomica: construye y reemplaza el estado, y bitacora."""
        event_log = (*self._state.event_log, evento)
        self._state = replace(self._state, state=nuevo, event_log=event_log,
                              **campos)
        self._log.info("[session] %s | estado=%s", evento, nuevo.name)
        return self._state
