"""Poda coste-complejidad (TreeGov, backend_v3, Fase 1.2).

Breiman, Friedman, Olshen & Stone (1984), "Classification and Regression
Trees", cap. 3: para cada nodo interno t con subarbol vivo T_t,

    g(t) = (r(t) - R(T_t)) / (|T_t| - 1)
    r(t)   = min(k_t, n_t - k_t)          # errores por regla de mayoria
    R(T_t) = suma de r(hoja) sobre las hojas vivas del subarbol
    |T_t|  = nº de hojas vivas del subarbol

NOTA de convencion: r(t) se usa en forma de CONTEO (no la forma ponderada
p(t) * r(t) de Breiman). Como el factor de escala es comun a todos los
nodos en un mismo arbol, la secuencia de poda (el orden de g) es identica;
solo cambian las unidades de alpha (aqui: errores enteros).

Reglas:
  * En cada paso se podan TODOS los nodos cuyo g empata con el minimo
    (convencion de Breiman; empates simultaneos).
  * La secuencia termina cuando queda solo la raiz; el ultimo PruneStep
    corresponde a la poda final de la raiz.
  * prune(alpha): devuelve T(alpha) = el ultimo arbol cuyos pasos aplicados
    tienen alpha_k <= alpha (el "mas podado que aun resiste alpha"). Si
    alpha >= alpha del ultimo paso, el resultado es la raiz sola.
    Sobre un modelo de raiz sola: no hay pasos, se devuelve el mismo modelo.
  * La poda REINDEXA los ids (0..m-1, BFS) y reconstruye un TreeModel
    estrictamente valido; hojas nuevas reciben leaf_reason="podado".
  * prune() siempre parte del modelo original recibido: es idempotente por
    contrato (jamás apila podas sobre un arbol ya podado).

Validacion cruzada k-fold y regla 1-SE: aplazadas a Fase 1.3 (documentado;
la API no contiene parametros muertos).

Dependencias: stdlib + numpy/pandas solo via estructuras del modelo.

Fase 3.1 (multiclass): r(t) is defined as n - max(n_events), the
number of rows that do not belong to the modal class. For K=2 this
reduces exactly to min(k, n-k). See docs/3.1_design_multiclass.md §1.

Fase 3.9 (weighted pruning): if ``TreeNode.w_events`` is populated,
r(t) uses the weighted mass, r_w(t) = sum(w_events) - max(w_events),
coherent with the weighted-Gini growth (Phase 3.2). If ``w_events``
is empty (hand-built nodes), the original count form applies. With
unit weights both forms coincide numerically (parity).
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass

from .log_config import get_logger
from .tree_builder import TreeModel, TreeNode

__all__ = ["PruneStep", "Pruner"]


@dataclass(frozen=True)
class PruneStep:
    """Un eslabon de la secuencia de poda."""

    alpha: float
    n_leaves: int      # hojas del arbol DESPUES de este paso
    r_subtree: float   # errores totales del arbol DESPUES de este paso
                       # (int si el arbol no pondera; float si pondera,
                       # Fase 3.9)


class Pruner:
    """Secuencia de poda coste-complejidad y seleccion por alpha manual."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._log = logger if logger is not None else get_logger("pruning")

    # ------------------------------------------------------------------
    # estado vivo mutable (solo dentro de una corrida)
    # ------------------------------------------------------------------

    @staticmethod
    def _estado_vivo(model: TreeModel):
        """Mapas mutables: children (lista de hijos vivos) por nodo."""
        return {nd.node_id: list(nd.child_ids) for nd in model.nodes}

    @staticmethod
    def _errores_nodo(nd: TreeNode) -> float:
        """Errores del nodo como hoja (regla de mayoria).

        Fase 3.9: si ``w_events`` esta poblado, usa la masa ponderada
        r_w(t) = sum(w_events) - max(w_events) (coherente con el
        crecimiento ponderado del arbol). Si esta vacio (nodos
        construidos a mano en tests), usa el conteo fisico original
        r(t) = n - max(n_events). Con pesos unitarios ambas formas
        coinciden numericamente (paridad pre-3.9).
        """
        if nd.w_events:
            return float(sum(nd.w_events) - max(nd.w_events))
        return float(nd.n - max(nd.n_events))

    @staticmethod
    def _hojas_errores(model: TreeModel, children, nid: int) -> tuple[int, float]:
        """(n_hojas, errores) del subarbol vivo enraizado en nid."""
        if not children[nid]:
            return 1, Pruner._errores_nodo(model.nodes[nid])
        hojas = 0
        err = 0
        for cid in children[nid]:
            h_, e_ = Pruner._hojas_errores(model, children, cid)
            hojas += h_
            err += e_
        return hojas, err

    @staticmethod
    def _eliminar_descendientes(children: dict[int, list[int]], nid: int) -> None:
        """Elimina TODAS las claves del subarbol de nid (excepto el propio
        nid). Sin esto, los descendientes quedan inalcanzables pero vivos y
        producen pasos espurios en la secuencia de poda."""
        hijos = children.get(nid, [])
        children[nid] = []
        for cid in hijos:
            Pruner._eliminar_descendientes(children, cid)
            children.pop(cid, None)

    def _paso(self, model: TreeModel, children) -> tuple[float, list[int]] | None:
        """Devuelve (alpha_k, nodos a podar) o None si no hay interno valido.

        Un nodo es interno vivo si tiene hijos en el estado vivo; los
        descendientes de nodos ya podados no estan en el mapa (ver
        _eliminar_descendientes)"""
        g_map: dict[int, float] = {}
        for nid, hijos in children.items():
            if not hijos:
                continue
            hojas, err_sub = self._hojas_errores(model, children, nid)
            if hojas <= 1:
                continue
            r_t = self._errores_nodo(model.nodes[nid])
            g_map[nid] = (r_t - err_sub) / (hojas - 1)
        if not g_map:
            return None
        alpha_k = min(g_map.values())
        podar = [nid for nid, g in g_map.items() if abs(g - alpha_k) <= 1e-15]
        return alpha_k, podar

    def sequence(self, model: TreeModel) -> tuple[PruneStep, ...]:
        """Secuencia completa de poda (el ultimo paso es la raiz sola)."""
        if len(model.nodes) == 1:
            return ()
        children = self._estado_vivo(model)
        pasos: list[PruneStep] = []
        while True:
            paso = self._paso(model, children)
            if paso is None:
                break
            alpha_k, podables = paso
            for nid in podables:
                self._eliminar_descendientes(children, nid)
            # medir el arbol vivo resultante
            if not children[model.root_id]:
                n_hojas, err = 1, self._errores_nodo(model.nodes[model.root_id])
            else:
                n_hojas, err = self._hojas_errores(
                    model, children, model.root_id
                )
            pasos.append(PruneStep(float(alpha_k), int(n_hojas), float(err)))
            self._log.debug(
                "[prune] paso: alpha=%.6g -> %d hojas, R=%.6g (podados: %s)",
                alpha_k, n_hojas, err, podables,
            )
        return tuple(pasos)

    # ------------------------------------------------------------------

    def prune(self, model: TreeModel, alpha: float) -> TreeModel:
        """T(alpha) con reindexado BFS; idempotente por contrato."""
        if isinstance(alpha, bool) or not math.isfinite(float(alpha)) \
                or float(alpha) < 0.0:
            raise ValueError(f"[pruning] alpha invalido: {alpha!r}")
        alpha = float(alpha)

        children = self._estado_vivo(model)
        podados: set[int] = set()
        while True:
            paso = self._paso(model, children)
            if paso is None:
                break
            alpha_k, podables = paso
            if alpha_k > alpha + 1e-15:
                break  # el siguiente paso excede alpha: parado aqui
            for nid in podables:
                self._eliminar_descendientes(children, nid)
                podados.add(nid)
        if not podados:
            self._log.info(
                "[pruning] alpha=%.6g: ningun paso aplicable -> modelo intacto",
                alpha,
            )
            return model
        return self._rebuild(model, children, alpha)

    # ------------------------------------------------------------------

    def _rebuild(
        self,
        model: TreeModel,
        children: dict[int, list[int]],
        alpha: float,
    ) -> TreeModel:
        """Nuevo TreeModel con ids reindexados 0..m-1 por BFS desde la raiz.

        Los metadatos se heredan del nodo original (n, n_events, pd_jeffreys, pd_final, class_labels);
        depth/parent_id se recalculan; las hojas creadas por la poda reciben
        leaf_reason="podado"; las preexistentes conservan su razon.
        """
        mapa: dict[int, int] = {}
        orden: list[int] = []
        cola: deque[int] = deque([model.root_id])
        while cola:
            nid = cola.popleft()
            if nid in mapa:
                continue
            mapa[nid] = len(orden)
            orden.append(nid)
            for cid in children[nid]:
                cola.append(cid)

        nuevos: list[TreeNode] = []
        # depth/parent: por nivel BFS. hijos vivor -> child_ids del mapa.
        depth_v: dict[int, int] = {model.root_id: 0}
        parent_v: dict[int, int | None] = {model.root_id: None}
        for pos, nid in enumerate(orden):
            pid = parent_v[nid]
            for cid in children[nid]:
                depth_v[cid] = depth_v[nid] + 1
                parent_v[cid] = nid
            nd = model.nodes[nid]
            es_hoja = not children[nid]
            nuevos.append(TreeNode(
                node_id=mapa[nid],
                depth=depth_v[nid],
                parent_id=(None if pid is None else mapa[pid]),
                n=nd.n,
                n_events=nd.n_events,
                pd_jeffreys=nd.pd_jeffreys,
                pd_final=nd.pd_final,
                class_labels=nd.class_labels,
                is_leaf=es_hoja,
                split=None if es_hoja else nd.split,
                child_ids=tuple(mapa[c] for c in children[nid]),
                leaf_reason=(
                    "podado" if (es_hoja and nd.child_ids) else nd.leaf_reason
                ),
            ))
        fp = f"{model.params_fingerprint}-p{alpha:.12g}"
        modelo = TreeModel(
            root_id=0, nodes=tuple(nuevos), method=model.method,
            params_fingerprint=fp,
            class_labels=model.class_labels,
            target_class=model.target_class,
            target_class_index=model.target_class_index,
        )
        self._log.info(
            "[pruning] alpha=%.6g: %d -> %d nodos (%d hojas)",
            alpha, len(model.nodes), len(nuevos),
            sum(1 for nd in nuevos if nd.is_leaf),
        )
        return modelo
