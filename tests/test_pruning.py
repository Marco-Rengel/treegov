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
from backend_v3.tree_builder import TreeBuilder  # noqa: E402
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
                     max_depth=4, min_child_size=10)
    m = tb.build(pd.DataFrame({"x": x}), y, {"x": _CONT})
    assert len(m.nodes) == 1
    assert Pruner().sequence(m) == ()
    assert Pruner().prune(m, 1.0) is m


def test_guards():
    m = _modelo()
    _assert_raises(ValueError, Pruner().prune, m, -0.1)
    _assert_raises(ValueError, Pruner().prune, m, float("nan"))


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
