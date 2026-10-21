"""Tests de backend_v3/pruning.py (Fase 1.2). Dual: pytest o python directo.

Secuencia de poda VERIFICADA A MANO sobre el fixture aprobado:
  y = [0]*6 + [1,0] + [1]*4  (12 filas), x = 1..12
Arbol real de CRT (min_child_size=1):
  id0 raiz (t=6.5) -> hijos 1,2; id1 hoja([0]*6); id2 (t=8.5) -> hijos 3,4
  id3 (t=7.5) -> hijos 5,6; id4 hoja([1]*4); id5 hoja(n=1); id6 hoja(n=1)
Estado inicial: hojas {1,4,5,6} -> R=0.
  g(nodo2) = (1 - 0)/(3 - 1) = 0.5   (subarbol vivo: hojas 3; r=1)
  g(nodo3) = (1 - 0)/(2 - 1) = 1.0
  g(raiz)  = (5 - 0)/(4 - 1) = 5/3
Paso 1: alpha=0.5 (podar nodo 2) -> hojas {1,2}, R = 0 + 1 = 1
Paso 2: alpha=4.0 (podar raiz)   -> 1 hoja,  R = 5
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.crt_engine import CrtEngine  # noqa: E402
from backend_v3.pruning import Pruner  # noqa: E402
from backend_v3.tree_builder import TreeBuilder, TreeModel  # noqa: E402
from backend_v3.types import PredictorType, TargetType  # noqa: E402

_BIN = TargetType.BINARY
_CONT = PredictorType.CONTINUOUS


def _assert_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:
        raise AssertionError(
            f"{fn.__name__} lanzo {type(e).__name__} en vez de {exc_type.__name__}: {e}"
        ) from e
    raise AssertionError(f"{fn.__name__} no lanzo {exc_type.__name__}")


def _modelo():
    x = pd.Series([float(i) for i in range(1, 13)])
    y = pd.Series([0, 0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 1])
    X = pd.DataFrame({"x": x})
    tb = TreeBuilder(CrtEngine(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"),
                     max_depth=4, min_child_size=1)
    return tb.build(X, y, {"x": _CONT})


def test_arbol_fixture_es_el_esperado():
    m = _modelo()
    assert len(m.nodes) == 7
    assert [nd.is_leaf for nd in m.nodes] == [False, True, False, False, True, True, True]
    assert m.nodes[0].split.threshold == 6.5
    assert m.nodes[2].split.threshold == 8.5
    assert m.nodes[3].split.threshold == 7.5


def test_secuencia_poda_manual():
    seq = Pruner().sequence(_modelo())
    assert len(seq) == 2
    assert math.isclose(seq[0].alpha, 0.5, rel_tol=1e-12)
    assert seq[0].n_leaves == 2 and seq[0].r_subtree == 1
    assert math.isclose(seq[1].alpha, 4.0, rel_tol=1e-12)
    assert seq[1].n_leaves == 1 and seq[1].r_subtree == 5


def test_prune_seleccion_alpha():
    m = _modelo()
    pr = Pruner()
    # alpha < 0.5: ningun paso aplicable -> modelo intacto
    assert pr.prune(m, 0.49) is m
    # alpha = 2: solo el paso 0.5 -> 3 nodos, nodo 2 colapsado como hoja
    m2 = pr.prune(m, 2.0)
    assert len(m2.nodes) == 3
    assert [nd.node_id for nd in m2.nodes] == [0, 1, 2]
    assert [nd.is_leaf for nd in m2.nodes] == [False, True, True]
    assert m2.nodes[2].leaf_reason == "podado"
    assert m2.nodes[0].child_ids == (1, 2)
    # alpha grande -> raiz sola
    m4 = pr.prune(m, 4.0)
    assert len(m4.nodes) == 1 and m4.nodes[0].is_leaf


def test_prune_determinista():
    m = _modelo()
    pr = Pruner()
    # determinismo absoluto: dos llamadas identicas
    assert pr.prune(m, 2.0) == pr.prune(m, 2.0)


def test_modelo_raiz_sola():
    x = pd.Series([1.0, 2.0, 3.0, 4.0])
    y = pd.Series([0, 0, 1, 1])
    tb = TreeBuilder(CrtEngine(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"),
                     max_depth=4, min_child_size=10)
    m = tb.build(pd.DataFrame({"x": x}), y, {"x": _CONT})
    assert len(m.nodes) == 1
    assert Pruner().sequence(m) == ()
    assert Pruner().prune(m, 1.0) is m


def test_guards():
    m = _modelo()
    _assert_raises(ValueError, Pruner().prune, m, -0.1)
    _assert_raises(ValueError, Pruner().prune, m, float("nan"))


def test_weighted_pruning_sequence():
    """Fase 3.9: la secuencia usa r_w(t) = sum(w_events) - max(w_events).

    Dos partes:
    (a) Estructura fijada a mano (el fixture de _modelo() con w_events
        inyectados via replace): la secuencia ponderada difiere de la
        de conteos y los valores se verifican a mano.
    (b) TreeBuilder con weights no uniformes: w_events poblado,
        r_subtree final = error ponderado de la raiz (a mano) y
        coherencia prune/sequence.
    Paridad: con weights=None el resultado es identico al pre-3.9.
    """
    from dataclasses import replace

    # (a) fixture con estructura fijada y masas ponderadas inyectadas
    m = _modelo()
    # masas: el no-evento del subarbol de id3 pasa de 1 a 4
    # (orden canonico: indice 0 = clase de interes = evento)
    w_inyectados = {
        0: (5.0, 10.0),  # raiz: 5 eventos, 7+3 no-eventos
        1: (0.0, 6.0),
        2: (5.0, 4.0),   # r_w = 9 - 5 = 4 (conteo: 1)
        3: (1.0, 4.0),   # r_w = 5 - 4 = 1 (conteo: 1)
        4: (4.0, 0.0),
        5: (1.0, 0.0),
        6: (0.0, 4.0),
    }
    nodos_w = tuple(
        replace(nd, w_events=w_inyectados[nd.node_id]) for nd in m.nodes
    )
    m_w = TreeModel(
        root_id=m.root_id, nodes=nodos_w, method=m.method,
        params_fingerprint=m.params_fingerprint,
        class_labels=m.class_labels,
        target_class=m.target_class,
        target_class_index=m.target_class_index,
    )
    seq_w = Pruner().sequence(m_w)
    # a mano (paso 1): g(id3) = (1-0)/1 = 1.0 < g(raiz) = 5/3 < g(id2) = 2.0
    #   -> poda id3; hojas {1,3,4}, R = r_w(id3) = 1
    # a mano (paso 2): g(raiz) = (5-1)/2 = 2.0 < g(id2) = (4-1)/1 = 3.0
    #   -> poda raiz; 1 hoja, R = r_w(raiz) = 5
    assert len(seq_w) == 2
    assert math.isclose(seq_w[0].alpha, 1.0, rel_tol=1e-12)
    assert seq_w[0].n_leaves == 3 and seq_w[0].r_subtree == 1.0
    assert math.isclose(seq_w[1].alpha, 2.0, rel_tol=1e-12)
    assert seq_w[1].n_leaves == 1 and seq_w[1].r_subtree == 5.0
    # difiere de la secuencia por conteos (0.5, 4.0)
    seq_u = Pruner().sequence(_modelo())
    assert [p.alpha for p in seq_w] != [p.alpha for p in seq_u]

    # (b) TreeBuilder con weights: w_events poblado y coherencia
    x = pd.Series([float(i) for i in range(1, 13)])
    y = pd.Series([0, 0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 1])
    X = pd.DataFrame({"x": x})
    w = np.ones(12)
    w[7] = 4.0
    tb = TreeBuilder(CrtEngine(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"),
                     max_depth=4, min_child_size=1, weights=w)
    m_b = tb.build(X, y, {"x": _CONT})
    assert all(nd.w_events for nd in m_b.nodes)
    seq_b = Pruner().sequence(m_b)
    root_w = m_b.nodes[0].w_events
    esperado_final = float(sum(root_w) - max(root_w))
    assert math.isclose(seq_b[-1].r_subtree, esperado_final, rel_tol=1e-12)
    assert seq_b[-1].n_leaves == 1
    m_p = Pruner().prune(m_b, seq_b[0].alpha)
    assert sum(1 for nd in m_p.nodes if nd.is_leaf) == seq_b[0].n_leaves

    # paridad: el fixture sin pesos mantiene los valores pre-3.9
    assert math.isclose(seq_u[0].alpha, 0.5, rel_tol=1e-12)
    assert math.isclose(seq_u[1].alpha, 4.0, rel_tol=1e-12)


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
