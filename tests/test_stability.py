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
    tb = TreeBuilder(CrtEngine(), target_type=_BIN, max_depth=4, min_child_size=5)
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


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
