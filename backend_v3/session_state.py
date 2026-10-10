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
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from enum import Enum, auto
from typing import Any

import numpy as np
import pandas as pd

from .chaid_engine import ChaidEngine
from .crt_engine import CrtEngine
from .imputation import TrainOnlyImputer
from .log_config import get_logger
from .profiling import _infer_column, infer_spec  # _infer_column: reuso interno backend
from .pruning import Pruner
from .quest_engine import QuestEngine
from .reporting import (
    build_classification_matrix,
    build_gains_table,
    build_oos_oot_report,
)
from .splitting import stratified_split
from .stability import OOTReport
from .tree_builder import TreeBuilder, TreeModel
from .types import PredictorType, TargetType
from .validation import (
    OOSMetrics, compute_oos_metrics, predict_leaf_assignment, predict_pd,
)

__all__ = ["FlowState", "SessionState", "Session"]

# Factoria de motores por nombre (Fase 2.1): el frontend/MCP nunca instancia
# motores directamente (sala limpia); invocan Session.train("CRT", ...).
_ENGINE_FACTORIES = {
    "CHAID": ChaidEngine,
    "CHAID_EXHAUSTIVE": lambda: ChaidEngine(exhaustive=True),
    "CRT": CrtEngine,
    "QUEST": QuestEngine,
}


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
    target_class: int | str | None = None    # Fase 3.1.c: clase de interes
    class_labels: tuple[tuple[int | str, str], ...] = ()  # (valor, etiqueta)
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
        # Caches de ponderacion por muestra (Fase 3.2)
        self._w_train: np.ndarray | None = None
        self._w_test: np.ndarray | None = None
        self._w_oot: np.ndarray | None = None
        self._w_col: str | None = None

    @property
    def state(self) -> SessionState:
        """Estado actual (inmutable)."""
        return self._state

    @property
    def class_labels_dict(self) -> dict[int | str, str]:
        """Vista dict del mapping clase -> etiqueta humana
        (conveniencia para GUI/MCP). Vacío antes de fix_spec."""
        return dict(self._state.class_labels)

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

    # ------------------------------------------------------------------
    # lecturas puras (sin transicion de estado)
    # ------------------------------------------------------------------

    def describe_dataset(self) -> tuple[tuple[str, ...], dict[str, str]]:
        """Columnas y tipos inferidos del dataset cargado (lectura pura).

        Pensado para GUI/MCP (Fase 2.1): tras load_dataset permite poblar
        selectores de target/predictores sin exponer el DataFrame ni el
        enum PredictorType (los tipos viajan como strings .name).
        """
        if self._df is None:
            raise RuntimeError("[session] describe_dataset sin dataset cargado")
        cols = tuple(str(c) for c in self._df.columns)
        tipos = {str(c): _infer_column(self._df[c]).name for c in self._df.columns}
        self._log.info("[session] describe_dataset: %d columnas", len(cols))
        return cols, tipos

    def describe_target(self, target: str) -> dict:
        """Frecuencia por valor observado en la columna target
        (lectura pura, sin transicion de estado).

        Pensado para GUI/MCP (Fase 3.1.e): tras load_dataset permite
        poblar el combo de clase de interes con las clases observadas
        y sus counts, sin exponer el DataFrame ni pandas.

        Returns:
            dict {valor_observado: frecuencia}, ordenado por valor
            ascendente. Los valores conservan su tipo original (int,
            str, etc.). Las filas con NaN en el target se ignoran.

        Raises:
            RuntimeError: sin dataset cargado.
            ValueError: target no es una columna del dataset.
        """
        if self._df is None:
            raise RuntimeError(
                "[session] describe_target sin dataset cargado"
            )
        if target not in self._df.columns:
            raise ValueError(
                f"[session] describe_target: columna ausente {target!r}"
            )
        vc = self._df[target].value_counts(dropna=True)
        ordenado = sorted(vc.items(), key=lambda kv: kv[0])
        return {k: int(v) for k, v in ordenado}

    def _routed_partition(self, partition: str) -> tuple[Any, Any, str]:
        """Resolve a partition name to its cached (X, y) and unseen policy.

        Routing contract: "train" uses the strict "error" unseen policy
        (every row must route), while "oos"/"oot" use "exclude" (unroutable
        rows are reported, never silently dropped). Raises ValueError if no
        model is trained or the partition name is unknown; RuntimeError if
        the chosen partition cache has not been populated yet.
        """
        if self._state.tree is None:
            raise ValueError("[session] partition requiere un modelo entrenado")
        if partition == "train":
            X, y, unseen_policy = self._X_train, self._y_train, "error"
        elif partition == "oos":
            X, y, unseen_policy = self._X_test, self._y_test, "exclude"
        elif partition == "oot":
            X, y, unseen_policy = self._X_oot, self._y_oot, "exclude"
        else:
            raise ValueError(
                f"[session] partition invalida: {partition!r} "
                f"(validas: ['train', 'oos', 'oot'])"
            )
        if X is None or y is None:
            raise RuntimeError(
                f"[session] partition={partition!r} sin datos en cache"
            )
        return X, y, unseen_policy

    def get_oos_oot_report(self) -> dict | None:
        """DTO plain-Python del estado OOS/OOT (None si no hay modelo)."""
        return build_oos_oot_report(self._state)

    def get_gains_table(
        self,
        *,
        partition: str = "oos",
        by: str = "leaf",
        n_buckets: int = 10,
        tie: str = "preserve",
        seed: int | None = None,
    ) -> dict[str, Any] | None:
        """Gains table DTO for a routed partition (None if no model trained).

        Read-only consumer of reporting.build_gains_table: routes the rows
        of the requested partition through the trained tree and returns the
        result as a plain-Python dict (asdict), so GUI/MCP never touch
        backend dataclasses.
        """
        if self._state.tree is None:
            return None
        X, y, unseen_policy = self._routed_partition(partition)
        leaf_assignment = predict_leaf_assignment(
            self._state.tree, X, unseen_policy=unseen_policy
        )
        result = build_gains_table(
            self._state.tree, leaf_assignment, y,
            by=by, n_buckets=n_buckets, tie=tie, seed=seed,
        )
        self._log.info(
            "[session] get_gains_table: partition=%s by=%s n=%d",
            partition, by, result.n_total,
        )
        return asdict(result)

    def get_classification_matrix(
        self, *, partition: str = "oos", threshold: float = 0.5
    ) -> dict[str, Any] | None:
        """Classification matrix DTO for a routed partition (None if no model).

        Read-only consumer of reporting.build_classification_matrix: leaf
        PDs are taken from the trained tree (pd_final per leaf node) and
        the result travels as a plain-Python dict (asdict), so GUI/MCP
        never touch backend dataclasses.
        """
        if self._state.tree is None:
            return None
        K = len(self._state.tree.class_labels)
        if K > 2:
            raise ValueError(
                f"[session] get_classification_matrix: clasificacion "
                f"multiclase no implementada en Fase 3.1 (K={K} clases "
                f"detectadas). Planificada para la Fase 3.5."
            )
        X, y, unseen_policy = self._routed_partition(partition)
        leaf_assignment = predict_leaf_assignment(
            self._state.tree, X, unseen_policy=unseen_policy
        )
        # Phase 3.1: pd_final is a per-class tuple; index 0 is the class of interest.
        pd_per_leaf = {
            nd.node_id: nd.pd_final[0]
            for nd in self._state.tree.nodes if nd.is_leaf
        }
        result = build_classification_matrix(
            leaf_assignment, y, pd_per_leaf, threshold=threshold
        )
        self._log.info(
            "[session] get_classification_matrix: partition=%s threshold=%.4g",
            partition, threshold,
        )
        return asdict(result)

    def reset_to_data_loaded(self) -> SessionState:
        """Vuelve a DATA_LOADED conservando el DataFrame en cache.

        Uso (GUI, Fase 2.1): rehacer el flujo (nuevo target/predictores o
        nueva particion) tras un modelo ya entrenado o un fallo en una
        transicion posterior, SIN releer el CSV. Los artefactos y caches
        posteriores a DATA_LOADED se descartan (defensivo), incluidas las
        caches de ponderacion por muestra (_w_train/_w_test/_w_oot/_w_col).
        """
        if self._df is None:
            raise ValueError("[session] reset_to_data_loaded en estado EMPTY")
        self._X_train = self._X_test = None
        self._y_train = self._y_test = None
        self._imputer = None
        self._X_oot = self._y_oot = None
        self._w_train = self._w_test = self._w_oot = None
        self._w_col = None
        self._state = SessionState(
            state=FlowState.DATA_LOADED,
            csv_path=self._state.csv_path,
            n_rows=self._state.n_rows,
            n_cols=self._state.n_cols,
            event_log=(*self._state.event_log, "reset_to_data_loaded"),
        )
        self._log.info("[session] reset_to_data_loaded | estado=DATA_LOADED")
        return self._state

    def fix_spec(
        self, target: str, spec: dict[str, PredictorType] | None = None,
        *, predictors: Sequence[str] | None = None,
        target_class: int | str,
        class_labels: Mapping[int | str, str],
        weight_col: str | None = None,
    ) -> SessionState:
        """DATA_LOADED -> SPEC_FIXED. Target binario 0/1 o multiclase (3.1.c).

        Si spec es None, se infiere con profiling.infer_spec.
        Si se pasa `predictors` (Fase 2.1, GUI wizard), el spec resuelto se
        filtra a ese subconjunto; el filtrado vive AQUI (la GUI jamas toca
        el enum PredictorType).
        `target_class` y `class_labels` son obligatorios: la clase
        de interes y las etiquetas humanas por clase.

        `weight_col` (Fase 3.2, opcional): nombre de la columna de pesos
        por muestra. Si se declara, se valida ANTES de la transicion
        (atomicidad): existe en el dataset, no es el target, no es un
        predictor declarado, es numerica (no bool ni object/string), sin
        NaN, y todos los valores estrictamente positivos. Si es None, la
        sesion queda en modo no ponderado (comportamiento identico al
        pre-3.2).
        """
        self._require(FlowState.DATA_LOADED, "fix_spec")
        assert self._df is not None
        if target not in self._df.columns:
            raise ValueError(f"[session] target ausente: {target!r}")
        if not self._df[target].notna().all():
            raise ValueError(f"[session] target {target!r} contiene NaN")
        valores = sorted(pd.unique(self._df[target].dropna()))
        if len(valores) < 2:
            raise ValueError(
                f"[session] target {target!r} constante: "
                f"{len(valores)} clase(s)"
            )
        if len(valores) == 2 and set(valores) != {0, 1}:
            raise ValueError(
                f"[session] target binario {target!r} debe estar "
                f"codificado 0/1 (evento=1); para otra codificacion, "
                f"recodificar antes de cargar. Valores observados: "
                f"{valores!r}"
            )
        # K >= 3: cualquier codificacion es valida.
        if target_class not in valores:
            raise ValueError(
                f"[session] target_class {target_class!r} no esta entre "
                f"las clases observadas: {valores!r}"
            )
        if not isinstance(class_labels, Mapping):
            raise TypeError("[session] class_labels debe ser un Mapping")
        claves = set(class_labels.keys())
        faltan = sorted(set(valores) - claves)
        if faltan:
            raise ValueError(
                f"[session] class_labels no cubre las clases observadas; "
                f"faltan: {faltan!r}"
            )
        sobran = sorted(claves - set(valores))
        if sobran:
            raise ValueError(
                f"[session] class_labels contiene claves no observadas: "
                f"{sobran!r}"
            )
        for k, v in class_labels.items():
            if not isinstance(v, str) or not v:
                raise ValueError(
                    f"[session] class_labels[{k!r}] debe ser un string "
                    f"no vacio"
                )
        labels = list(class_labels.values())
        if len(set(labels)) != len(labels):
            self._log.warning(
                "[session] class_labels con etiquetas duplicadas: %r", labels
            )
        if spec is None:
            spec = infer_spec(self._df, target, self._log)
        if predictors is not None:
            sel = {str(p) for p in predictors}
            if target in sel:
                raise ValueError(
                    f"[session] el target {target!r} no puede ser predictor"
                )
            faltantes = sorted(sel - set(spec))
            if faltantes:
                raise ValueError(
                    f"[session] predictores ausentes en el dataset: {faltantes!r}"
                )
            spec = {k: v for k, v in spec.items() if k in sel}
        if not spec:
            raise ValueError("[session] spec vacio")
        # --- Ponderacion por muestra (Fase 3.2): validacion atomica ---
        if weight_col is not None:
            if weight_col not in self._df.columns:
                raise ValueError(
                    f"[session] weight_col ausente en el dataset: "
                    f"{weight_col!r}"
                )
            if weight_col == target:
                raise ValueError(
                    f"[session] weight_col {weight_col!r} no puede ser "
                    f"el target"
                )
            if predictors is not None and weight_col in {str(p) for p in predictors}:
                raise ValueError(
                    f"[session] weight_col {weight_col!r}: la columna de "
                    f"pesos no puede ser predictor"
                )
            col_w = self._df[weight_col]
            if pd.api.types.is_bool_dtype(col_w) or not pd.api.types.is_numeric_dtype(col_w):
                raise ValueError(
                    f"[session] weight_col {weight_col!r} debe ser "
                    f"numerica (int o float); dtype observado: {col_w.dtype}"
                )
            if col_w.isna().any():
                raise ValueError(
                    f"[session] weight_col {weight_col!r} contiene NaN"
                )
            wvals = col_w.to_numpy(dtype=float)
            if not (wvals > 0).all():
                n_bad = int((wvals <= 0).sum())
                first_bad = int(np.flatnonzero(wvals <= 0)[0])
                raise ValueError(
                    f"[session] weight_col {weight_col!r}: {n_bad} valor(es) "
                    f"<= 0 (primero en la fila {first_bad}); los pesos "
                    f"deben ser estrictamente positivos"
                )
            self._w_col = weight_col
        else:
            self._w_col = None
        evento = f"fix_spec:{target}|predictores={len(spec)}"
        if self._w_col is not None:
            evento += f"|weight_col={self._w_col}"
        return self._commit(
            FlowState.SPEC_FIXED,
            evento=evento,
            target=target, target_classes=tuple(valores),
            target_class=target_class,
            class_labels=tuple(sorted(class_labels.items())),
            spec=tuple(spec.items()),
        )

    def partition(self, train_frac: float = 0.7, seed: int = 42) -> SessionState:
        """SPEC_FIXED -> PARTITIONED (Hamilton-Hare + imputer SOLO train).

        Fase 3.2: si fix_spec declaro `weight_col`, los pesos se pasan a
        stratified_split (cuotas por masa ponderada, check B2 activo) y se
        materializan los sub-vectores `_w_train`/`_w_test`. Sin weight_col,
        comportamiento identico al pre-3.2.
        """
        self._require(FlowState.SPEC_FIXED, "partition")
        assert self._df is not None
        st = self._state
        assert st.target is not None and st.spec is not None
        spec_d = dict(st.spec)  # tuple inmutable -> dict para el imputer
        w: np.ndarray | None = None
        if self._w_col is not None:
            w = self._df[self._w_col].to_numpy(dtype=float)
        idx_tr, idx_te = stratified_split(
            self._df[st.target], train_frac, seed, self._log, weights=w
        )
        if w is not None:
            self._w_train = w[idx_tr]
            self._w_test = w[idx_te]
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
        evento = (f"partition:frac={train_frac}|seed={seed}"
                  f"|train={len(idx_tr)}|test={len(idx_te)}")
        if w is not None:
            evento += "|weighted=true"
        return self._commit(
            FlowState.PARTITIONED,
            evento=evento,
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
        pd_floor: float | None = 0.0003,
        apply_jeffreys: bool = True,
    ) -> SessionState:
        """PARTITIONED -> TRAINED (TreeBuilder sobre train imputado).

        `engine` puede ser una instancia con best_split() o su nombre
        ("CHAID" | "CHAID_EXHAUSTIVE" | "CRT" | "QUEST"); la factoria
        interna (Fase 2.1) permite al frontend/MCP invocar por nombre sin
        importar motores (sala limpia).

        Gobernanza (types.GovernanceMode): los defaults son BANKING
        (Jeffreys + PD Floor, BCBS CRE 20.39); apply_jeffreys=False con
        pd_floor=None produce el modo RESEARCH (PD cruda k/n).

        Fase 3.1.c: la clase de interes y las etiquetas canonicas se leen
        de SessionState (fijadas en fix_spec). La clase de interes se lee
        exclusivamente de SessionState (fijada en fix_spec). Solo CHAID /
        CHAID_EXHAUSTIVE admiten K > 2 clases en esta fase.

        Fase 3.2: si la sesion esta ponderada (fix_spec con weight_col),
        los pesos de train (`_w_train`) se propagan a TreeBuilder junto
        con `weight_col` para el fingerprint.
        """
        self._require(FlowState.PARTITIONED, "train")
        st = self._state
        assert st.spec is not None
        assert self._X_train is not None and self._y_train is not None
        K = len(st.target_classes)
        if isinstance(engine, str):
            engine_name = engine
        elif isinstance(engine, ChaidEngine):
            engine_name = "CHAID_EXHAUSTIVE" if engine.exhaustive else "CHAID"
        elif isinstance(engine, CrtEngine):
            engine_name = "CRT"
        elif isinstance(engine, QuestEngine):
            engine_name = "QUEST"
        else:
            engine_name = type(engine).__name__
        # Bloqueo multiclase previo a instanciar nada (atomicidad).
        if K > 2 and engine_name not in ("CHAID", "CHAID_EXHAUSTIVE"):
            raise ValueError(
                f"[session] engine {engine_name!r} no soporta targets "
                f"multiclase en Fase 3.1 (K={K} clases detectadas). "
                f"Use CHAID o CHAID_EXHAUSTIVE para multiclase, o espere "
                f"a la Fase 3.4."
            )
        # Fase 3.1.c paso 4: SessionState es la unica fuente de verdad.
        # El endurecimiento de fix_spec garantiza target_class no-None.
        target_class = st.target_class
        if target_class is None:
            raise RuntimeError(
                "[session] train sin target_class en SessionState "
                "(fix_spec no ejecutado o estado corrupto)"
            )
        if isinstance(engine, str):
            try:
                engine = _ENGINE_FACTORIES[engine]()
            except KeyError:
                raise ValueError(
                    f"[session] motor desconocido: {engine!r} "
                    f"(validos: {sorted(_ENGINE_FACTORIES)})"
                ) from None
        # Etiquetas canonicas: primero la clase de interes, luego el resto
        # ordenado por valor original.
        labels_map = dict(st.class_labels)
        target_label = labels_map[target_class]
        resto = tuple(
            labels_map[c]
            for c in sorted(c for c in labels_map if c != target_class)
        )
        class_labels_canonical = (target_label,) + resto
        builder = TreeBuilder(
            engine, target_type=target_type, target_class=target_class,
            class_labels=class_labels_canonical,
            max_depth=max_depth,
            min_child_size=min_child_size, pd_floor=pd_floor,
            apply_jeffreys=apply_jeffreys,
            weights=self._w_train, weight_col=self._w_col,
            seed=st.seed, logger=get_logger("builder"),
        )
        modelo = builder.build(self._X_train, self._y_train, dict(st.spec))
        evento = (f"train:{modelo.method}|nodos={len(modelo.nodes)}"
                  f"|fp={modelo.params_fingerprint}")
        if self._w_col is not None:
            evento += f"|weighted=true,weight_col={self._w_col}"
        return self._commit(
            FlowState.TRAINED,
            evento=evento,
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
        K = len(st.tree.class_labels)
        if K > 2:
            raise ValueError(
                f"[session] evaluate_oos: metricas multiclase no "
                f"implementadas en Fase 3.1 (K={K} clases detectadas). "
                f"Planificadas para la Fase 3.5."
            )
        p_2d = predict_pd(st.tree, self._X_test)
        p = p_2d[:, 0]  # Phase 3.1.d: binary consumers read column 0
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

        Fase 3.2: si la sesion esta ponderada (fix_spec con weight_col),
        el CSV OOT debe incluir esa columna; el vector se materializa en
        `_w_oot` y se valida (finito, estrictamente positivo).
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
        if self._w_col is not None:
            esperadas = esperadas | {self._w_col}
        got_keys = set(df_oot.columns)
        if got_keys != esperadas:
            raise ValueError(
                f"[session] columnas OOT difieren de spec+target: "
                f"faltan={sorted(esperadas - got_keys)} sobran={sorted(got_keys - esperadas)}"
            )
        if not df_oot[st.target].notna().all():
            raise ValueError(f"[session] target OOT con NaN: {st.target!r}")
        valores = sorted(pd.unique(df_oot[st.target]))
        # Fase 3.1.d: el target OOT debe cubrir exactamente las clases del
        # spec (para K=2, target_classes == (0, 1): comportamiento identico
        # al chequeo pre-3.1 "fuera de 0/1").
        if set(valores) != set(st.target_classes):
            raise ValueError(
                f"[session] target OOT no coincide con las clases del "
                f"spec: {valores!r} vs {sorted(st.target_classes)!r}"
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

        if self._w_col is not None:
            w_oot = df_oot[self._w_col].to_numpy(dtype=float)
            if not np.isfinite(w_oot).all():
                raise ValueError(
                    f"[session] weight_col OOT {self._w_col!r} contiene "
                    f"valores no finitos"
                )
            if not (w_oot > 0).all():
                n_bad = int((w_oot <= 0).sum())
                first_bad = int(np.flatnonzero(w_oot <= 0)[0])
                raise ValueError(
                    f"[session] weight_col OOT {self._w_col!r}: "
                    f"{n_bad} valor(es) <= 0 (primero en la fila "
                    f"{first_bad}); los pesos deben ser estrictamente "
                    f"positivos"
                )
            self._w_oot = w_oot

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
        evento = (f"load_oot:{os.path.basename(csv_path)}|n={len(df_oot)}"
                  f"|temporal_verified={temporal_ok}")
        if self._w_col is not None:
            evento += "|weighted=true"
        return self._commit(
            FlowState.OOT_LOADED,
            evento=evento,
            n_oot=int(len(df_oot)), temporal_verified=temporal_ok,
            oot_source="external-file",
        )

    def evaluate_oot(self, *, n_groups: int = 10) -> SessionState:
        """OOT_LOADED -> OOT_EVALUATED: metricas OOT + Gini Drop + PSI/CSI.

        unseen_policy="exclude" (transparencia MRM): las filas no enrutables
        cuentan en n_excluded y forman su propio bin en PSI.
        """
        self._require(FlowState.OOT_LOADED, "evaluate_oot")
        st_check = self._state
        if st_check.tree is not None:
            K = len(st_check.tree.class_labels)
            if K > 2:
                raise ValueError(
                    f"[session] evaluate_oot: metricas multiclase no "
                    f"implementadas en Fase 3.1 (K={K} clases "
                    f"detectadas). Planificadas para la Fase 3.5."
                )
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
                [model.nodes[int(a)].pd_final[0] for a in asign_oot[validas]]
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
        p_tr = np.array([model.nodes[int(a)].pd_final[0] for a in asign_tr])
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
            p_te = np.array([model.nodes[int(a)].pd_final[0] for a in asign_te])
            n_te_eff = max(3, int(len(p_te)) // 5)
            gini_oos = compute_oos_metrics(
                p_te, self._y_test, n_groups=n_te_eff
            ).gini

        def _drop(g):
            # None, NaN o Gini_train == 0 -> indefinido (NUNCA se reporta
            # silenciosamente como 'sin alerta': gini_drop_alert -> UNDETERMINED)
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
