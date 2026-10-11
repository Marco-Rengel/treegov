"""Tests de backend_v3/stability.py (Fase 1.3). Dual: pytest o python directo.

Valores verificados a mano:
  - PSI identidad -> 0.
  - PSI cambio moderado: (-0.1)*ln(5/6) + 0.1*ln(2) = 0.0182322 + 0.0693147
    = 0.0875469 -> STABLE.
  - PSI inestable: 0.4*ln(9/5) + 0.4*ln(5) = 0.2351147 + 0.6437751
    = 0.8788898 -> UNSTABLE.
  - PSI bin vacio (clip eps=1e-4): (1e-4 - 1) * ln(1e-4) = 0.9999 * 9.2103404
    = 9.20972.
  - Gini alertas: 0.5 CRITICAL, 0.25 WARNING, 0.1 NONE, None UNDETERMINED.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.stability import (  # noqa: E402
    CSIReport,
    PSIReport,
    StabilityMonitor,
    gini_drop_alert,
    psi_index,
    traffic_light,
)
from backend_v3.crt_engine import CrtEngine  # noqa: E402
from backend_v3.tree_builder import TreeBuilder  # noqa: E402
from backend_v3.types import PredictorType, TargetType  # noqa: E402
from backend_v3.validation import predict_leaf_assignment  # noqa: E402

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


# ---------------------------------------------------------------------------
# psi_index
# ---------------------------------------------------------------------------


def test_psi_identidad_cero():
    psi, contrib = psi_index(
        np.array([0.6, 0.3, 0.1]), np.array([0.6, 0.3, 0.1])
    )
    assert psi == 0.0
    assert np.all(contrib == 0.0)
    assert traffic_light(psi) == "STABLE"


def test_psi_manual_moderado():
    psi, _ = psi_index(np.array([0.6, 0.3, 0.1]), np.array([0.5, 0.3, 0.2]))
    esperado = -0.1 * math.log(5.0 / 6.0) + 0.1 * math.log(2.0)
    assert math.isclose(psi, esperado, rel_tol=1e-12)
    assert math.isclose(psi, 0.0875469, abs_tol=1e-4)
    assert traffic_light(psi) == "STABLE"


def test_psi_manual_inestable():
    psi, _ = psi_index(np.array([0.9, 0.1]), np.array([0.5, 0.5]))
    esperado = 0.4 * math.log(9.0 / 5.0) + 0.4 * math.log(5.0)
    assert math.isclose(psi, esperado, rel_tol=1e-12)
    assert math.isclose(psi, 0.8788898, abs_tol=1e-4)
    assert traffic_light(psi) == "UNSTABLE"


def test_psi_bin_vacio_clip():
    # OOT no visita una celda existente en train -> clip eps (NO renormalizar)
    psi, _ = psi_index(np.array([1.0]), np.array([0.0]))
    esperado = (1e-4 - 1.0) * math.log(1e-4)
    assert math.isclose(psi, esperado, rel_tol=1e-9)
    assert math.isclose(psi, 9.20972, abs_tol=1e-3)
    assert traffic_light(psi) == "UNSTABLE"


def test_semaforos_exactos():
    assert traffic_light(0.099999) == "STABLE"
    assert traffic_light(0.10) == "MODERATE"
    assert traffic_light(0.25) == "UNSTABLE"
    assert traffic_light(float("nan")) == "UNDETERMINED"
    _assert_raises(ValueError, psi_index, np.array([0.5, 0.5]), np.array([1.0]))


# ---------------------------------------------------------------------------
# gini_drop_alert
# ---------------------------------------------------------------------------


def test_gini_drop_alert_manual():
    assert gini_drop_alert(0.5) == "CRITICAL"
    assert gini_drop_alert(0.4000001) == "CRITICAL"
    assert gini_drop_alert(0.40) == "WARNING"
    assert gini_drop_alert(0.25) == "WARNING"
    assert gini_drop_alert(0.20) == "NONE"
    assert gini_drop_alert(0.19) == "NONE"
    # FIX 2: indefinido (None o NaN) no es "sin alerta": es UNDETERMINED
    assert gini_drop_alert(None) == "UNDETERMINED"
    assert gini_drop_alert(float("nan")) == "UNDETERMINED"


# ---------------------------------------------------------------------------
# StabilityMonitor: leaf PSI y CSI
# ---------------------------------------------------------------------------


def _modelo_hojas():
    """Modelo con 2 hojas de 42 filas cada una (fixture CSV mini)."""
    n = 84
    edad = np.concatenate([np.arange(20, 40), np.arange(40, 60),
                           np.arange(20, 40), np.arange(40, 60),
                           np.arange(20, 40), np.arange(40, 60)])[:126]
    y = (edad >= 40).astype(int)
    X = pd.DataFrame({"edad": edad})
    tb = TreeBuilder(CrtEngine(), target_type=_BIN, target_class=1,
                     class_labels=("Event", "Non-event"),
                     max_depth=4, min_child_size=5)
    return tb.build(X, pd.Series(y), {"edad": _CONT})


def test_leaf_psi_estable():
    m = _modelo_hojas()
    hojas = [nd for nd in m.nodes if nd.is_leaf]
    assert len(hojas) == 2
    # asignacion train: a cada fila su hoja; ese dataset se separa perfecto
    mon = StabilityMonitor()
    # construir X_train coherente con el modelo (el original)
    n = 126
    edad = np.concatenate([np.arange(20, 40), np.arange(40, 60),
                           np.arange(20, 40), np.arange(40, 60),
                           np.arange(20, 40), np.arange(40, 60)])[:n]
    X_train = pd.DataFrame({"edad": edad})
    asign_tr = predict_leaf_assignment(m, X_train)
    counts = np.array(
        [float((asign_tr == nd.node_id).sum()) for nd in hojas], dtype=float
    )
    rep = mon.leaf_psi(m, counts, asign_tr)  # misma cohorte -> PSI = 0
    assert rep.psi == 0.0 and rep.flag == "STABLE"
    assert len(rep.per_bin) == 2


def test_csi_categoria_nueva():
    mon = StabilityMonitor()
    X_tr = pd.DataFrame({"seg": ["a", "a", "b", "b", "a", "b"]})
    X_ac = pd.DataFrame({"seg": ["a", "b", "c", "c", "c", "c"]})
    rep = mon.covariate_csi(X_tr, X_ac, "seg", PredictorType.NOMINAL)
    assert isinstance(rep, CSIReport)
    assert rep.predictor == "seg"
    assert rep.csi > 0.0
    etiquetas = [e for (e, _, _, _) in rep.per_bin]
    assert "<OTHER>" in etiquetas


def test_csi_continuo_estable():
    mon = StabilityMonitor()
    rng = np.random.default_rng(7)
    x = pd.Series(rng.normal(0, 1, 10000))
    X_tr = pd.DataFrame({"x": x})
    rep = mon.covariate_csi(X_tr, X_tr, "x", PredictorType.CONTINUOUS)
    assert rep.csi == 0.0 and rep.flag == "STABLE"
    # son 10 deciles del train
    assert len(rep.per_bin) == 10


# ---------------------------------------------------------------------------
# Fase 3.0.g: parámetro renormalize (psi_index / StabilityMonitor)
# ---------------------------------------------------------------------------


def test_psi_index_renormalize_changes_with_empty_bin():
    """renormalize=True cambia el resultado del PSI cuando hay bins vacíos:
    la renormalización tras el clip altera los pesos relativos."""
    expected = np.array([0.9, 0.1, 0.0])
    actual = np.array([0.7, 0.3, 0.0])
    # Clip eps=1e-4: ambos quedan [x, y, 1e-4] con suma 1.0001. Al
    # renormalizar, ambos se dividen por el mismo factor -> ratios a/e
    # intactos pero diferencias (a - e) escaladas -> PSI distinto.
    psi_sin, _ = psi_index(expected, actual)
    psi_con, _ = psi_index(expected, actual, renormalize=True)
    assert psi_sin != psi_con
    assert psi_sin > 0.0
    assert psi_con > 0.0


def test_psi_index_renormalize_no_op_when_already_normalized():
    """Con distribuciones normalizadas y sin bins vacíos, renormalize=True
    es un no-op."""
    expected = np.array([0.6, 0.4])
    actual = np.array([0.5, 0.5])
    psi_sin, _ = psi_index(expected, actual)
    psi_con, _ = psi_index(expected, actual, renormalize=True)
    assert math.isclose(psi_sin, psi_con, rel_tol=1e-12)


def test_stability_monitor_renormalize_invalid():
    """renormalize debe ser bool: int y str lanzan ValueError."""
    _assert_raises(ValueError, StabilityMonitor, renormalize="yes")
    _assert_raises(ValueError, StabilityMonitor, renormalize=1)
    assert StabilityMonitor().renormalize is False
    assert StabilityMonitor(renormalize=True).renormalize is True


def test_stability_monitor_agnostic_to_k():
    """Fase 3.1.d: StabilityMonitor NO bloquea K>2.

    El diseño §5.3 del 3.1_design_multiclass.md establece que PSI y
    CSI son target-agnostic; el bloqueo multiclase vive en
    Session.evaluate_oot (por el Gini Drop, que sí es binario).
    Este test documenta explícitamente esa distinción: el monitor
    de estabilidad procesa un modelo con K=3 sin problemas.

    Nota: el bloqueo no se prueba aquí (ya está en
    tests/test_session_state.py::test_evaluate_oot_multiclass_raises).
    Aquí solo verificamos que la capa inferior es agnóstica.
    """
    # Fixture K=3: 3 hojas puras, cada una 30 filas de su clase.
    # Predictor categórico para no depender de bins continuos.
    seg = np.tile(["a", "b", "c"], 30)
    y = np.tile([0, 1, 2], 30)
    X = pd.DataFrame({"seg": seg})
    from backend_v3.chaid_engine import ChaidEngine
    m = TreeBuilder(ChaidEngine(), target_type=_BIN, target_class=2,
                    class_labels=("Bajo", "Alto", "Medio"),
                    max_depth=3, min_child_size=5).build(
        X, pd.Series(y), {"seg": PredictorType.NOMINAL})
    # leaf_psi: misma cohorte como train y como actual -> PSI = 0.
    asign = predict_leaf_assignment(m, X)
    hojas = [nd for nd in m.nodes if nd.is_leaf]
    counts = np.array(
        [float((asign == nd.node_id).sum()) for nd in hojas], dtype=float
    )
    mon = StabilityMonitor()
    rep = mon.leaf_psi(m, counts, asign)
    assert rep.psi == 0.0 and rep.flag == "STABLE"


# ---------------------------------------------------------------------------
# 3.2.h - Ponderación por muestra
# ---------------------------------------------------------------------------


def _fixture_hojas_y_oot():
    """Modelo de 2 hojas + cohortes train/OOT enrutables."""
    m = _modelo_hojas()
    n = 126
    edad = np.concatenate([np.arange(20, 40), np.arange(40, 60),
                           np.arange(20, 40), np.arange(40, 60),
                           np.arange(20, 40), np.arange(40, 60)])[:n]
    X_train = pd.DataFrame({"edad": edad})
    asign_tr = predict_leaf_assignment(m, X_train)
    # OOT desplazada (PSI > 0) pero totalmente enrutable
    X_oot = pd.DataFrame({"edad": np.arange(25, 75)})
    asign_oot = predict_leaf_assignment(m, X_oot)
    return m, X_train, X_oot, asign_tr, asign_oot


def test_weighted_stability_parity_uniform_weights():
    """Pesos uniformes (todos 1): resultados idénticos al caso sin pesos."""
    m, X_train, X_oot, asign_tr, asign_oot = _fixture_hojas_y_oot()
    spec = {"edad": _CONT}
    mon = StabilityMonitor()
    psi_0, csi_0 = mon.report(m, X_train, X_oot, asign_tr, asign_oot, spec)
    psi_1, csi_1 = mon.report(
        m, X_train, X_oot, asign_tr, asign_oot, spec,
        weights_train=np.ones(len(X_train)),
        weights_actual=np.ones(len(X_oot)),
    )
    assert psi_1.psi == psi_0.psi
    assert psi_1.flag == psi_0.flag
    assert psi_1.per_bin == psi_0.per_bin
    assert len(csi_1) == len(csi_0) == 1
    assert csi_1[0].csi == csi_0[0].csi
    assert csi_1[0].flag == csi_0[0].flag
    assert csi_1[0].per_bin == csi_0[0].per_bin


def test_weighted_stability_psi_uses_weights():
    """El PSI ponderado difiere del no ponderado y coincide con el manual."""
    m, X_train, X_oot, asign_tr, asign_oot = _fixture_hojas_y_oot()
    hojas = [nd for nd in m.nodes if nd.is_leaf]
    counts = np.array(
        [float((asign_tr == nd.node_id).sum()) for nd in hojas], dtype=float
    )
    # Pesos crecientes con la edad OOT -> sesgan la distribución de hojas
    w_oot = np.linspace(1.0, 3.0, len(X_oot))
    mon = StabilityMonitor()
    rep_w = mon.leaf_psi(m, counts, asign_oot, weights_oot=w_oot)
    rep_0 = mon.leaf_psi(m, counts, asign_oot)
    assert not math.isclose(rep_w.psi, rep_0.psi, rel_tol=1e-12)
    # Cálculo manual: p_act = masa ponderada por hoja / masa total
    p_exp = counts / counts.sum()
    p_act = np.array(
        [w_oot[asign_oot == nd.node_id].sum() for nd in hojas]
    ) / w_oot.sum()
    psi_manual, _ = psi_index(p_exp, p_act)
    assert math.isclose(rep_w.psi, psi_manual, rel_tol=1e-12)


def test_weighted_stability_csi_uses_weights():
    """CSI continuo ponderado: difiere del no ponderado y es el manual."""
    mon = StabilityMonitor()
    X_tr = pd.DataFrame({"x": np.arange(100, dtype=float)})
    X_ac = pd.DataFrame({"x": np.arange(100, dtype=float)})
    # Pesos concentrados en los valores altos de la cohorte actual
    w_ac = np.where(X_ac["x"].to_numpy() >= 50, 5.0, 1.0)
    rep_w = mon.covariate_csi(X_tr, X_ac, "x", _CONT, weights_actual=w_ac)
    rep_0 = mon.covariate_csi(X_tr, X_ac, "x", _CONT)
    assert not math.isclose(rep_w.csi, rep_0.csi, rel_tol=1e-12)
    # Manual: mismos deciles de train; p_act ponderada
    qs = np.quantile(X_tr["x"].to_numpy(dtype=float), np.linspace(0, 1, 11))
    bordes = np.unique(qs)
    bordes[0] = -np.inf
    bordes[-1] = np.inf
    n_bins = len(bordes) - 1
    bins_tr = np.digitize(X_tr["x"].to_numpy(dtype=float), bordes[1:-1])
    bins_ac = np.digitize(X_ac["x"].to_numpy(dtype=float), bordes[1:-1])
    p_exp = np.array(
        [float((bins_tr == i).sum()) for i in range(n_bins)]
    ) / len(X_tr)
    p_act = np.array(
        [float(w_ac[bins_ac == i].sum()) for i in range(n_bins)]
    ) / w_ac.sum()
    csi_manual, _ = psi_index(p_exp, p_act)
    assert math.isclose(rep_w.csi, csi_manual, rel_tol=1e-12)


def test_weighted_stability_unseen_bin_accumulates_weights():
    """<UNSEEN> acumula la SUMA de pesos de las filas no asignables."""
    m, X_train, _X_oot, asign_tr, _asign_oot = _fixture_hojas_y_oot()
    hojas = [nd for nd in m.nodes if nd.is_leaf]
    counts = np.array(
        [float((asign_tr == nd.node_id).sum()) for nd in hojas], dtype=float
    )
    # OOT: 10 filas, 3 de ellas no asignables (-1)
    asign_oot = np.array(
        [hojas[0].node_id] * 4 + [hojas[1].node_id] * 3 + [-1] * 3
    )
    w_oot = np.arange(1.0, 11.0)  # 1..10: cada fila con peso distinto
    mon = StabilityMonitor()
    rep = mon.leaf_psi(m, counts, asign_oot, weights_oot=w_oot)
    etiquetas = [e for (e, _, _, _) in rep.per_bin]
    assert "<UNSEEN>" in etiquetas
    i_unseen = etiquetas.index("<UNSEEN>")
    p_act_unseen = rep.per_bin[i_unseen][2]
    esperado = float(w_oot[asign_oot < 0].sum()) / float(w_oot.sum())
    assert math.isclose(p_act_unseen, esperado, rel_tol=1e-12)
    # No es el conteo (3/10): es la masa (8+9+10)/55
    assert not math.isclose(p_act_unseen, 0.3, rel_tol=1e-12)


def test_weighted_stability_other_bin_accumulates_weights():
    """<OTHER> acumula la SUMA de pesos de las filas con categoría nueva."""
    mon = StabilityMonitor()
    X_tr = pd.DataFrame({"seg": ["a", "a", "b", "b", "a", "b"]})
    X_ac = pd.DataFrame({"seg": ["a", "b", "c", "c", "c", "c"]})
    w_ac = np.array([1.0, 1.0, 2.0, 4.0, 8.0, 16.0])
    rep = mon.covariate_csi(
        X_tr, X_ac, "seg", PredictorType.NOMINAL, weights_actual=w_ac
    )
    etiquetas = [e for (e, _, _, _) in rep.per_bin]
    assert "<OTHER>" in etiquetas
    i_other = etiquetas.index("<OTHER>")
    p_act_other = rep.per_bin[i_other][2]
    esperado = float(w_ac[2:].sum()) / float(w_ac.sum())  # 30/32
    assert math.isclose(p_act_other, esperado, rel_tol=1e-12)
    # No es el conteo (4/6)
    assert not math.isclose(p_act_other, 4.0 / 6.0, rel_tol=1e-12)


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
