"""Recursive decision-tree builder (TreeGov, backend_v3, Phase 1).

Assembles any of the 4 engines (ChaidEngine / ChaidEngine exhaustive /
CrtEngine / QuestEngine) into a complete, deterministic, auditable tree.

Hard rules:
  - BFS growth with a FIFO queue: ids 0, 1, 2, ... are assigned by level
    and expansion order (deterministic; never a stack).
  - Multi-way routing: branches (K >= 2 groups, engine's natural order) or
    threshold (left: x <= t, right: x > t). CHAID may produce K > 2;
    C&RT and QUEST are strictly binary.
  - min_child_size is an ABSOLUTE FLOOR per branch: if ANY branch of the
    proposed split would end up with fewer than min_child_size rows, the
    whole split is rejected (no fallback merge; it is documented and the
    node stays a leaf).
  - If the engine raises, TreeBuilder PROPAGATES the exception (fail-fast):
    it is never translated into a leaf (an error is never disguised as an
    analytical decision).
  - Per-node PD vector, by GovernanceMode (Phase 2.1, types.GovernanceMode):
      BANKING (default): multivariate Jeffreys (k_c + 0.5) / (n + K * 0.5)
          per class c (Jeffreys 1946; symmetric Dirichlet(0.5, ...) prior),
          then component-wise soft floor + renormalization [BCBS CRE 32.4];
      RESEARCH: raw empirical proportions k_c / n, no floor.
    For K = 2 the Jeffreys formula reduces exactly to the binary
    (k + 0.5) / (n + 1.0). The OPERATIONAL PD lives on leaves
    (is_leaf=True) only; internal-node PDs are exposed for traceability.
  - Phase 3.1 (multiclass): the target may have K >= 2 classes. Classes
    are reordered internally so that the class of interest (target_class)
    is always index 0 of n_events / pd_jeffreys / pd_final / class_labels;
    the remaining classes follow in ascending order. The invariant
    sum(pd_final) == 1 holds for every node (enforced by TreeModel).
    class_labels are human-readable labels in canonical order
    (index 0 = target_class).
  - Phase 3.2.e (sample weights): TreeBuilder accepts `weights`
    (per-row masses), `min_child_weight` (weighted-mass floor per
    branch, cumulative with `min_child_size`, which still measures
    PHYSICAL ROWS) and `weight_col` (fingerprint traceability only).
    Each node records `w_events` (weighted mass per class), purely
    informative: it does NOT alter routing nor pruning. The Jeffreys
    PD uses the weighted mass (Heeringa, West & Berglund 2010, §5.3).
    With `weights=None` behavior is bit-identical to pre-3.2.
  - Structural determinism: two build() calls with the same data and
    parameters produce identical TreeModel objects (==). params_fingerprint
    is a stable sha256 (json with sorted keys; no memory addresses).
    The event_log does NOT live in TreeModel: it lives in SessionState
    (session_state).

Allowed dependencies: numpy, pandas, stdlib + backend_v3 engines.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from dataclasses import dataclass
from numbers import Integral

import numpy as np
import pandas as pd

from .log_config import get_logger
from .types import GovernanceMode, PredictorType, SplitConfig, TargetType

__all__ = ["TreeNode", "TreeModel", "TreeBuilder"]


@dataclass(frozen=True)
class TreeNode:
    """Tree node. Immutable and hashable (split is itself hashable).

    Phase 3.1 (multiclass): n_events, pd_jeffreys and pd_final are
    K-length tuples in canonical class order -- index 0 is always the
    class of interest (target_class), the remaining classes follow in
    ascending order -- and class_labels[c] is the human-readable label
    of class c. sum(pd_final) == 1 for every node (TreeModel enforces
    it with tolerance 1e-12). pd_final is operational only on leaves
    (is_leaf=True); on internal nodes it is exposed for traceability.
    """

    node_id: int
    depth: int
    parent_id: int | None
    n: int
    n_events: tuple[int, ...]        # per-class counts, canonical order
    # Multivariate Jeffreys (k_c + 0.5) / (n + K*0.5) in BANKING mode;
    # raw k_c / n in RESEARCH mode
    pd_jeffreys: tuple[float, ...]
    pd_final: tuple[float, ...]      # component-wise soft floor +
                                     # renormalization if pd_floor is set;
                                     # pd_jeffreys otherwise.
                                     # Operational on leaves only
    class_labels: tuple[str, ...]    # label of class c, same canonical order
    is_leaf: bool
    split: SplitConfig | None
    child_ids: tuple[int, ...]
    leaf_reason: str | None  # None en internos; "max_depth" | "min_child" |
                             # "sin_split" | "rama_insuficiente" en hojas
    # Phase 3.2.e: per-class WEIGHTED mass, canonical order. Purely
    # informative (no routing/pruning effect). Empty tuple for hand-built
    # nodes (tests); TreeBuilder.build always populates it. Placed last
    # because dataclass rules forbid a defaulted field between non-defaulted
    # ones (logical position: right after n_events).
    w_events: tuple[float, ...] = ()


@dataclass(frozen=True)
class TreeModel:
    """Arbol completo e inmutable. Determinista; sin timestamps.

    Phase 3.1: class_labels / target_class / target_class_index record the
    analyst's explicit class-of-interest choice. Canonical-order invariant:
    index 0 of every per-class vector is target_class, so target_class_index
    is always 0 (verified in __post_init__).
    """

    root_id: int
    nodes: tuple[TreeNode, ...]  # indexado por node_id (0..len-1)
    method: str
    params_fingerprint: str
    class_labels: tuple[str, ...]  # canonical order: index 0 = target_class
    target_class: int | str        # class of interest, as entered by analyst
    target_class_index: int        # always 0 by construction (invariant)

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("[TreeModel] sin nodos")
        if self.target_class_index != 0:
            raise ValueError(
                f"[TreeModel] target_class_index debe ser 0 (invariante de "
                f"orden canonico): {self.target_class_index!r}"
            )
        ids = [nd.node_id for nd in self.nodes]
        if ids != list(range(len(ids))):
            raise ValueError("[TreeModel] node_id debe ser 0..n-1 en orden")
        raiz = self.nodes[self.root_id]
        if raiz.parent_id is not None:
            raise ValueError("[TreeModel] la raiz tiene parent_id")
        K = len(self.class_labels)
        for nd in self.nodes:
            # Phase 3.1 invariants: coherent per-class vector lengths and
            # pd_final normalized to 1 (tolerance for float drift: 1e-12).
            if not (len(nd.pd_final) == len(nd.pd_jeffreys)
                    == len(nd.n_events) == len(nd.class_labels) == K):
                raise ValueError(
                    f"[TreeModel] nodo {nd.node_id}: longitudes incoherentes "
                    f"(pd_final={len(nd.pd_final)}, "
                    f"pd_jeffreys={len(nd.pd_jeffreys)}, "
                    f"n_events={len(nd.n_events)}, "
                    f"class_labels={len(nd.class_labels)}, modelo={K})"
                )
            if abs(sum(nd.pd_final) - 1.0) > 1e-12:
                raise ValueError(
                    f"[TreeModel] nodo {nd.node_id}: sum(pd_final) = "
                    f"{sum(nd.pd_final)} != 1.0"
                )
            for c, k_c in enumerate(nd.n_events):
                if k_c > nd.n:
                    raise ValueError(
                        f"[TreeModel] nodo {nd.node_id}: "
                        f"n_events[{c}]={k_c} > n={nd.n}"
                    )
            # Phase 3.2.e: w_events (si presente) debe tener longitud K y
            # valores >= 0; la tupla vacia es valida (nodos a mano en tests)
            if nd.w_events:
                if len(nd.w_events) != K or any(v < 0 for v in nd.w_events):
                    raise ValueError(
                        f"[TreeModel] nodo {nd.node_id}: w_events invalido "
                        f"(len={len(nd.w_events)}, modelo={K})"
                    )
            if nd.is_leaf:
                if nd.split is not None or nd.child_ids:
                    raise ValueError(
                        f"[TreeModel] nodo {nd.node_id} hoja pero con split/hijos"
                    )
            else:
                if nd.split is None or len(nd.child_ids) < 2:
                    raise ValueError(
                        f"[TreeModel] nodo {nd.node_id} interno sin split/hijos"
                    )
                for cid in nd.child_ids:
                    if not (0 <= cid < len(self.nodes)):
                        raise ValueError(
                            f"[TreeModel] nodo {nd.node_id} referencia hijo invalido {cid}"
                        )
                    hijo = self.nodes[cid]
                    if hijo.parent_id != nd.node_id:
                        raise ValueError(
                            f"[TreeModel] nodo {cid}: parent_id incoherente"
                        )
                    if hijo.depth != nd.depth + 1:
                        raise ValueError(
                            f"[TreeModel] nodo {cid}: depth incoherente "
                            f"(padre {nd.depth}, hijo {hijo.depth})"
                        )
        # alcanzabilidad: BFS desde la raiz debe visitar TODOS los nodos
        from collections import deque as _dq
        visitados = {self.root_id}
        cola = _dq([self.root_id])
        while cola:
            cur = cola.popleft()
            for cid in self.nodes[cur].child_ids:
                if cid in visitados:
                    raise ValueError(f"[TreeModel] ciclo/referencia repetida: {cid}")
                visitados.add(cid)
                cola.append(cid)
        if len(visitados) != len(self.nodes):
            raise ValueError(
                f"[TreeModel] {len(self.nodes) - len(visitados)} nodos inalcanzables "
                "desde la raiz"
            )


class TreeBuilder:
    """Crecimiento BFS con cola FIFO; ids secuenciales por nivel."""

    def __init__(
        self,
        engine,
        *,
        target_type: TargetType,
        target_class: int | str,
        class_labels: tuple[str, ...],
        max_depth: int | None = 4,
        min_child_size: int = 50,
        pd_floor: float | None = 0.0005,
        apply_jeffreys: bool = True,
        seed: int | None = None,
        logger: logging.Logger | None = None,
        weights: np.ndarray | None = None,
        min_child_weight: float | None = None,
        weight_col: str | None = None,
        population_col: str | None = None,
        population_ok_values: tuple[str, ...] = (),
    ) -> None:
        """max_depth=None -> modo grow_full (crece hasta min_child_size).

        Ese modo existe para alimentar la poda coste-complejidad
        (Breiman et al. 1984, §3) de backend_v3.pruning; sin poda, usar el
        default 4 (pre-pruning).

        pd_floor=None + apply_jeffreys=False -> modo RESEARCH (PD cruda
        k/n, sin floor); los defaults son el modo BANKING (BCBS CRE 32.4).

        target_class (Phase 3.1): mandatory class of interest. It is not
        used numerically by the engines; it fixes the canonical class
        ordering (index 0 of every per-class vector) and is recorded in
        the fingerprint. Mandatory by design (3.1 §1bis.1): no silent
        default may decide the semantics of the PD vector.

        class_labels: Human-readable label per class in canonical
        order (index 0 = target_class). Mandatory.

        weights (Phase 3.2.e, keyword-only): per-row sample weights of
        X_train (1D, finite, strictly positive). The engines receive the
        sub-vector per node and compute weighted splits; the per-class
        weighted mass is recorded in `TreeNode.w_events` (purely
        informative: no routing/pruning effect) and feeds the Jeffreys PD
        (Heeringa, West & Berglund 2010, §5.3). With weights=None the
        behavior is bit-identical to pre-3.2.

        min_child_weight (keyword-only): minimum ACCUMULATED WEIGHT per
        branch; if any branch falls below, the whole split is rejected
        ("rama_insuficiente", same absolute-floor criterion as
        min_child_size). min_child_size measures PHYSICAL ROWS,
        min_child_weight measures WEIGHTED MASS: they can be combined and
        are cumulative. None (default) disables the check.

        weight_col (keyword-only): name of the weight column in the CSV,
        recorded in the fingerprint for traceability only; not used
        numerically.

        population_col (keyword-only): nombre de la columna de poblacion
        en el CSV (Fase 3.3). Solo se registra en el fingerprint para
        trazabilidad; no se usa numericamente aqui. El filtrado de filas
        se hace aguas arriba, en Session.

        population_ok_values (keyword-only): whitelist de valores OK de
        la columna de poblacion. Solo se registra en el fingerprint; no
        se usa numericamente aqui.
        """
        if not hasattr(engine, "best_split"):
            raise TypeError("engine debe exponer best_split(X, y, spec, ...)")
        if target_class is None:
            raise ValueError("target_class no puede ser None")
        if not isinstance(class_labels, (tuple, list)) or not class_labels:
            raise ValueError(
                "[tree_builder] class_labels invalido: debe ser una "
                "secuencia (tuple o list) no vacia de strings"
            )
        if any(not isinstance(lbl, str) or not lbl for lbl in class_labels):
            raise ValueError(
                "[tree_builder] class_labels invalido: todas las "
                "etiquetas deben ser strings no vacios"
            )
        if len(set(class_labels)) != len(class_labels):
            raise ValueError(
                "[tree_builder] class_labels invalido: etiquetas duplicadas"
            )
        class_labels = tuple(class_labels)
        if max_depth is not None and (
            isinstance(max_depth, bool) or not isinstance(max_depth, Integral)
            or int(max_depth) < 1
        ):
            raise ValueError(f"max_depth debe ser entero >= 1 o None: {max_depth!r}")
        if (isinstance(min_child_size, bool)
                or not isinstance(min_child_size, Integral)
                or int(min_child_size) < 1):
            raise ValueError(
                f"min_child_size debe ser entero >= 1: {min_child_size!r}"
            )
        if pd_floor is not None and (
            isinstance(pd_floor, bool) or not (0.0 <= float(pd_floor) < 1.0)
        ):
            raise ValueError(f"pd_floor fuera de [0, 1) o None: {pd_floor!r}")
        if not isinstance(apply_jeffreys, bool):
            raise ValueError(
                f"apply_jeffreys debe ser bool: {apply_jeffreys!r}"
            )
        if weights is not None:
            w_arr = np.asarray(weights, dtype=float)
            if w_arr.ndim != 1:
                raise ValueError(
                    f"weights debe ser 1D (recibido shape={w_arr.shape})"
                )
            if not np.all(np.isfinite(w_arr)) or not np.all(w_arr > 0.0):
                raise ValueError(
                    "weights deben ser finitos y estrictamente positivos"
                )
        if min_child_weight is not None and (
            isinstance(min_child_weight, bool)
            or not float(min_child_weight) > 0.0
        ):
            raise ValueError(
                f"min_child_weight debe ser float > 0 o None: "
                f"{min_child_weight!r}"
            )
        if weight_col is not None and (
            not isinstance(weight_col, str) or not weight_col
        ):
            raise ValueError(
                f"weight_col debe ser None o un string no vacio: {weight_col!r}"
            )
        if population_col is None:
            if population_ok_values:
                raise ValueError(
                    "population_ok_values debe estar vacio cuando "
                    "population_col es None"
                )
            pop_col_norm: str | None = None
            pop_ok_norm: tuple[str, ...] = ()
        else:
            if not isinstance(population_col, str) or not population_col:
                raise ValueError(
                    f"population_col debe ser None o un string no vacio: "
                    f"{population_col!r}"
                )
            if not population_ok_values:
                raise ValueError(
                    "population_ok_values no puede estar vacio si "
                    "population_col esta declarado"
                )
            for v in population_ok_values:
                if not isinstance(v, str) or not v:
                    raise ValueError(
                        f"population_ok_values debe contener strings no "
                        f"vacios; recibido {v!r}"
                    )
            pop_col_norm = population_col
            pop_ok_norm = tuple(population_ok_values)
        self._engine = engine
        self._target_type = target_type
        self._target_class = target_class
        self._class_labels = class_labels
        # None -> modo grow_full (el docstring lo promete desde Fase 1.2;
        # antes int(None) lanzaba TypeError: bug corregido en Fase 2.1)
        self.max_depth = None if max_depth is None else int(max_depth)
        self.min_child_size = int(min_child_size)
        self.pd_floor = None if pd_floor is None else float(pd_floor)
        self.apply_jeffreys = apply_jeffreys
        self.seed = seed
        self._weights = None if weights is None else np.asarray(weights, dtype=float)
        self._min_child_weight = (
            None if min_child_weight is None else float(min_child_weight)
        )
        self._weight_col = weight_col
        self._population_col = pop_col_norm
        self._population_ok_values = pop_ok_norm
        self._log = logger if logger is not None else get_logger("builder")

    # ------------------------------------------------------------------

    def build(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        spec: dict[str, PredictorType],
    ) -> TreeModel:
        """Construye el arbol completo. Las excepciones del motor se propagan.

        Phase 3.1 (multiclass): the target may have K >= 2 classes. The
        canonical ordering places target_class at index 0 of every
        per-class vector; the remaining classes follow in ascending order.
        NaN targets, single-class targets and a target_class absent from
        the data are rejected here, at a single validation point.
        """
        if not spec:
            raise ValueError("[tree_builder] spec vacio")
        if len(X) != len(y) or len(X) == 0:
            raise ValueError("[tree_builder] X e y invalidos o de distinta longitud")

        # Phase 3.1: validate the target and fix the canonical class order
        # (class of interest at index 0; remaining classes ascending).
        yv = pd.Series(y)
        if yv.isna().any():
            raise ValueError(
                "[tree_builder] el target contiene NaN; imputar o excluir "
                "las filas antes de construir el arbol"
            )
        observed = tuple(sorted(pd.unique(yv)))
        if self._target_class not in observed:
            raise ValueError(
                f"[tree_builder] target_class={self._target_class!r} no esta "
                f"entre las clases observadas: {observed!r}"
            )
        other_classes = tuple(c for c in observed if c != self._target_class)
        ordered_classes = (self._target_class,) + other_classes
        K = len(ordered_classes)
        if K < 2:
            raise ValueError(
                "[tree_builder] target constante (K=1 clase observada); un "
                "arbol exige al menos 2 clases"
            )
        class_to_index = {c: i for i, c in enumerate(ordered_classes)}
        # Per-row canonical codes (0 = class of interest).
        ycodes = yv.map(class_to_index).to_numpy(dtype=np.int64)
        if len(self._class_labels) != K:
            raise ValueError(
                f"[tree_builder] class_labels tiene "
                f"{len(self._class_labels)} entradas pero el target "
                f"tiene {K} clases observadas"
            )
        class_labels_tuple = self._class_labels

        # Phase 3.2.e: vector de pesos por fila (unos si no ponderado)
        if self._weights is None:
            w = np.ones(len(X))
        else:
            w = self._weights
            if w.size != len(X):
                raise ValueError(
                    f"[tree_builder] weights (n={w.size}) e X (n={len(X)}) "
                    "difieren en longitud"
                )
        self._log.info(
            "[builder] ponderado=%s weight_col=%s min_child_weight=%s",
            self._weights is not None, self._weight_col, self._min_child_weight,
        )

        fingerprint = self._fingerprint(spec, class_labels_tuple)
        nodos: list[TreeNode] = []
        cola: deque[tuple[int, int | None, int, np.ndarray]] = deque()
        cola.append((0, None, 0, np.arange(len(X))))
        next_id = 1

        while cola:
            node_id, parent_id, depth, idx = cola.popleft()  # FIFO BFS
            Yn = ycodes[idx]
            n = int(len(idx))
            # Per-class counts in canonical order (index 0 = target_class).
            counts = np.bincount(Yn, minlength=K)
            n_events_tuple = tuple(int(c) for c in counts)
            # Phase 3.2.e: masa ponderada por clase. Con weights=None es
            # counts.astype(float) (mismos valores, tipo float: paridad
            # exacta con el codigo pre-3.2).
            if self._weights is None:
                w_counts = counts.astype(float)
            else:
                w_counts = np.bincount(Yn, weights=w[idx], minlength=K)
            w_events_tuple = tuple(float(c) for c in w_counts)
            if self.apply_jeffreys:
                # Multivariate Jeffreys: posterior mean under a symmetric
                # Dirichlet(0.5, ..., 0.5) prior (Jeffreys 1946). For K = 2
                # it reduces exactly to the binary (k + 0.5) / (n + 1.0).
                # Phase 3.2.e: usa la masa ponderada w_counts; con
                # weights=None, sum(w_counts) == n (identico al pre-3.2).
                denom = float(w_counts.sum()) + K * 0.5
                pd_j_tuple = tuple(
                    float((k_c + 0.5) / denom) for k_c in w_counts
                )
            else:
                n_tot_w = float(w_counts.sum())
                pd_j_tuple = tuple(
                    float(k_c / n_tot_w) if n_tot_w > 0 else 0.0
                    for k_c in w_counts
                )
            if self.pd_floor is not None:
                if K == 2:
                    # Phase 3.7.e (pre-1.0.0rc1): hard floor in binary.
                    # Applying the soft-floor renormalization to K=2 can push
                    # the class-of-interest PD BELOW pd_floor (BCBS CRE 32.4
                    # is a hard lower bound). In binary, assign the complement
                    # directly without renormalizing.
                    p0 = max(self.pd_floor, pd_j_tuple[0])
                    p1 = 1.0 - p0
                    if p1 < self.pd_floor:
                        p1 = self.pd_floor
                        p0 = 1.0 - p1
                    pd_f_tuple = (float(p0), float(p1))
                else:
                    # Multivariate soft floor + renormalization (design 3.1
                    # section 3.3, unchanged for K > 2).
                    temp = np.array(
                        [max(self.pd_floor, p) for p in pd_j_tuple], dtype=float
                    )
                    pd_f_tuple = tuple(float(x) for x in (temp / temp.sum()))
            else:
                pd_f_tuple = pd_j_tuple

            razon: str | None = None
            cfg: SplitConfig | None = None
            partes: list[np.ndarray] | None = None

            if self.max_depth is not None and depth >= self.max_depth:
                razon = "max_depth"
            elif n < 2 * self.min_child_size:
                razon = "min_child"
            else:
                cfg = self._engine.best_split(
                    X.iloc[idx], yv.iloc[idx], spec,
                    target_type=self._target_type,
                    weights=None if self._weights is None else w[idx],
                )  # excepciones PROPAGAN (fail-fast, no capturamos)
                if cfg is None:
                    razon = "sin_split"
                else:
                    partes = self._partition(X, idx, cfg)
                    # min_child_size mide FILAS FISICAS (sin cambios)
                    if any(len(p) < self.min_child_size for p in partes):
                        razon = "rama_insuficiente"  # rechazo del split entero
                        cfg = None
                    elif self._min_child_weight is not None:
                        # min_child_weight mide MASA PONDERADA (acumulativo
                        # con min_child_size; mismo criterio absoluto)
                        pesos_rama = [float(w[p].sum()) for p in partes]
                        if any(pr < self._min_child_weight for pr in pesos_rama):
                            razon = "rama_insuficiente"
                            cfg = None

            if razon is not None:
                nodos.append(TreeNode(
                    node_id=node_id, depth=depth, parent_id=parent_id,
                    n=n, n_events=n_events_tuple, pd_jeffreys=pd_j_tuple,
                    pd_final=pd_f_tuple, class_labels=class_labels_tuple,
                    is_leaf=True, split=None, child_ids=(), leaf_reason=razon,
                    w_events=w_events_tuple,
                ))
                self._log.debug(
                    "[builder] nodo %d HOJA (%s) n=%d n_events=%s pd=%s",
                    node_id, razon, n, n_events_tuple, pd_f_tuple,
                )
                continue

            k_child = len(partes)  # type: ignore[arg-type]
            child_ids = tuple(range(next_id, next_id + k_child))
            next_id += k_child
            nodos.append(TreeNode(
                node_id=node_id, depth=depth, parent_id=parent_id,
                n=n, n_events=n_events_tuple, pd_jeffreys=pd_j_tuple,
                pd_final=pd_f_tuple, class_labels=class_labels_tuple,
                is_leaf=False, split=cfg, child_ids=child_ids, leaf_reason=None,
                w_events=w_events_tuple,
            ))
            self._log.info(
                "[builder] nodo %d divide con %r en %d ramas (ids %s)",
                node_id, cfg.predictor, k_child, child_ids,  # type: ignore[union-attr]
            )
            for cid, part in zip(child_ids, partes):  # type: ignore[arg-type]
                cola.append((cid, node_id, depth + 1, part))

        metodo = self._method_name()
        modelo = TreeModel(
            root_id=0, nodes=tuple(nodos), method=metodo,
            params_fingerprint=fingerprint,
            class_labels=class_labels_tuple,
            target_class=self._target_class,
            target_class_index=0,
        )
        self._log.info(
            "[builder] arbol %s: %d nodos (%d hojas), fingerprint=%s",
            metodo, len(nodos), sum(nd.is_leaf for nd in nodos), fingerprint,
        )
        return modelo

    # ------------------------------------------------------------------

    def _partition(
        self, X: pd.DataFrame, idx: np.ndarray, cfg: SplitConfig
    ) -> list[np.ndarray]:
        """Reparte las filas idx segun el split (threshold o branches).

        Guard de integridad: la particion DEBE ser exacta (suma de ramas ==
        filas de entrada); cualquier fila huerfana es un bug del routing y
        se detecta aqui (p. ej. NaN residual no imputado).
        """
        col = X[cfg.predictor]
        if cfg.bin_edges:
            # H14 (Fase 3.10.b): routing por rangos numericos. np.digitize
            # asigna cada fila a un bin 0..len(edges) y cada bin se mapea a
            # su rama via las etiquetas "bin_i" de cfg.branches (las ramas
            # llegan ya fusionadas del motor: una parte por RAMA, no por
            # bin; la guarda de integridad de abajo detecta huerfanos).
            # TODO(zona_gris): el prompt pedia una parte por BIN
            # (range(len(bin_edges)+1)); eso desincronizaria el arbol de
            # cfg.branches/cfg.child_ns. Resolver si se prefiere otra cosa.
            vals = col.iloc[idx].to_numpy(dtype=float)
            bin_idx = np.digitize(vals, cfg.bin_edges)
            n_bins = len(cfg.bin_edges) + 1
            mapa = np.full(n_bins, -1, dtype=int)
            ramas = cfg.branches or ()
            for j, grupo in enumerate(ramas):
                for lbl in grupo:
                    mapa[int(str(lbl)[4:])] = j
            partes = [idx[mapa[bin_idx] == j] for j in range(len(ramas))]
        elif cfg.threshold is not None:
            vals = col.iloc[idx].to_numpy(dtype=float)
            izq = vals <= float(cfg.threshold)
            partes = [idx[izq], idx[~izq]]
        else:
            partes = []
            for grupo in cfg.branches or ():
                mask = col.iloc[idx].isin(list(grupo)).to_numpy()
                partes.append(idx[mask])
        total = sum(len(p) for p in partes)
        if total != len(idx):
            raise ValueError(
                f"[tree_builder] particion incompleta: {total} != {len(idx)} "
                f"(predictor {cfg.predictor!r})"
            )
        return partes

    def _method_name(self) -> str:
        cls = type(self._engine).__name__
        if cls == "ChaidEngine":
            return "CHAID_EXHAUSTIVE" if getattr(self._engine, "exhaustive", False) else "CHAID"
        if cls == "CrtEngine":
            return "CRT"
        if cls == "QuestEngine":
            return "QUEST"
        return cls

    def _governance_label(self) -> str:
        """Etiqueta del modo de gobernanza EFECTIVO (para el fingerprint).

        BANKING  = Jeffreys + floor; RESEARCH = cruda + sin floor; CUSTOM =
        cualquier combinacion intermedia (posible via API; la GUI solo emite
        BANKING/RESEARCH, el fingerprint registra la verdad computacional).
        """
        if self.apply_jeffreys and self.pd_floor is not None:
            return GovernanceMode.BANKING.name
        if not self.apply_jeffreys and self.pd_floor is None:
            return GovernanceMode.RESEARCH.name
        return "CUSTOM"

    def _fingerprint(
        self, spec: dict[str, PredictorType], class_labels: tuple[str, ...]
    ) -> str:
        """sha256 (16 hex) del dict canonico determinista.

        Incluye los hiperparametros PUBLICOS del motor (engine_params):
        dos ChaidEngine con alpha_merge distinto NO comparten fingerprint.
        Incluye el modo de gobernanza (Fase 2.1): dos arboles con distinto
        modo NO comparten fingerprint (trazabilidad MRM).

        Phase 3.1: the payload also records target_class,
        target_class_index, class_labels and n_classes. Two trees equal in
        everything except the class of interest do NOT share a fingerprint
        (MRM evidence that the class choice was explicit).
        """
        engine_params = {
            k: str(v) for k, v in sorted(vars(self._engine).items())
            if not k.startswith("_") and not callable(v)
        }
        payload = {
            "method": self._method_name(),
            "engine_params": engine_params,
            "spec": {k: v.name for k, v in sorted(spec.items())},
            "max_depth": self.max_depth if self.max_depth is not None else "None",
            "min_child_size": self.min_child_size,
            "governance_mode": self._governance_label(),
            "apply_jeffreys": self.apply_jeffreys,
            "pd_floor": self.pd_floor,  # None serializa como null (json)
            "seed": self.seed,
            "target_class": str(self._target_class),
            "target_class_index": 0,
            "class_labels": list(class_labels),
            "n_classes": len(class_labels),
            # Phase 3.2.e: weighting mode in the fingerprint (changes
            # pre-3.2 fingerprints; documented precedent: Phase 3.1)
            "weighted": self._weights is not None,
            "weight_col": self._weight_col,
            "min_child_weight": self._min_child_weight,
            "population_col": self._population_col,
            "population_ok_values": list(self._population_ok_values),
        }
        blob = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]
