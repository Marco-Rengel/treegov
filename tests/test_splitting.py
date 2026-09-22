"""Tests de backend_v3/splitting.py (Fase 1). Dual: pytest o python directo."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.splitting import stratified_split  # noqa: E402


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


def test_cobertura_y_proporciones_exactas():
    # 80 ceros, 20 unos, frac 0.7 -> 56/14 exacto (cuotas enteras)
    y = pd.Series([0] * 80 + [1] * 20)
    tr, te = stratified_split(y, 0.7, 42)
    n_total = len(y)
    assert len(tr) == 70 and len(te) == 30
    assert len(set(tr) & set(te)) == 0
    assert sorted([*tr, *te]) == list(range(n_total))
    ytr = y.iloc[tr]
    assert int((ytr == 0).sum()) == 56 and int((ytr == 1).sum()) == 14


def test_largest_remainder():
    # 4 ceros, 3 unos, frac 0.5: cuotas (2.0, 1.5); floors (2, 1); objetivo
    # round(3.5)=4 -> resto R=1 -> mayor fraccion residual es clase 1 (0.5):
    # train = 2 ceros + 2 unos.
    y = pd.Series([0, 0, 0, 0, 1, 1, 1])
    tr, te = stratified_split(y, 0.5, 7)
    assert len(tr) == 4 and len(te) == 3
    ytr = y.iloc[tr]
    assert int((ytr == 1).sum()) == 2  # clase 1 recibio el +1 del resto


def test_determinismo_por_seed():
    y = pd.Series([0] * 50 + [1] * 50)
    a = stratified_split(y, 0.7, 123)
    b = stratified_split(y, 0.7, 123)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
    c = stratified_split(y, 0.7, 124)
    assert not np.array_equal(c[0], a[0])


def test_guards():
    y = pd.Series([0, 1, 0, 1])
    _assert_raises(ValueError, stratified_split, y, 0.0, 1)
    _assert_raises(ValueError, stratified_split, y, 1.0, 1)
    _assert_raises(ValueError, stratified_split, y, 1.2, 1)
    _assert_raises(ValueError, stratified_split, y, "0.5", 1)
    _assert_raises(ValueError, stratified_split, pd.Series([], dtype=float), 0.5, 1)


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
