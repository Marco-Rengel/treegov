"""Tests de backend_v3/imputation.py (Fase 0, Paso 8).

Nucleo: garantia anti-leakage — los valores imputados provienen SOLO de
train, aunque test tenga distribuciones radicalmente distintas.

Ejecutable de DOS formas (pytest NO es dependencia del proyecto):

    .venv\\Scripts\\python -m pytest tests/test_imputation.py -v
    .venv\\Scripts\\python tests\\test_imputation.py
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.imputation import ImputationSpec, TrainOnlyImputer  # noqa: E402
from backend_v3.types import PredictorType  # noqa: E402

_CONT = PredictorType.CONTINUOUS
_ORD = PredictorType.ORDINAL
_NOM = PredictorType.NOMINAL


def _assert_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:  # pragma: no cover
        raise AssertionError(
            f"{fn.__name__} lanzo {type(e).__name__} en vez de {exc_type.__name__}: {e}"
        ) from e
    raise AssertionError(f"{fn.__name__} no lanzo {exc_type.__name__}")


def test_no_leakage_train_only():
    # train: cont media = 2.0 ; nom moda = "a"
    X_train = pd.DataFrame({
        "ingreso": pd.Series([1.0, 2.0, 3.0, np.nan]),
        "sector": pd.Series(["a", "a", "b", None]),
    })
    spec = {"ingreso": _CONT, "sector": _NOM}
    imp = TrainOnlyImputer(logger=logging.getLogger("treegov.imputation.t1"))
    sp = imp.fit(X_train, spec)
    assert isinstance(sp, ImputationSpec)
    assert sp.means == {"ingreso": 2.0}
    assert sp.modes == {"sector": "a"}
    assert sp.fitted_n == 4

    # test con distribucion RADICALMENTE distinta: si hubiera fuga, los
    # NaN se rellenarian con 100.0 / "b" (estadisticos de test).
    X_test = pd.DataFrame({
        "ingreso": pd.Series([100.0, np.nan, 50.0]),
        "sector": pd.Series(["b", "b", None]),
    })
    out = imp.transform(X_test)
    assert out["ingreso"].tolist() == [100.0, 2.0, 50.0]   # NaN -> 2.0 (train)
    assert out["sector"].tolist() == ["b", "b", "a"]       # NaN -> "a" (train)


def test_transform_no_modifica_entrada():
    X = pd.DataFrame({"v": pd.Series([1.0, np.nan])})
    imp = TrainOnlyImputer(logger=logging.getLogger("treegov.imputation.t2"))
    imp.fit(pd.DataFrame({"v": pd.Series([3.0, 5.0])}), {"v": _CONT})
    out = imp.transform(X)
    assert np.isnan(X["v"].iloc[1])       # original intacto (copia)
    assert out["v"].iloc[1] == 4.0        # imputado con la media de train (4.0)


def test_moda_empates_determinista():
    imp = TrainOnlyImputer(logger=logging.getLogger("treegov.imputation.t3"))
    # empate de frecuencias: etiquetas ordenables -> la menor
    sp = imp.fit(
        pd.DataFrame({"c": pd.Series(["b", "a", "b", "a"])}), {"c": _NOM}
    )
    assert sp.modes["c"] == "a"
    # etiquetas no comparables entre si -> primera por orden de aparicion
    imp2 = TrainOnlyImputer(logger=logging.getLogger("treegov.imputation.t3b"))
    sp2 = imp2.fit(
        pd.DataFrame({"c": pd.Series([1, "z", 1, "z"])}), {"c": _NOM}
    )
    assert sp2.modes["c"] == 1


def test_guards():
    imp = TrainOnlyImputer(logger=logging.getLogger("treegov.imputation.t4"))
    # transform antes de fit -> RuntimeError
    _assert_raises(RuntimeError, imp.transform, pd.DataFrame({"a": [1.0]}))
    # columna ausente en train
    _assert_raises(
        ValueError, imp.fit,
        pd.DataFrame({"a": [1.0, 2.0]}), {"b": _CONT},
    )
    # columna 100% NaN en train -> no hay con que imputar
    _assert_raises(
        ValueError, imp.fit,
        pd.DataFrame({"a": pd.Series([np.nan, np.nan])}), {"a": _CONT},
    )
    # ajuste correcto y transform con columna faltante
    imp.fit(pd.DataFrame({"a": [1.0, 2.0]}), {"a": _CONT})
    _assert_raises(ValueError, imp.transform, pd.DataFrame({"zzz": [1.0]}))


def test_ordinal_simbolico_usa_moda_y_numerico_media():
    imp = TrainOnlyImputer(logger=logging.getLogger("treegov.imputation.t5"))
    X = pd.DataFrame({
        "grado": pd.Series(["alto", "bajo", "bajo", None]),      # ordinal simb
        "nivel": pd.Series([1.0, 2.0, 3.0, np.nan]),             # ordinal num
    })
    sp = imp.fit(X, {"grado": _ORD, "nivel": _ORD})
    assert sp.modes == {"grado": "bajo"}
    assert sp.means == {"nivel": 2.0}
    out = imp.transform(X)
    assert out["grado"].tolist() == ["alto", "bajo", "bajo", "bajo"]
    assert out["nivel"].tolist() == [1.0, 2.0, 3.0, 2.0]


# ---------------------------------------------------------------------------
# ejecucion directa sin pytest
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        obj
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
