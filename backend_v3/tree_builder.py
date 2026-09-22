"""Constructor recursivo de arboles de decision (TreeGov, backend_v3, Fase 1).

Ensambla cualquiera de los 4 motores (ChaidEngine / ChaidEngine exhaustive /
CrtEngine / QuestEngine) en un arbol completo, determinista y auditable.

Reglas duras:
  - Crecimiento BFS con cola FIFO: los ids 0, 1, 2, ... se asignan por nivel
    y orden de expansion (determinista; nunca pila).
  - Routing multi-rama: branches (K >= 2 grupos, orden natural del motor) o
    threshold (izquierda: x <= t, derecha: x > t). CHAID puede producir
    K > 2; C&RT y QUEST son estrictamente binarios.
  - min_child_size es un PISO ABSOLUTO por rama: si ALGUNA rama del split
    propuesto quedara con menos de min_child_size filas, el split entero se
    rechaza (no hay fusion de respaldo; se documenta y el nodo queda hoja).
  - Si el motor lanza una excepcion, TreeBuilder la PROPAGA (fail-fast):
    nunca se traduce a hoja (el error no se disfraza de decision analitica).
  - PD por nodo: estimador de Jeffreys (k + 0.5) / (n + 1.0) y
    pd_final = max(pd_floor, pd_jeffreys)   [BCBS CRE 20.39].
    La PD OPERATIVA solo es la de las hojas (is_leaf=True); la de nodos
    internos se expone solo con fines de trazabilidad.
  - Determinismo estructural: dos build() con los mismos datos y parametros
    producen TreeModel identicos (==). params_fingerprint es un sha256
    estable (json con claves ordenadas; nada de direcciones de memoria).
    El event_log NO vive en TreeModel: vive en SessionState (session_state).

Dependencias permitidas: numpy, pandas, stdlib + motores de backend_v3.
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
from .types import PredictorType, SplitConfig, TargetType

__all__ = ["TreeNode", "TreeModel", "TreeBuilder"]


@dataclass(frozen=True)
class TreeNode:
    """Nodo del arbol. Inmutable y hashable (salvo split, hashable el mismo)."""

    node_id: int
    depth: int
    parent_id: int | None
    n: int
    n_events: int
    pd_jeffreys: float  # (k + 0.5) / (n + 1)
    pd_final: float     # max(pd_floor, pd_jeffreys); operativa solo en hojas
    is_leaf: bool
    split: SplitConfig | None
    child_ids: tuple[int, ...]
    leaf_reason: str | None  # None en internos; "max_depth" | "min_child" |
                             # "sin_split" | "rama_insuficiente" en hojas


@dataclass(frozen=True)
class TreeModel:
    """Arbol completo e inmutable. Determinista; sin timestamps."""

    root_id: int
    nodes: tuple[TreeNode, ...]  # indexado por node_id (0..len-1)
    method: str
    params_fingerprint: str

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("[TreeModel] sin nodos")
        ids = [nd.node_id for nd in self.nodes]
        if ids != list(range(len(ids))):
            raise ValueError("[TreeModel] node_id debe ser 0..n-1 en orden")
        raiz = self.nodes[self.root_id]
        if raiz.parent_id is not None:
            raise ValueError("[TreeModel] la raiz tiene parent_id")
        for nd in self.nodes:
            if nd.n_events > nd.n:
                raise ValueError(
                    f"[TreeModel] nodo {nd.node_id}: n_events={nd.n_events} > n={nd.n}"
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
        max_depth: int | None = 4,
        min_child_size: int = 50,
        pd_floor: float = 0.0003,
        seed: int | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """max_depth=None -> modo grow_full (crece hasta min_child_size).

        Ese modo existe para alimentar la poda coste-complejidad
        (Breiman et al. 1984, §3) de backend_v3.pruning; sin poda, usar el
        default 4 (pre-pruning)."""
        if not hasattr(engine, "best_split"):
            raise TypeError("engine debe exponer best_split(X, y, spec, ...)")
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
        if isinstance(pd_floor, bool) or not (0.0 <= float(pd_floor) < 1.0):
            raise ValueError(f"pd_floor fuera de [0, 1): {pd_floor!r}")
        self._engine = engine
        self._target_type = target_type
        self.max_depth = int(max_depth)
        self.min_child_size = int(min_child_size)
        self.pd_floor = float(pd_floor)
        self.seed = seed
        self._log = logger if logger is not None else get_logger("builder")

    # ------------------------------------------------------------------

    def build(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        spec: dict[str, PredictorType],
    ) -> TreeModel:
        """Construye el arbol completo. Las excepciones del motor se propagan."""
        if not spec:
            raise ValueError("[tree_builder] spec vacio")
        if len(X) != len(y) or len(X) == 0:
            raise ValueError("[tree_builder] X e y invalidos o de distinta longitud")

        # Fase 1: target obligatoriamente 0/1 (la PD de hojas exige la clase
        # de evento = 1; validado aqui en un solo punto)
        yv = pd.Series(y)
        if set(pd.unique(yv)) != {0, 1}:
            raise ValueError(
                "[tree_builder] target fuera de {0, 1}; en Fase 1 el arbol "
                "exige variable binaria con evento = 1"
            )
        ycodes = yv.to_numpy(dtype=np.int64)

        fingerprint = self._fingerprint(spec)
        nodos: list[TreeNode] = []
        cola: deque[tuple[int, int | None, int, np.ndarray]] = deque()
        cola.append((0, None, 0, np.arange(len(X))))
        next_id = 1

        while cola:
            node_id, parent_id, depth, idx = cola.popleft()  # FIFO BFS
            Yn = ycodes[idx]
            n = int(len(idx))
            k_ev = int(Yn.sum())
            pd_j = (k_ev + 0.5) / (n + 1.0)
            pd_f = max(self.pd_floor, pd_j)

            razon: str | None = None
            cfg: SplitConfig | None = None
            partes: list[np.ndarray] | None = None

            if self.max_depth is not None and depth >= self.max_depth:
                razon = "max_depth"
            elif n < 2 * self.min_child_size:
                razon = "min_child"
            else:
                cfg = self._engine.best_split(
                    X.iloc[idx], yv.iloc[idx], spec, target_type=self._target_type
                )  # excepciones PROPAGAN (fail-fast, no capturamos)
                if cfg is None:
                    razon = "sin_split"
                else:
                    partes = self._partition(X, idx, cfg)
                    if any(len(p) < self.min_child_size for p in partes):
                        razon = "rama_insuficiente"  # rechazo del split entero
                        cfg = None

            if razon is not None:
                nodos.append(TreeNode(
                    node_id=node_id, depth=depth, parent_id=parent_id,
                    n=n, n_events=k_ev, pd_jeffreys=pd_j, pd_final=pd_f,
                    is_leaf=True, split=None, child_ids=(), leaf_reason=razon,
                ))
                self._log.debug(
                    "[builder] nodo %d HOJA (%s) n=%d k=%d pd=%.6g",
                    node_id, razon, n, k_ev, pd_f,
                )
                continue

            k_child = len(partes)  # type: ignore[arg-type]
            child_ids = tuple(range(next_id, next_id + k_child))
            next_id += k_child
            nodos.append(TreeNode(
                node_id=node_id, depth=depth, parent_id=parent_id,
                n=n, n_events=k_ev, pd_jeffreys=pd_j, pd_final=pd_f,
                is_leaf=False, split=cfg, child_ids=child_ids, leaf_reason=None,
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
        if cfg.threshold is not None:
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

    def _fingerprint(self, spec: dict[str, PredictorType]) -> str:
        """sha256 (16 hex) del dict canonico determinista.

        Incluye los hiperparametros PUBLICOS del motor (engine_params):
        dos ChaidEngine con alpha_merge distinto NO comparten fingerprint.
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
            "pd_floor": self.pd_floor,
            "seed": self.seed,
        }
        blob = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]
