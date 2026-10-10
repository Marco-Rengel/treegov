"""Tests de backend_v3/splitting.py (Fase 1). Dual: pytest o python directo."""

import math
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


# ---------------------------------------------------------------------------
# 3.2.f - Ponderacion por muestra
# ---------------------------------------------------------------------------


def test_weighted_splitting_parity_uniform():
    # Pesos uniformes == sin pesos (mismo split, fila a fila).
    y = pd.Series([0] * 60 + [1] * 40)
    tr0, te0 = stratified_split(y, 0.7, 42)
    tr1, te1 = stratified_split(y, 0.7, 42, weights=np.ones(100))
    assert np.array_equal(tr0, tr1)
    assert np.array_equal(te0, te1)


def test_weighted_splitting_split_unchanged_by_weights():
    """La estratificacion es por conteo de filas; los pesos no cambian
    el split (los pesos viajan con cada fila y afectan al modelo, no a
    la particion). Con pesos no triviales, idx_train/idx_test son
    identicos a los del modo sin pesos con el mismo seed."""
    y = pd.Series([0] * 60 + [1] * 40)
    w = np.array([1.0] * 60 + [2.0] * 40)
    tr0, te0 = stratified_split(y, 0.4, 42)
    tr1, te1 = stratified_split(y, 0.4, 42, weights=w)
    assert np.array_equal(tr0, tr1)
    assert np.array_equal(te0, te1)
    # Proporcion de filas por clase en train: identica en ambos modos.
    for clase in (0, 1):
        p0 = (y.iloc[tr0] == clase).sum() / len(tr0)
        p1 = (y.iloc[tr1] == clase).sum() / len(tr1)
        assert math.isclose(p0, p1, rel_tol=1e-9)


def test_weighted_splitting_rejects_wrong_length():
    y = pd.Series([0] * 50 + [1] * 50)
    _assert_raises(ValueError, stratified_split, y, 0.7, 42,
                   weights=np.ones(99))


def test_weighted_splitting_rejects_nonpositive():
    y = pd.Series([0] * 50 + [1] * 50)
    w_cero = np.ones(100); w_cero[10] = 0.0
    w_neg = np.ones(100); w_neg[10] = -1.0
    _assert_raises(ValueError, stratified_split, y, 0.7, 42, weights=w_cero)
    _assert_raises(ValueError, stratified_split, y, 0.7, 42, weights=w_neg)


def test_weighted_splitting_rejects_non_finite():
    y = pd.Series([0] * 50 + [1] * 50)
    w_nan = np.ones(100); w_nan[10] = np.nan
    w_inf = np.ones(100); w_inf[10] = np.inf
    _assert_raises(ValueError, stratified_split, y, 0.7, 42, weights=w_nan)
    _assert_raises(ValueError, stratified_split, y, 0.7, 42, weights=w_inf)


def test_weighted_splitting_check_b2_with_weights():
    # Clase 1 con 3 filas; pesos extremos hacia abajo en clase 0 (0.1).
    # W0=5.0, W1=3.0, W=8.0, frac=0.7: Q0=3.5 (f=3), Q1=2.1 (f=2),
    # obj=round(5.6)=6, floors 3+2=5 -> R=1 -> mayor fraccion residual es
    # clase 0 (0.5) -> clase 0 recibe +1. Train: 4 clase 0 + 2 clase 1.
    # Test: 46 clase 0 + 1 clase 1 -> B2 falla en la clase 1.
    y = pd.Series([0] * 50 + [1] * 3)
    w = np.array([0.1] * 50 + [1.0] * 3)
    try:
        stratified_split(y, 0.7, 42, weights=w)
    except ValueError as e:
        assert "1" in str(e)  # menciona la clase infractora
        return
    raise AssertionError("stratified_split no lanzo ValueError (B2)")


def test_weighted_splitting_check_b2_not_applied_without_weights():
    # Invariante C1: mismo fixture (clase 1 con 3 filas) SIN pesos no
    # lanza B2 aunque test quede con 1 sola fila de la clase 1.
    y = pd.Series([0] * 50 + [1] * 3)
    tr, te = stratified_split(y, 0.7, 42)  # sin weights: no debe lanzar
    yte = y.iloc[te]
    assert int((yte == 1).sum()) == 1  # confirma que el fixture es el mismo


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
