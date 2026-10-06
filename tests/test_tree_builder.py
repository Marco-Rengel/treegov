"""Tests de backend_v3/tree_builder.py (Fase 1).

Valores verificados a mano:

  Fixture A (CRT): x=[1..10], y=[0]x5+[1]x5 -> t=5.5, dI=0.5.
      hoja izq: n=5, k=0 -> pd_j = 0.5/6 ; hoja der null: pd_j = 5.5/6.
  Fixture BFS (CRT): ids [0..4], depths [0,1,1,2,2] (verificado a mano).
  Fixture C: x=[1]x95+[100]x5, y=[0]x95+[1]x5 -> mejor corte t=50.5 con
      dI=0.095; rama der tiene n=5 < min_child_size=6 -> split rechazado
      completo -> raiz hoja con razon "rama_insuficiente".
  Fixture CHAID: categorias a (40 ceros), b (16 ceros+24 unos), c (40 unos);
      sin fusion (todos los pares significativos) -> raiz con 3 ramas.

Dual: pytest o python directo.
"""

import logging
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.chaid_engine import ChaidEngine  # noqa: E402
from backend_v3.crt_engine import CrtEngine  # noqa: E402
from backend_v3.quest_engine import QuestEngine  # noqa: E402
from backend_v3.tree_builder import TreeBuilder, TreeModel  # noqa: E402
from backend_v3.types import PredictorType, TargetType  # noqa: E402

_BIN = TargetType.BINARY
_CONT = PredictorType.CONTINUOUS
_NOM = PredictorType.NOMINAL


def _quiet_engine(cls, **kw):
    quiet = logging.getLogger(f"treegov.{cls.__name__}.tests")
    if not quiet.handlers:
        quiet.addHandler(logging.NullHandler())
    quiet.propagate = False
    kw.setdefault("logger", quiet)
    return cls(**kw)


def _crt():
    return _quiet_engine(CrtEngine)


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


# ---------------------------------------------------------------------------
# estructura basica y PD de Jeffreys
# ---------------------------------------------------------------------------


def test_fixture_a_estructura_y_pd():
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    tb = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"), max_depth=4,
                     min_child_size=2, pd_floor=0.0003)
    modelo = tb.build(X, y, {"x": _CONT})

    assert isinstance(modelo, TreeModel)
    assert modelo.method == "CRT"
    assert modelo.root_id == 0
    assert len(modelo.nodes) == 3

    raiz, izq, der = modelo.nodes
    assert raiz.node_id == 0 and raiz.depth == 0 and raiz.parent_id is None
    assert not raiz.is_leaf
    assert raiz.split is not None and raiz.split.threshold == 5.5
    assert raiz.split.predictor == "x"
    assert raiz.child_ids == (1, 2)
    assert raiz.n == 10 and raiz.n_events == (5, 5)
    assert math.isclose(raiz.pd_jeffreys[0], 5.5 / 11.0, rel_tol=1e-12)
    assert math.isclose(raiz.pd_final[0], 0.5, rel_tol=1e-12)

    assert izq.node_id == 1 and izq.depth == 1 and izq.parent_id == 0
    assert izq.is_leaf and izq.leaf_reason == "sin_split"
    assert izq.n == 5 and izq.n_events == (0, 5)
    assert math.isclose(izq.pd_jeffreys[0], 0.5 / 6.0, rel_tol=1e-12)
    assert izq.pd_final[0] > 0.0                   # jamas 0 (Jeffreys + floor)
    assert math.isclose(der.pd_jeffreys[0], 5.5 / 6.0, rel_tol=1e-12)


def test_bfs_ids_y_niveles():
    # ids estrictamente 0,1,2,... asignados por nivel (BFS FIFO)
    x = pd.Series([1.0] * 4 + [2.0] * 4 + [3.0] * 4 + [4.0] * 4)
    y = pd.Series([0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1])
    X = pd.DataFrame({"x": x})
    tb = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"), max_depth=3,
                     min_child_size=4)
    m = tb.build(X, y, {"x": _CONT})
    assert [nd.node_id for nd in m.nodes] == [0, 1, 2, 3, 4]
    assert [nd.depth for nd in m.nodes] == [0, 1, 1, 2, 2]
    assert [nd.is_leaf for nd in m.nodes] == [False, True, False, True, True]
    assert m.nodes[0].child_ids == (1, 2)
    assert m.nodes[2].child_ids == (3, 4)


def test_min_child_rechaza_split_completo():
    # corte perfecto PERO rama derecha n=5 < min_child_size=6 -> hoja raiz
    x = pd.Series([1.0] * 95 + [100.0] * 5)
    y = pd.Series([0] * 95 + [1] * 5)
    X = pd.DataFrame({"x": x})
    tb = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"), max_depth=4,
                     min_child_size=6)
    m = tb.build(X, y, {"x": _CONT})
    assert len(m.nodes) == 1
    assert m.nodes[0].is_leaf
    assert m.nodes[0].leaf_reason == "rama_insuficiente"


def test_max_depth_y_min_child_en_raiz():
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    # max_depth=1: hijos son hojas por profundidad
    m1 = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"), max_depth=1,
                     min_child_size=2).build(X, y, {"x": _CONT})
    assert len(m1.nodes) == 3
    assert all(nd.is_leaf for nd in m1.nodes[1:])
    assert all(nd.leaf_reason == "max_depth" for nd in m1.nodes[1:])
    # min_child: raiz n=10 < 2*6 -> hoja "min_child"
    m2 = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"), max_depth=4,
                     min_child_size=7).build(X, y, {"x": _CONT})
    assert len(m2.nodes) == 1
    assert m2.nodes[0].leaf_reason == "min_child"


def test_chaid_multirama():
    x = pd.Series(["a"] * 40 + ["b"] * 40 + ["c"] * 40)
    y = pd.Series([0] * 40 + [0] * 16 + [1] * 24 + [1] * 40)
    X = pd.DataFrame({"nivel": x})
    tb = TreeBuilder(_quiet_engine(ChaidEngine), target_type=_BIN,
                     target_class=1, class_labels=("Event", "Non-event"),
                     max_depth=3, min_child_size=10)
    m = tb.build(X, y, {"nivel": _NOM})
    assert m.method == "CHAID"
    raiz = m.nodes[0]
    assert not raiz.is_leaf
    assert raiz.split is not None and raiz.split.branches is not None
    assert len(raiz.child_ids) == 3          # CHAID produce K > 2
    assert len(m.nodes) == 4
    assert [nd.n for nd in m.nodes[1:]] == [40, 40, 40]


def test_builds_con_cada_motor_son_validos():
    x = pd.Series([float(i) for i in range(1, 21)] * 3)
    y = pd.Series(([0] * 10 + [1] * 10) * 3)
    X = pd.DataFrame({"x": x})
    for eng in (_crt(), _quiet_engine(QuestEngine)):
        m = TreeBuilder(eng, target_type=_BIN, target_class=1,
                        class_labels=("Event", "Non-event"), max_depth=4,
                        min_child_size=5).build(X, y, {"x": _CONT})
        assert len(m.nodes) >= 3
        assert m.nodes[0].split is not None
    # CHAID exhaustive sobre la misma senial con una clave ordinal
    xo = pd.Series([1] * 30 + [2] * 30)
    yo = pd.Series([0] * 25 + [1] * 5 + [1] * 25 + [0] * 5)
    m = TreeBuilder(_quiet_engine(ChaidEngine, exhaustive=True),
                    target_type=_BIN, target_class=1,
                    class_labels=("Event", "Non-event"),
                    max_depth=4, min_child_size=5).build(
        pd.DataFrame({"b": xo}), yo, {"b": PredictorType.ORDINAL}
    )
    assert m.method == "CHAID_EXHAUSTIVE"


def test_determinismo_fingerprint():
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    tb1 = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                      class_labels=("Event", "Non-event"),
                      max_depth=4, min_child_size=2)
    tb2 = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                      class_labels=("Event", "Non-event"),
                      max_depth=4, min_child_size=2)
    m1, m2 = tb1.build(X, y, {"x": _CONT}), tb2.build(X, y, {"x": _CONT})
    assert m1 == m2  # estructura completa identica (event_log NO vive aqui)
    assert m1.params_fingerprint == m1.params_fingerprint == m2.params_fingerprint
    # cambiar un parametro cambia el fingerprint
    tb3 = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                      class_labels=("Event", "Non-event"),
                      max_depth=5, min_child_size=2)
    assert tb3.build(X, y, {"x": _CONT}).params_fingerprint != m1.params_fingerprint


def test_fingerprint_incluye_hiperparametros_del_motor():
    # FIX obligatorio: dos ChaidEngine con alpha_merge distinto -> fingerprints
    # distintos (auditabilidad MRM).
    spec = {"b": PredictorType.ORDINAL}
    eng1 = ChaidEngine(alpha_merge=0.05)
    eng2 = ChaidEngine(alpha_merge=0.10)
    tb1 = TreeBuilder(eng1, target_type=_BIN, target_class=1,
                      class_labels=("Event", "Non-event"),
                      max_depth=4, min_child_size=5)
    tb2 = TreeBuilder(eng2, target_type=_BIN, target_class=1,
                      class_labels=("Event", "Non-event"),
                      max_depth=4, min_child_size=5)
    labels = ("Event", "Non-event")
    assert tb1._fingerprint(spec, labels) != tb2._fingerprint(spec, labels)
    # determinismo interno: mismo motor, mismo fingerprint
    assert tb1._fingerprint(spec, labels) == TreeBuilder(
        ChaidEngine(alpha_merge=0.05), target_type=_BIN, target_class=1,
        class_labels=("Event", "Non-event"),
        max_depth=4, min_child_size=5,
    )._fingerprint(spec, labels)


def test_regla_min_child_es_2x_no_3x():
    # Evidencia OBS 5 (rechazada): con min_child=4 y n=10, el pre-check 2*min
    # (8 <= 10) PERMITE el split binario 5/5. Si fuese 3*min (12) se perderia.
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    m = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                    class_labels=("Event", "Non-event"), max_depth=4,
                    min_child_size=4).build(X, y, {"x": _CONT})
    assert len(m.nodes) == 3            # split realizado
    assert not m.nodes[0].is_leaf
    assert m.nodes[0].split is not None


def test_guards_treemodel():
    # Fase 3.1: n_events / pd_jeffreys / pd_final son tuples (K componentes),
    # y TreeNode/TreeModel llevan el campo class_labels. Los fixtures usan K=2
    # con labels neutros para probar los invariantes.
    _labels = ("Event", "Non-event")
    from backend_v3.tree_builder import TreeNode
    hoja_ok = dict(depth=1, parent_id=0, n=5, n_events=(2, 3),
                   pd_jeffreys=(0.4, 0.6), pd_final=(0.4, 0.6),
                   class_labels=_labels, is_leaf=True, split=None, child_ids=(),
                   leaf_reason="sin_split")
    raiz0 = TreeNode(node_id=0, depth=0, parent_id=None, n=10, n_events=(5, 5),
                     pd_jeffreys=(0.5, 0.5), pd_final=(0.5, 0.5),
                     class_labels=_labels, is_leaf=True, split=None,
                     child_ids=(), leaf_reason="sin_split")
    # nodo 1 declarado pero inalcanzable desde la raiz (raiz es hoja): ValueError
    nodo1 = TreeNode(node_id=1, **hoja_ok)
    _assert_raises(ValueError, TreeModel, 0, (raiz0, nodo1), "CRT", "fp",
                   _labels, 1, 0)
    # n_events[c] > n para alguna clase
    nodo_malo = TreeNode(node_id=0, depth=0, parent_id=None, n=5, n_events=(7, -2),
                         pd_jeffreys=(0.5, 0.5), pd_final=(0.5, 0.5),
                         class_labels=_labels, is_leaf=True,
                         split=None, child_ids=(), leaf_reason="sin_split")
    _assert_raises(ValueError, TreeModel, 0, (nodo_malo,), "CRT", "fp",
                   _labels, 1, 0)
    # hijo con parent_id incoherente
    raiz_int = TreeNode(node_id=0, depth=0, parent_id=None, n=10, n_events=(5, 5),
                        pd_jeffreys=(0.5, 0.5), pd_final=(0.5, 0.5),
                        class_labels=_labels, is_leaf=False,
                        split=_dummy_split(), child_ids=(1,), leaf_reason=None)
    hijo_mal = TreeNode(node_id=1, depth=1, parent_id=99, n=5, n_events=(2, 3),
                        pd_jeffreys=(0.4, 0.6), pd_final=(0.4, 0.6),
                        class_labels=_labels, is_leaf=True, split=None,
                        child_ids=(), leaf_reason="sin_split")
    _assert_raises(ValueError, TreeModel, 0, (raiz_int, hijo_mal), "CRT", "fp",
                   _labels, 1, 0)


def _dummy_split():
    from backend_v3.types import SplitConfig
    return SplitConfig(
        predictor="x", method="CRT", statistic=0.1, statistic_name="gini_gain",
        df=(), parent_n=10, child_ns=(5, 5), threshold=5.5, impurity_gain=0.1,
    )


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def test_guards_builder():
    class _Explota:
        def best_split(self, *a, **k):
            raise ValueError("boom")

    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    # excepcion del motor PROPAGA (fail-fast)
    _assert_raises(
        ValueError,
        TreeBuilder(_Explota(), target_type=_BIN, target_class=1,
                    class_labels=("Event", "Non-event"), max_depth=4,
                    min_child_size=2).build,
        X, y, {"x": _CONT},
    )
    _assert_raises(
        ValueError, TreeBuilder, _crt(), target_type=_BIN, target_class=1,
        class_labels=("Event", "Non-event"), max_depth=0,
    )
    _assert_raises(
        ValueError, TreeBuilder, _crt(), target_type=_BIN, target_class=1,
        class_labels=("Event", "Non-event"), min_child_size=0,
    )
    _assert_raises(
        ValueError, TreeBuilder, _crt(), target_type=_BIN, target_class=1,
        class_labels=("Event", "Non-event"), pd_floor=1.5,
    )
    # Fase 3.1: target_class fuera de las clases observadas -> ValueError
    _assert_raises(
        ValueError,
        TreeBuilder(_crt(), target_type=_BIN, target_class=99,
                    class_labels=("Event", "Non-event")).build,
        X, y, {"x": _CONT},
    )
    # Fase 3.1: spec vacio -> ValueError
    _assert_raises(
        ValueError,
        TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                    class_labels=("Event", "Non-event")).build,
        X, y, {},
    )


# ---------------------------------------------------------------------------
# Fase 2.1: Governance Mode (BANKING / RESEARCH)
# ---------------------------------------------------------------------------


def test_governance_banking_default():
    """Default = BANKING: Jeffreys (k+0.5)/(n+1) y floor 0.0003."""
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    tb = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"),
                     max_depth=4, min_child_size=2)
    assert tb.apply_jeffreys is True and tb.pd_floor == 0.0003
    m = tb.build(X, y, {"x": _CONT})
    izq = m.nodes[1]                       # hoja pura: k=0, n=5
    assert math.isclose(izq.pd_jeffreys[0], 0.5 / 6.0, rel_tol=1e-12)
    assert math.isclose(izq.pd_final[0], max(0.0003, 0.5 / 6.0), rel_tol=1e-12)
    assert tb._governance_label() == "BANKING"


def test_governance_research_raw_pd():
    """RESEARCH: PD cruda k/n, SIN floor -> una hoja pura puede ser 0.0."""
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    tb = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"),
                     max_depth=4, min_child_size=2,
                     apply_jeffreys=False, pd_floor=None)
    m = tb.build(X, y, {"x": _CONT})
    izq, der = m.nodes[1], m.nodes[2]
    assert izq.pd_jeffreys[0] == 0.0       # k/n = 0/5 (crudo, sin suavizado)
    assert izq.pd_final[0] == 0.0          # sin floor: el 0 respira
    assert math.isclose(der.pd_jeffreys[0], 1.0, rel_tol=1e-12)   # 5/5
    assert der.pd_final[0] == 1.0
    assert tb._governance_label() == "RESEARCH"


def test_fingerprint_distingue_modos():
    """MRM: dos arboles con distinto governance mode NO comparten fingerprint."""
    spec = {"x": _CONT}
    labels = ("Event", "Non-event")
    base = dict(target_type=_BIN, target_class=1,
                class_labels=("Event", "Non-event"),
                max_depth=4, min_child_size=2)
    fp_banking = TreeBuilder(_crt(), **base)._fingerprint(spec, labels)
    fp_research = TreeBuilder(_crt(), apply_jeffreys=False,
                              pd_floor=None, **base)._fingerprint(spec, labels)
    fp_custom = TreeBuilder(_crt(), apply_jeffreys=False,
                            pd_floor=0.0003, **base)._fingerprint(spec, labels)
    assert len({fp_banking, fp_research, fp_custom}) == 3
    tb_custom = TreeBuilder(_crt(), apply_jeffreys=False,
                            pd_floor=0.0003, **base)
    assert tb_custom._governance_label() == "CUSTOM"


def test_guards_governance():
    # apply_jeffreys no bool -> ValueError
    _assert_raises(
        ValueError, TreeBuilder, _crt(), target_type=_BIN, target_class=1,
        class_labels=("Event", "Non-event"), apply_jeffreys="yes",
    )
    # pd_floor negativo -> ValueError; None explicito es valido
    _assert_raises(
        ValueError, TreeBuilder, _crt(), target_type=_BIN, target_class=1,
        class_labels=("Event", "Non-event"), pd_floor=-0.1,
    )
    tb = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"), pd_floor=None)
    assert tb.pd_floor is None


def test_grow_full_max_depth_none():
    """max_depth=None permite crecer mas alla de 4 niveles hasta
    min_child_size (modo grow_full para la poda de Breiman 1984 §3).

    Regresa el bug latente: int(None) lanzaba TypeError en __init__.
    """
    rng = np.random.default_rng(42)
    n = 500
    x = pd.Series(rng.normal(0, 1, n))
    y = pd.Series((x + rng.normal(0, 0.3, n) > 0).astype(int))
    X = pd.DataFrame({"x": x})
    spec = {"x": PredictorType.CONTINUOUS}
    # contraste: max_depth=4 vs max_depth=None sobre el mismo dataset
    m4 = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"), max_depth=4,
                     min_child_size=5).build(X, y, spec)
    m_full = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                         class_labels=("Event", "Non-event"), max_depth=None,
                         min_child_size=5).build(X, y, spec)
    depth_m4 = max(nd.depth for nd in m4.nodes)
    depth_full = max(nd.depth for nd in m_full.nodes)
    assert depth_m4 == 4                       # pre-pruning respeta el tope
    assert depth_full >= depth_m4              # grow_full no se corta antes
    assert m_full.nodes[-1].node_id == len(m_full.nodes) - 1  # BFS integro


# ---------------------------------------------------------------------------
# Fase 3.1: invariantes multiclase (K=2 y K=3)
# ---------------------------------------------------------------------------


def test_multiclass_binary_pd_values():
    """K=2 with target_class=1 gives exactly the same PD values as the
    pre-3.1 scalar PD."""
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    tb = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"), max_depth=4,
                     min_child_size=2, pd_floor=0.0003)
    m = tb.build(X, y, {"x": _CONT})
    raiz, izq, der = m.nodes
    assert raiz.n_events == (5, 5)
    assert math.isclose(raiz.pd_jeffreys[0], 5.5 / 11.0, rel_tol=1e-12)
    assert math.isclose(raiz.pd_final[0], 0.5, rel_tol=1e-12)
    assert izq.n_events == (0, 5)
    assert math.isclose(izq.pd_jeffreys[0], 0.5 / 6.0, rel_tol=1e-12)
    assert der.n_events == (5, 0)
    assert math.isclose(der.pd_jeffreys[0], 5.5 / 6.0, rel_tol=1e-12)


def test_multiclass_binary_pd_sums_to_one():
    """sum(pd_final) == 1 for every node in a K=2 tree."""
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    m = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                    class_labels=("Event", "Non-event"), max_depth=4,
                    min_child_size=2, pd_floor=0.0003).build(X, y, {"x": _CONT})
    for nd in m.nodes:
        assert abs(sum(nd.pd_final) - 1.0) <= 1e-12
        assert abs(sum(nd.pd_jeffreys) - 1.0) <= 1e-12
        assert len(nd.pd_final) == len(nd.n_events) == len(nd.class_labels) == 2


def test_multiclass_target_class_inverted():
    """target_class=0 inverts the class order: pd_final[0] of the inverted
    tree equals pd_final[1] of the original tree."""
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    m1 = TreeBuilder(_crt(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"), max_depth=4,
                     min_child_size=2, pd_floor=0.0003).build(X, y, {"x": _CONT})
    m2 = TreeBuilder(_crt(), target_type=_BIN, target_class=0,
                     class_labels=("Non-event", "Event"), max_depth=4,
                     min_child_size=2, pd_floor=0.0003).build(X, y, {"x": _CONT})
    assert m1.params_fingerprint != m2.params_fingerprint
    assert math.isclose(m1.nodes[0].pd_final[0], m2.nodes[0].pd_final[1],
                        rel_tol=1e-12)
    assert math.isclose(m1.nodes[0].pd_final[1], m2.nodes[0].pd_final[0],
                        rel_tol=1e-12)
    # symmetric fixture: counts coincide; the inverted-PD asserts are the key
    assert m1.nodes[0].n_events == (5, 5)
    assert m2.nodes[0].n_events == (5, 5)


def test_multiclass_k3_builds():
    """K=3 target with CHAID builds a tree; every node has a 3-component PD
    vector summing to 1."""
    x = pd.Series(["a"] * 40 + ["b"] * 40 + ["c"] * 40)
    y = pd.Series([0] * 40 + [1] * 40 + [2] * 40)
    X = pd.DataFrame({"nivel": x})
    m = TreeBuilder(_quiet_engine(ChaidEngine), target_type=_BIN,
                    target_class=0, class_labels=("Low", "Mid", "High"),
                    max_depth=3, min_child_size=10).build(
        X, y, {"nivel": _NOM})
    assert m.method == "CHAID"
    assert len(m.class_labels) == 3
    assert m.target_class == 0
    assert m.target_class_index == 0
    for nd in m.nodes:
        assert len(nd.pd_final) == 3
        assert abs(sum(nd.pd_final) - 1.0) <= 1e-12
    assert m.nodes[0].n_events == (40, 40, 40)


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
