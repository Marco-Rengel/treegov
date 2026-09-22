"""Tests de backend_v3/profiling.py (Fase 1). Dual: pytest o python directo."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.profiling import MAX_ORDINAL_CATS, infer_spec  # noqa: E402
from backend_v3.types import PredictorType  # noqa: E402


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


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "texto": ["a", "b", "a", "c"] * 30,                 # nominal
        "enteros_pocos": [1, 2, 3, 4, 5] * 24,               # 5 distintos -> ORDINAL
        "enteros_muchos": list(range(50)) + list(range(70)),  # 50 distintos -> CONTINUOUS
        "flotante": [0.1 * i for i in range(120)],           # 120 distintos -> CONTINUOUS
        "default": [0, 1] * 60,                              # target (excluido)
    })


def test_inferencia_tipos():
    spec = infer_spec(_frame(), "default")
    assert spec["texto"] == PredictorType.NOMINAL
    assert spec["enteros_pocos"] == PredictorType.ORDINAL
    assert spec["enteros_muchos"] == PredictorType.CONTINUOUS
    assert spec["flotante"] == PredictorType.CONTINUOUS
    assert "default" not in spec
    assert len(spec) == 4


def test_frontera_exacta_umbral():
    # MAX_ORDINAL_CATS = 20: 20 -> ORDINAL, 21 -> CONTINUOUS
    # (longitudes comunes: 20*21 = 21*20 = 420)
    assert MAX_ORDINAL_CATS == 20
    df = pd.DataFrame({
        "veinte": list(range(20)) * 21,
        "veintiuno": list(range(21)) * 20,
        "default": [0, 1] * 210,
    })
    spec = infer_spec(df, "default")
    assert spec["veinte"] == PredictorType.ORDINAL
    assert spec["veintiuno"] == PredictorType.CONTINUOUS


def test_guards():
    df = _frame()
    _assert_raises(ValueError, infer_spec, df, "default_zzz")
    _assert_raises(
        ValueError, infer_spec, pd.DataFrame({"default": [0, 1]}), "default"
    )  # solo target: sin predictores


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
