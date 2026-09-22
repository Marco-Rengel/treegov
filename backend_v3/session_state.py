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
from .profiling import infer_spec
from .pruning import Pruner
from .splitting import stratified_split
from .tree_builder import TreeBuilder, TreeModel
from .types import PredictorType, TargetType
from .validation import OOSMetrics, compute_oos_metrics, predict_pd

__all__ = ["FlowState", "SessionState", "Session"]


class FlowState(Enum):
    """Estados del pipeline transaccional de TreeGov."""

    EMPTY = auto()
    DATA_LOADED = auto()
    SPEC_FIXED = auto()
    PARTITIONED = auto()
    TRAINED = auto()


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
        idx_tr, idx_te = stratified_split(
            self._df[st.target], train_frac, seed, self._log
        )
        X = self._df[[c for c in self._df.columns if c != st.target]]
        X_train = X.iloc[idx_tr].reset_index(drop=True)
        X_test = X.iloc[idx_te].reset_index(drop=True)
        y_train = self._df[st.target].iloc[idx_tr].astype(int).reset_index(drop=True)

        imp = TrainOnlyImputer(logger=get_logger("imputation"))
        imp.fit(X_train, dict(st.spec))        # SOLO train (tuple -> dict)
        self._X_train = imp.transform(X_train)
        self._X_test = imp.transform(X_test)   # aplica reglas de train
        self._y_train = y_train
        self._y_test = self._df[st.target].iloc[idx_te].astype(int).to_numpy()
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
