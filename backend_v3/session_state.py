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
    build_classification_matrix_multiclass,
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
    # Fase 3.3: columna de poblacion (segmento/categoria)
    population_col: str | None = None
    # Fase 3.3: whitelist de valores OK en la columna de poblacion
    population_ok_values: tuple[str, ...] = ()
    # Fase 3.3: filas excluidas por poblacion en el dataset de desarrollo
    n_excluded_population: int = 0
    # Fase 3.3: desglose por motivo de exclusion (desarrollo)
    population_breakdown: tuple[tuple[str, int], ...] = ()
    # Fase 3.3: filas excluidas por poblacion en la cohorte OOT
    n_excluded_population_oot: int = 0
    # Fase 3.3: desglose por motivo de exclusion (OOT)
    population_breakdown_oot: tuple[tuple[str, int], ...] = ()
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
        # Caches de categorias de poblacion (Fase 3.3)
        self._pop_col: str | None = None
        self._pop_ok_values: tuple[str, ...] | None = None

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

    def describe_weight_column(self, col: str) -> dict:
        """Diagnostico de una columna candidata a pesos (lectura pura,
        sin transicion de estado).

        Pensado para GUI/MCP (Fase 3.2.h): permite al wizard mostrar el
        aviso ambar de columna de pesos invalida sin exponer el
        DataFrame ni pandas. Replica los criterios de fix_spec (valores
        finitos, estrictamente positivos, sin NaN) en modo solo-lectura.

        Returns:
            dict con claves:
                "exists" (bool): la columna esta en el dataset.
                "n" (int): nº de filas (0 si la columna no existe).
                "n_nonpositive" (int): nº de valores <= 0 o no finitos.
                "n_nan" (int): nº de valores NaN.

        Raises:
            RuntimeError: sin dataset cargado.
        """
        if self._df is None:
            raise RuntimeError(
                "[session] describe_weight_column sin dataset cargado"
            )
        if col not in self._df.columns:
            return {"exists": False, "n": 0, "n_nonpositive": 0, "n_nan": 0}
        serie = self._df[col]
        n_nan = int(serie.isna().sum())
        if pd.api.types.is_numeric_dtype(serie):
            vals = serie.dropna().to_numpy(dtype=float)
            n_nonpositive = int((~(vals > 0)).sum())
        else:
            # no numerica: todo valor no-NaN es invalido como peso
            n_nonpositive = int(serie.notna().sum())
        return {
            "exists": True,
            "n": int(len(serie)),
            "n_nonpositive": n_nonpositive,
            "n_nan": n_nan,
        }

    def describe_population_column(self, col: str) -> dict:
        """Perfil de solo lectura de una columna candidata a poblacion
        (Fase 3.3, sin transicion de estado).

        Pensado para GUI/MCP: permite al wizard poblar la tabla de
        categorias observadas y sus conteos, sin exponer el DataFrame.

        Returns:
            dict con claves:
                "exists" (bool): la columna esta en el dataset.
                "n" (int): nº de filas (0 si la columna no existe).
                "values" (tuple[tuple[str, int], ...]): pares
                    (valor, conteo) ordenados por conteo descendente y
                    luego por valor ascendente (determinista). Los NaN
                    se representan con el sentinel "<NaN>". Tupla vacia
                    si la columna no existe o esta vacia.

        Raises:
            RuntimeError: sin dataset cargado.
        """
        if self._df is None:
            raise RuntimeError(
                "[session] describe_population_column sin dataset cargado"
            )
        if col not in self._df.columns:
            return {"exists": False, "n": 0, "values": ()}
        serie = self._df[col]
        n = int(len(serie))
        vc = serie.value_counts(dropna=False)
        items: list[tuple[str, int]] = []
        for v, c in vc.items():
            if pd.isna(v):
                v_str = "<NaN>"
            else:
                v_str = str(v)
            items.append((v_str, int(c)))
        items.sort(key=lambda kv: (-kv[1], kv[0]))
        return {"exists": True, "n": n, "values": tuple(items)}

    def get_data_preview(self, n_rows: int = 50) -> dict:
        """Preview crudo del dataset cargado (lectura pura, sin transicion).

        Fase 3.11.b.1 (Data Viewer, diseno 3.11.b D3): pensado para
        GUI/MCP; responde a "que cargue?" con los datos CRUDOS del CSV
        original (sin imputacion, sin codificacion, sin split).

        Contrato de retorno (tipos puros, JSON-serializable):
            {"columns": list[str], "rows": list[tuple],
             "n_total": int, "truncated": bool}
        Toda celda se convierte a tipo nativo de Python (int/float/str/
        bool); los valores ausentes del CSV (pd.isna) se devuelven como
        None (nunca NaN ni escalares numpy/pandas en el retorno).
        `truncated` es True si n_total > len(rows).

        Divergencia consciente con la familia describe_*: SIN dataset
        cargado NO lanza RuntimeError; devuelve el dict vacio
        ({"columns": [], "rows": [], "n_total": 0, "truncated": False})
        para simplificar el estado vacio del visor (diseno D3; la
        divergencia se registra en docs/design_decisions.md al cierre
        de la sub-fase).
        """
        if self._df is None:
            return {"columns": [], "rows": [], "n_total": 0,
                    "truncated": False}
        n_total = int(self._df.shape[0])
        columns = [str(c) for c in self._df.columns]
        rows = [
            tuple(self._cell_native(v) for v in fila)
            for fila in self._df.iloc[:n_rows].itertuples(
                index=False, name=None
            )
        ]
        self._log.info(
            "[session] get_data_preview: %d/%d filas", len(rows), n_total
        )
        return {
            "columns": columns,
            "rows": rows,
            "n_total": n_total,
            "truncated": n_total > len(rows),
        }

    @staticmethod
    def _cell_native(v: Any) -> Any:
        """Convierte una celda pandas/numpy a tipo nativo de Python.

        NaN/NaT -> None; np.bool_ -> bool; np.integer -> int;
        np.floating -> float; el resto (str, bool nativos) pasa intacto.
        """
        if pd.isna(v):
            return None
        if isinstance(v, np.bool_):
            return bool(v)
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, np.floating):
            return float(v)
        return v

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

    def _partition_weights(self, partition: str) -> np.ndarray | None:
        """Vector de pesos de la particion (None si la sesion no es ponderada).

        Fase 3.2.g: longitud completa de la particion (sin filtrar); el
        filtrado por filas enrutables lo hace el consumidor via su propia
        mascara `routed`.
        """
        if partition == "train":
            return self._w_train
        if partition == "oos":
            return self._w_test
        if partition == "oot":
            return self._w_oot
        return None

    def _translate_y_to_internal(self, y: np.ndarray) -> np.ndarray:
        """Traduce etiquetas originales (CSV) al orden interno canonico.

        Fase 3.5.c: aplica solo al path multiclase (K > 2). En K = 2 el
        path binario se mantiene intacto y NO se llama a este helper
        (paridad bit a bit con el pre-3.5.c).

        Recibe un vector 1D de etiquetas en valores ORIGINALES y
        devuelve otro de la misma longitud con las etiquetas traducidas
        al orden interno del modelo (columna c <-> etiqueta c). El
        orden interno se reconstruye desde SessionState con la misma
        regla que Session.train usa para class_labels_canonical:
        indice 0 = st.target_class; indices 1..K-1 = resto de
        st.target_classes ordenado ascendente.
        """
        st = self._state
        if st.target_class is None or not st.target_classes:
            raise RuntimeError(
                "[session] _translate_y_to_internal sin target_class/"
                "target_classes en SessionState (fix_spec no ejecutado)"
            )
        orden = (st.target_class,) + tuple(
            sorted(c for c in st.target_classes if c != st.target_class)
        )
        mapa = {valor: idx for idx, valor in enumerate(orden)}
        return np.array([mapa[v] for v in np.asarray(y)], dtype=int)

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

        Fase 3.2.g: si la sesion es ponderada, propaga el vector de pesos
        de la particion solicitada (longitud completa, sin filtrar).
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
            weights=self._partition_weights(partition),
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
        never touch         backend dataclasses.

        Fase 3.2.g: si la sesion es ponderada, propaga el vector de pesos
        de la particion solicitada (longitud completa; el filtrado por
        filas enrutables lo hace `_validated_routed` internamente).
        """
        if self._state.tree is None:
            return None
        K = len(self._state.tree.class_labels)
        X, y, unseen_policy = self._routed_partition(partition)
        leaf_assignment = predict_leaf_assignment(
            self._state.tree, X, unseen_policy=unseen_policy
        )
        if K == 2:
            # Phase 3.1: pd_final is a per-class tuple; index 0 is the class of interest.
            pd_per_leaf = {
                nd.node_id: nd.pd_final[0]
                for nd in self._state.tree.nodes if nd.is_leaf
            }
            result = build_classification_matrix(
                leaf_assignment, y, pd_per_leaf, threshold=threshold,
                weights=self._partition_weights(partition),
            )
        else:
            pd_per_leaf = {
                nd.node_id: tuple(nd.pd_final)
                for nd in self._state.tree.nodes if nd.is_leaf
            }
            y_interno = self._translate_y_to_internal(y)
            result = build_classification_matrix_multiclass(
                leaf_assignment, y_interno, pd_per_leaf,
                weights=self._partition_weights(partition),
            )
        self._log.info(
            "[session] get_classification_matrix: partition=%s K=%d",
            partition, K,
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
        self._pop_col = None
        self._pop_ok_values = None
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
        population_col: str | None = None,
        population_ok_values: tuple[str, ...] | None = None,
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
        # --- Fase 3.3: categorias de poblacion ---
        if population_col is None:
            if population_ok_values:
                raise ValueError(
                    "[session] population_ok_values requiere population_col "
                    "(no se puede declarar whitelist sin columna)"
                )
            self._pop_col = None
            self._pop_ok_values = None
        else:
            if population_col not in self._df.columns:
                raise ValueError(
                    f"[session] population_col ausente en el dataset: "
                    f"{population_col!r}"
                )
            if population_col == target:
                raise ValueError(
                    f"[session] population_col {population_col!r} no puede "
                    f"ser el target"
                )
            if predictors is not None and population_col in {str(p) for p in predictors}:
                raise ValueError(
                    f"[session] population_col {population_col!r}: la "
                    f"columna de poblacion no puede ser predictor"
                )
            if population_ok_values is None or len(population_ok_values) == 0:
                raise ValueError(
                    "[session] population_col declarado pero "
                    "population_ok_values esta vacio; se exige una whitelist "
                    "no vacia de valores OK"
                )
            for v in population_ok_values:
                if not isinstance(v, str) or not v:
                    raise ValueError(
                        f"[session] population_ok_values debe contener "
                        f"strings no vacios; recibido {v!r}"
                    )
            col_p = self._df[population_col]
            if col_p.isna().any():
                first_nan = int(np.flatnonzero(col_p.isna().to_numpy())[0])
                raise ValueError(
                    f"[session] population_col {population_col!r} contiene "
                    f"NaN (primera fila: {first_nan}); codifique el valor "
                    f"faltante como string en el CSV"
                )
            ok_mask = col_p.isin(population_ok_values).to_numpy()
            K_full = len(pd.unique(self._df[target].dropna()))
            K_ok = len(pd.unique(self._df.loc[ok_mask, target].dropna()))
            # WARNING por cada clase del completo que no sobrevive al filtro.
            # Se loguea SIEMPRE (evidencia MRM), antes de la posible
            # excepcion por K_ok < 2.
            clases_full = set(pd.unique(self._df[target].dropna()))
            clases_ok = set(pd.unique(self._df.loc[ok_mask, target].dropna()))
            perdidas = sorted(clases_full - clases_ok)
            for c in perdidas:
                n_c = int((self._df[target] == c).sum())
                self._log.warning(
                    "[session] clase %r (n=%d en el dataset completo) NO "
                    "aparece tras el filtro de poblacion",
                    c, n_c,
                )
            if K_ok < 2:
                raise ValueError(
                    f"[session] el filtro de poblacion deja K_ok={K_ok} "
                    f"clases del target (dataset completo: K={K_full}); se "
                    f"exigen >= 2 clases para entrenar"
                )
            self._pop_col = population_col
            self._pop_ok_values = tuple(population_ok_values)
        evento = f"fix_spec:{target}|predictores={len(spec)}"
        if self._w_col is not None:
            evento += f"|weight_col={self._w_col}"
        if self._pop_col is not None:
            evento += (
                f"|population_col={self._pop_col}"
                f",ok={len(self._pop_ok_values or ())}"
            )
        return self._commit(
            FlowState.SPEC_FIXED,
            evento=evento,
            target=target, target_classes=tuple(valores),
            target_class=target_class,
            class_labels=tuple(sorted(class_labels.items())),
            spec=tuple(spec.items()),
            population_col=self._pop_col,
            population_ok_values=self._pop_ok_values or (),
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
        # Fase 3.3: aplicar filtro de poblacion si esta declarado.
        if self._pop_col is not None:
            ok_mask = (
                self._df[self._pop_col]
                .isin(self._pop_ok_values or ())
                .to_numpy()
            )
            n_excluded = int((~ok_mask).sum())
            non_ok = self._df.loc[~ok_mask, self._pop_col]
            vc = non_ok.value_counts()
            breakdown = tuple(
                (str(v), int(c))
                for v, c in sorted(
                    vc.items(), key=lambda kv: (-int(kv[1]), str(kv[0]))
                )
            )
        else:
            ok_mask = np.ones(len(self._df), dtype=bool)
            n_excluded = 0
            breakdown = ()
        ok_indices = np.flatnonzero(ok_mask)

        w: np.ndarray | None = None
        if self._w_col is not None:
            w_full = self._df[self._w_col].to_numpy(dtype=float)
            w_ok = w_full[ok_indices]
        else:
            w_full = None
            w_ok = None

        y_ok = self._df[st.target].iloc[ok_indices]
        idx_tr_rel, idx_te_rel = stratified_split(
            y_ok, train_frac, seed, self._log, weights=w_ok
        )
        idx_tr = ok_indices[idx_tr_rel]
        idx_te = ok_indices[idx_te_rel]

        if w_full is not None:
            self._w_train = w_full[idx_tr]
            self._w_test = w_full[idx_te]
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
        if self._w_col is not None:
            evento += "|weighted=true"
        if self._pop_col is not None:
            evento += (
                f"|population_col={self._pop_col}|excluded={n_excluded}"
            )
        return self._commit(
            FlowState.PARTITIONED,
            evento=evento,
            train_idx=tuple(int(i) for i in idx_tr),
            test_idx=tuple(int(i) for i in idx_te),
            train_frac=float(train_frac), seed=int(seed),
            n_excluded_population=n_excluded,
            population_breakdown=breakdown,
        )

    def train(
        self,
        engine,
        *,
        target_type: TargetType = TargetType.BINARY,
        max_depth: int = 4,
        min_child_size: int = 50,
        min_child_weight: float | None = None,
        pd_floor: float | None = 0.0005,
        apply_jeffreys: bool = True,
    ) -> SessionState:
        """PARTITIONED -> TRAINED (TreeBuilder sobre train imputado).

        `engine` puede ser una instancia con best_split() o su nombre
        ("CHAID" | "CHAID_EXHAUSTIVE" | "CRT" | "QUEST"); la factoria
        interna (Fase 2.1) permite al frontend/MCP invocar por nombre sin
        importar motores (sala limpia).

        Gobernanza (types.GovernanceMode): los defaults son BANKING
        (Jeffreys + PD Floor, BCBS CRE 32.4); apply_jeffreys=False con
        pd_floor=None produce el modo RESEARCH (PD cruda k/n).

        Fase 3.1.c: la clase de interes y las etiquetas canonicas se leen
        de SessionState (fijadas en fix_spec). La clase de interes se lee
        exclusivamente de SessionState (fijada en fix_spec).
        Fase 3.4.b: todos los motores admiten K > 2. Las métricas y
        reportes downstream siguen bloqueados hasta la Fase 3.5.

        Fase 3.2: si la sesion esta ponderada (fix_spec con weight_col),
        los pesos de train (`_w_train`) se propagan a TreeBuilder junto
        con `weight_col` para el fingerprint.
        Fase 3.7.c: `min_child_weight` (keyword-only, default None) es el
        piso de MASA PONDERADA por rama, complementario a min_child_size
        (que mide filas fisicas). Solo tiene efecto numerico cuando la
        sesion es ponderada (weight_col declarado en fix_spec): con
        weight_col=None el vector interno es de unos y min_child_weight
        actua como un piso equivalente en filas, redundante con
        min_child_size. None (default) desactiva la comprobacion.
        """
        self._require(FlowState.PARTITIONED, "train")
        st = self._state
        assert st.spec is not None
        assert self._X_train is not None and self._y_train is not None
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
        # Phase 3.4.b: ningún motor bloquea targets multiclase aquí.
        # Las métricas y reportes downstream (validation, reporting,
        # stability) siguen bloqueando K > 2 hasta la Fase 3.5.
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
            min_child_weight=min_child_weight,
            seed=st.seed, logger=get_logger("builder"),
        )
        modelo = builder.build(self._X_train, self._y_train, dict(st.spec))
        evento = (f"train:{modelo.method}|nodos={len(modelo.nodes)}"
                  f"|fp={modelo.params_fingerprint}")
        if self._w_col is not None:
            evento += f"|weighted=true,weight_col={self._w_col}"
        if min_child_weight is not None:
            evento += f"|min_child_weight={min_child_weight}"
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

        Fase 3.2.g: si la sesion es ponderada, propaga `weights=self._w_test`
        a compute_oos_metrics (metricas ponderadas).
        """
        self._require(FlowState.TRAINED, "evaluate_oos")
        st = self._state
        assert st.tree is not None
        assert self._X_test is not None and self._y_test is not None
        K = len(st.tree.class_labels)
        p_2d = predict_pd(st.tree, self._X_test)
        if K == 2:
            p = p_2d[:, 0]  # Phase 3.1.d: binary consumers read column 0
            y_eval = self._y_test
        else:
            p = p_2d
            y_eval = self._translate_y_to_internal(self._y_test)
        metrics = compute_oos_metrics(
            p, y_eval, n_groups=n_groups, weights=self._w_test
        )
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

    def get_prune_sequence(self) -> list[dict[str, Any]]:
        """TRAINED -> secuencia de poda coste-complejidad como DTO plano.

        Fase 3.9 (Poda Interactiva): expone ``Pruner.sequence(tree)``
        al frontend como lista de dicts (claves ``alpha``, ``n_leaves``,
        ``r_subtree``) para que la GUI muestre la tabla de alphas y el
        analista elija con discrecion (design_decisions.md §8.6).
        Solo lectura: no muta el estado de la sesion ni commitea
        eventos. El frontend no importa dataclasses del backend, por
        eso se serializa con ``dataclasses.asdict``.
        """
        self._require(FlowState.TRAINED, "get_prune_sequence")
        st = self._state
        assert st.tree is not None
        secuencia = Pruner(logger=get_logger("pruning")).sequence(st.tree)
        return [asdict(paso) for paso in secuencia]

    def get_univariate_trees(self, max_depth: int = 3) -> list[dict]:
        """Genera un arbol univariado por predictor y extrae metricas y cortes.

        Fase 3.11.c.1 (diseno: docs/3.11.c_design_univariate_cost_matrix.md):
        para cada predictor del spec entrena un arbol de profundidad
        ``max_depth`` con el MISMO motor del modelo principal y parametros
        de gobernanza BANKING (Jeffreys + pd_floor), lo evalua sobre test
        (mismo camino que ``evaluate_oos``) y devuelve un DTO plano: lista
        de dicts con claves ``predictor`` (str), ``gini`` (float),
        ``ks`` (float) y ``cut_points`` (list[tuple[str, float]], umbrales
        de los nodos internos; vacio si el predictor no produjo cortes).
        Solo lectura: no muta el estado ni commitea eventos. Un predictor
        que falla (p. ej. categorias no vistas en test con
        unseen_policy="error") queda registrado con metricas 0.0 y sin
        cortes, con WARNING en el log.
        """
        if self._state.tree is None:
            raise ValueError(
                "[session] get_univariate_trees requiere un modelo entrenado"
            )
        st = self._state
        assert st.spec is not None
        assert self._X_train is not None and self._y_train is not None
        assert self._X_test is not None and self._y_test is not None
        # Mismo motor que el modelo principal (factoria unica del modulo,
        # fuente de verdad de la Fase 2.1); fallback CRT defensivo.
        factory = _ENGINE_FACTORIES.get(st.tree.method, CrtEngine)
        results: list[dict] = []
        for predictor, ptype in dict(st.spec).items():
            builder = TreeBuilder(
                factory(),
                target_type=TargetType.BINARY,
                target_class=st.target_class,
                class_labels=st.tree.class_labels,
                max_depth=max_depth,
                min_child_size=5,
                pd_floor=0.0005,
                apply_jeffreys=True,
                seed=st.seed,
                logger=get_logger("builder"),
                # TODO(zona_gris): el prompt omitia weights; se propagan los
                # pesos de train para paridad con train() (gobernanza de
                # sesiones ponderadas, Fase 3.2). Resolver en 3.11.c.2/3.
                weights=self._w_train,
            )
            try:
                uni_tree = builder.build(
                    self._X_train, self._y_train, {predictor: ptype}
                )
                p_2d = predict_pd(uni_tree, self._X_test)
                if len(uni_tree.class_labels) == 2:
                    p = p_2d[:, 0]  # Phase 3.1.d: binario lee columna 0
                    y_eval = self._y_test
                else:
                    p = p_2d
                    y_eval = self._translate_y_to_internal(self._y_test)
                # n_groups adaptativo: HL exige n_groups >= 3 y
                # n_groups * 5 <= N (contrato de compute_oos_metrics).
                n_test = len(self._X_test)
                n_groups = min(10, max(3, n_test // 5))
                metrics = compute_oos_metrics(
                    p, y_eval, n_groups=n_groups, weights=self._w_test
                )
                cuts: list[tuple[str, float]] = []
                for nd in uni_tree.nodes:
                    if not nd.is_leaf and nd.split is not None:
                        if nd.split.threshold is not None:
                            cuts.append(
                                (nd.split.predictor, float(nd.split.threshold))
                            )
                results.append({
                    "predictor": predictor,
                    "gini": metrics.gini if metrics.gini is not None else 0.0,
                    "ks": metrics.ks if metrics.ks is not None else 0.0,
                    "cut_points": cuts,
                })
            except Exception as e:
                self._log.warning(
                    "[session] Error entrenando univariado para %s: %s",
                    predictor, e,
                )
                results.append({
                    "predictor": predictor, "gini": 0.0, "ks": 0.0,
                    "cut_points": [],
                })
        return results

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
        if self._pop_col is not None:
            esperadas = esperadas | {self._pop_col}
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
        # Fase 3.3: filtrar por poblacion ANTES de materializar X/y.
        if self._pop_col is not None:
            pop_ok_mask = (
                df_oot[self._pop_col]
                .isin(self._pop_ok_values or ())
                .to_numpy()
            )
            n_excl_oot = int((~pop_ok_mask).sum())
            non_ok_oot = df_oot.loc[~pop_ok_mask, self._pop_col]
            vc_oot = non_ok_oot.value_counts()
            breakdown_oot = tuple(
                (str(v), int(c))
                for v, c in sorted(
                    vc_oot.items(), key=lambda kv: (-int(kv[1]), str(kv[0]))
                )
            )
            df_oot = df_oot.loc[pop_ok_mask].reset_index(drop=True)
        else:
            n_excl_oot = 0
            breakdown_oot = ()
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
        if self._pop_col is not None:
            evento += (
                f"|population_col={self._pop_col}|excluded_oot={n_excl_oot}"
            )
        return self._commit(
            FlowState.OOT_LOADED,
            evento=evento,
            n_oot=int(len(df_oot)), temporal_verified=temporal_ok,
            oot_source="external-file",
            n_excluded_population_oot=n_excl_oot,
            population_breakdown_oot=breakdown_oot,
        )

    def evaluate_oot(
        self, *, n_groups: int = 10, weight_oot: bool = True
    ) -> SessionState:
        """OOT_LOADED -> OOT_EVALUATED: metricas OOT + Gini Drop + PSI/CSI.

        unseen_policy="exclude" (transparencia MRM): las filas no enrutables
        cuentan en n_excluded y forman su propio bin en PSI.

        Fase 3.2.g: si la sesion es ponderada, propaga pesos a las metricas:
        `_w_oot[validas]` para el computo OOT, `_w_train` para el Gini de
        train y `_w_test` para el gini_oos al vuelo.

        Fase 3.2.h: `weight_oot` (default True) controla si la cohorte OOT
        usa sus propios pesos en PSI/CSI (convencion por defecto: cada
        cohorte con sus pesos, diseno v2 §5.3 B4 opcion 1). Con
        `weight_oot=False`, el OOT usa pesos uniformes en PSI/CSI.
        """
        self._require(FlowState.OOT_LOADED, "evaluate_oot")
        from .stability import GiniDropReport, StabilityMonitor, gini_drop_alert

        st = self._state
        assert st.tree is not None and st.spec is not None
        assert self._X_oot is not None and self._y_oot is not None

        model = st.tree
        K = len(model.class_labels)
        spec_d = dict(st.spec)

        asign_oot = predict_leaf_assignment(
            model, self._X_oot, unseen_policy="exclude"
        )
        validas = asign_oot >= 0
        n_val = int(validas.sum())
        n_exc = int((~validas).sum())

        # metricas OOT sobre las filas enrutables
        if n_val >= 15:
            if K == 2:
                p_val = np.array(
                    [model.nodes[int(a)].pd_final[0] for a in asign_oot[validas]]
                )
                y_val = self._y_oot[validas]
            else:
                p_val = np.array(
                    [model.nodes[int(a)].pd_final for a in asign_oot[validas]]
                )
                y_val = self._translate_y_to_internal(self._y_oot[validas])
            g_eff = n_groups if n_val >= 5 * n_groups else max(3, n_val // 5)
            w_val = None if self._w_oot is None else self._w_oot[validas]
            metrics = compute_oos_metrics(p_val, y_val,
                                          n_groups=g_eff, weights=w_val)
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
        if K == 2:
            p_tr = np.array([model.nodes[int(a)].pd_final[0] for a in asign_tr])
            y_tr = self._y_train.to_numpy()
        else:
            p_tr = np.array([model.nodes[int(a)].pd_final for a in asign_tr])
            y_tr = self._translate_y_to_internal(self._y_train.to_numpy())
        n_tr = int(len(p_tr))
        g_eff_tr = min(5, max(3, n_tr // 5))
        m_tr = compute_oos_metrics(p_tr, y_tr,
                                   n_groups=g_eff_tr, weights=self._w_train)
        gini_train = m_tr.gini if m_tr.gini is not None else float("nan")

        if st.oos_metrics is not None:
            gini_oos = st.oos_metrics.gini
        else:
            asign_te = predict_leaf_assignment(
                model, self._X_test, unseen_policy="error"
            )
            if K == 2:
                p_te = np.array([model.nodes[int(a)].pd_final[0] for a in asign_te])
                y_te = self._y_test
            else:
                p_te = np.array([model.nodes[int(a)].pd_final for a in asign_te])
                y_te = self._translate_y_to_internal(self._y_test)
            n_te_eff = max(3, int(len(p_te)) // 5)
            gini_oos = compute_oos_metrics(
                p_te, y_te, n_groups=n_te_eff, weights=self._w_test
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
        w_actual = self._w_oot if (weight_oot and self._w_oot is not None) else None
        psi, csi = monitor.report(
            model, self._X_train, self._X_oot, asign_tr, asign_oot, spec_d,
            weights_train=self._w_train, weights_actual=w_actual,
        )

        reporte = OOTReport(
            metrics=metrics, drop=drop_report, psi=psi, csi=csi,
            n_oot=int(st.n_oot or 0), n_excluded=n_exc,
        )
        narrativa = "OOT" if st.temporal_verified else "OOS-no-verificado"
        evento = (
            f"evaluate_oot:{narrativa}|n={n_val}|excluidas={n_exc}"
            f"|drop_oot={'nan' if drop_oot is None else format(drop_oot, '.4g')}"
            f"|psi={psi.psi:.4g}({psi.flag})"
        )
        if self._w_col is not None:
            evento += f"|weighted=true,weight_col={self._w_col}"
            if not weight_oot:
                evento += "|weight_oot=false"
        return self._commit(
            FlowState.OOT_EVALUATED,
            evento=evento,
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
