"""Tests de backend_v3/crt_engine.py (Fase 0, Paso 7).

Valores de referencia verificados a mano (aprobados en la auditoria del
diseno): dI=0.5 (umbral binario), dI=1.0 (varianza), dI=49/225
(exhaustivo K=3), dI=0.15 (heuristica K>10 con empate m=5/m=6),
agreement=1.0 y n_used 6/7 (surrogates con NaN), dI=64/225
(ordinal simbolico).

Ejecutable de DOS formas (pytest NO es dependencia del proyecto):

    .venv\\Scripts\\python -m pytest tests/test_crt_engine.py -v
    .venv\\Scripts\\python tests\\test_crt_engine.py
"""

import logging
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.crt_engine import CrtEngine  # noqa: E402
from backend_v3.types import PredictorType, SplitConfig, TargetType  # noqa: E402

_NOMINAL = PredictorType.NOMINAL
_ORDINAL = PredictorType.ORDINAL
_CONTINUOUS = PredictorType.CONTINUOUS
_BINARY = TargetType.BINARY
_CATEGORICAL = TargetType.CATEGORICAL
_T_CONT = TargetType.CONTINUOUS


def _engine(**kwargs) -> CrtEngine:
    quiet = logging.getLogger("treegov.crt.tests")
    if not quiet.handlers:
        quiet.addHandler(logging.NullHandler())
    quiet.propagate = False
    return CrtEngine(logger=quiet, **kwargs)


def _assert_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:  # pragma: no cover - diagnostico
        raise AssertionError(
            f"{fn.__name__} lanzo {type(e).__name__} en vez de {exc_type.__name__}: {e}"
        ) from e
    raise AssertionError(f"{fn.__name__} no lanzo {exc_type.__name__}")


# ---------------------------------------------------------------------------
# 1. Umbral continuo binario: valores exactos verificados a mano
# ---------------------------------------------------------------------------


def test_umbral_continuo_binario_manual():
    # x=[1,2,3,4], y=[0,0,1,1]
    # I_padre = 1 - 2*(0.5^2) = 0.5
    # t=1.5 -> dI = 1/6 ; t=2.5 -> dI = 1/2 (max) ; t=3.5 -> dI = 1/6
    cfg = _engine().evaluate(
        pd.Series([1.0, 2.0, 3.0, 4.0]), pd.Series([0, 0, 1, 1]),
        predictor="x", predictor_type=_CONTINUOUS, target_type=_BINARY,
    )
    assert cfg is not None
    assert cfg.threshold == 2.5
    assert cfg.branches is None
    assert cfg.statistic == 0.5
    assert cfg.impurity_gain == 0.5
    assert cfg.statistic_name == "gini_gain"
    assert cfg.df == ()
    assert cfg.child_ns == (2, 2)
    assert cfg.parent_n == 4
    assert cfg.p_value is None and cfg.p_value_adjusted is None
    assert cfg.bonferroni_multiplier is None and cfg.n_merges is None
    assert cfg.method == "CRT"


def test_umbral_continuo_varianza_manual():
    # x=[1,2,3,4], y=[1,1,3,3]
    # I_padre = E[y^2]-E[y]^2 = 5 - 4 = 1
    # t=2.5 -> ambos lados constantes -> dI = 1.0
    cfg = _engine().evaluate(
        pd.Series([1.0, 2.0, 3.0, 4.0]),
        pd.Series([1.0, 1.0, 3.0, 3.0]),
        predictor="x", predictor_type=_CONTINUOUS, target_type=_T_CONT,
    )
    assert cfg is not None
    assert cfg.threshold == 2.5
    assert cfg.statistic_name == "variance_gain"
    assert math.isclose(cfg.statistic, 1.0, rel_tol=1e-12)
    assert cfg.impurity_gain == cfg.statistic


# ---------------------------------------------------------------------------
# 2. Nominal exhaustivo K=3
# ---------------------------------------------------------------------------


def test_nominal_exhaustivo_k3():
    # a=[2 ceros, 8 unos]; b igual; c=[9 ceros, 1 uno]
    # particiones: {a}|{bc} dI=0.0544, {b}|{ac} dI=0.0544,
    #              {ab}|{c} dI = 442/900 - 192/900 - 54/900 = 196/900 = 49/225
    x = pd.Series(["a"] * 10 + ["b"] * 10 + ["c"] * 10)
    y = pd.Series(
        [0] * 2 + [1] * 8 + [0] * 2 + [1] * 8 + [0] * 9 + [1] * 1
    )
    cfg = _engine().evaluate(
        x, y, predictor="x3", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg is not None
    assert cfg.threshold is None
    assert cfg.branches == (("a", "b"), ("c",))
    assert cfg.child_ns == (20, 10)
    assert cfg.parent_n == 30
    esperado = 49.0 / 225.0  # 0.217777...
    assert math.isclose(cfg.statistic, esperado, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# 3. Nominal heuristico K > 10: orden por tasa + adyacentes
# ---------------------------------------------------------------------------


def test_nominal_heuristico_k11():
    # tasas por categoria (n=100 c/u), orden natural != orden de tasa:
    tasas = {"a": 0.0, "b": 1.0, "c": 0.1, "d": 0.9, "e": 0.2, "f": 0.8,
             "g": 0.3, "h": 0.7, "i": 0.4, "j": 0.6, "k": 0.5}
    xs, ys = [], []
    for cat, tasa in tasas.items():
        n1 = int(round(100 * tasa))
        xs += [cat] * 100
        ys += [1] * n1 + [0] * (100 - n1)
    x = pd.Series(xs)
    y = pd.Series(ys)
    cfg = _engine().evaluate(
        x, y, predictor="xk", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg is not None
    # dI maximo exacto = 0.15 (empate teorico m=5/m=6; argmax -> primero)
    assert math.isclose(cfg.statistic, 0.15, rel_tol=1e-9)
    # convencion: derecha = tramo de tasas ALTAS (analogo a x > t en continuo)
    izq = set(cfg.branches[0])
    der = set(cfg.branches[1])
    assert izq | der == set(tasas)
    assert len(izq & der) == 0
    assert der in ({"b", "d", "f", "h", "j"}, {"b", "d", "f", "h", "j", "k"})
    assert "a" in izq and "c" in izq  # las tasas mas bajas a la izquierda
    assert cfg.child_ns[0] + cfg.child_ns[1] == 1100


def test_heuristica_multiclase_warning():
    # K_cat=11 > 10 y K_cls=3 -> WARNING regulatorio obligatorio
    xs, ys = [], []
    for i in range(11):
        n_dom = 20
        for k in range(3):
            n_k = n_dom if k == (i % 3) else 5
            xs += [f"g{i:02d}"] * n_k
            ys += [k] * n_k
    captura = _ListHandler()
    log = logging.getLogger("treegov.crt.heur")
    log.handlers = [captura]
    log.propagate = False
    log.setLevel(logging.DEBUG)
    eng = CrtEngine(logger=log)
    cfg = eng.evaluate(
        pd.Series(xs), pd.Series(ys),
        predictor="xm", predictor_type=_NOMINAL, target_type=_CATEGORICAL,
    )
    mensajes = "\n".join(captura.mensajes)
    assert "se pierde optimalidad en multiclase" in mensajes
    assert cfg is not None
    assert len(cfg.branches) == 2
    flat = [v for g in cfg.branches for v in g]
    assert len(set(flat)) == 11


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.mensajes: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.mensajes.append(record.getMessage())


# ---------------------------------------------------------------------------
# 4. Ordinal simbolico -> branches (no threshold)
# ---------------------------------------------------------------------------


def test_ordinal_simbolico_branches():
    # tasas: 1_bajo 0/5, 2_medio 3/5, 3_alto 5/5; orden alfabetico = semantico
    x = pd.Series(["1_bajo"] * 5 + ["2_medio"] * 5 + ["3_alto"] * 5)
    y = pd.Series([0] * 5 + [0] * 2 + [1] * 3 + [1] * 5)
    cfg = _engine().evaluate(
        x, y, predictor="ord", predictor_type=_ORDINAL, target_type=_BINARY
    )
    assert cfg is not None
    # mejor corte tras "1_bajo": dI = 112/225 - 48/225 = 64/225
    assert cfg.branches == (("1_bajo",), ("2_medio", "3_alto"))
    assert cfg.threshold is None
    assert math.isclose(cfg.statistic, 64.0 / 225.0, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# 5. Surrogates (Breiman 1984, §5.3)
# ---------------------------------------------------------------------------


def test_surrogates_breiman():
    # primario x1 (con NaN en fila 8): corte 4.5 sobre 7 filas, izq = x<=4.5
    x1 = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, np.nan])
    y = pd.Series([0, 0, 0, 0, 1, 1, 1, 1])
    eng = _engine()
    primario = eng.evaluate(
        x1, y, predictor="x1", predictor_type=_CONTINUOUS, target_type=_BINARY
    )
    assert primario is not None and primario.threshold == 4.5
    assert primario.parent_n == 7
    assert math.isclose(primario.statistic, 24.0 / 49.0, rel_tol=1e-12)

    X = pd.DataFrame({
        "x1": x1,
        # replica exacta escalada, con NaN en fila 1 -> n_used = 6
        "x2": pd.Series([np.nan, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0]),
        # anti-replica perfecta -> flipped=True, n_used = 7
        "x3": pd.Series([8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]),
        # sin asociacion: agreement = 4/7 = majority -> descartado
        "x4": pd.Series([1.0, 1.0, 2.0, 2.0, 1.0, 2.0, 1.0, 2.0]),
    })
    spec = {"x1": _CONTINUOUS, "x2": _CONTINUOUS, "x3": _CONTINUOUS,
            "x4": _CONTINUOUS}
    surr = eng.surrogate_splits(
        primario, X, y, spec, target_type=_BINARY
    )
    assert len(surr) == 2

    s2, s3 = surr[0], surr[1]  # ambos agreement=1.0; orden de spec
    assert s2.split.predictor == "x2"
    assert s2.agreement == 1.0
    assert s2.flipped is False
    assert s2.n_used == 6
    assert s2.majority_to_beat == 0.5
    assert s2.split.threshold == 9.0
    assert math.isclose(s2.split.statistic, 24.0 / 49.0, rel_tol=1e-12)

    assert s3.split.predictor == "x3"
    assert s3.agreement == 1.0
    assert s3.flipped is True
    assert s3.n_used == 7
    assert math.isclose(s3.majority_to_beat, 4.0 / 7.0, rel_tol=1e-12)
    assert math.isclose(s3.split.statistic, 0.5, rel_tol=1e-12)

    # coherencia de invariantes en los SplitConfig embebidos
    for s in surr:
        assert s.split.method == "CRT"
        assert s.split.impurity_gain == s.split.statistic
        assert s.split.p_value is None


def test_surrogates_asimetrico_a():
    # Caso A de la auditoria (Bloque 1, FIX 2). NOTA: el enunciado original
    # decia "agreement = 5/6 con primario 4/3", aritmeticamente imposible
    # (n_used = 4+3 = 7 -> same/7 nunca da /6). Forma coherente verificada:
    #
    # primario: x1=[1..7], y=[0,0,0,0,1,1,1] -> thr=4.5; P_L=4, P_R=3.
    # candidato x2=[1,4,5,6,2,3,7] -> left ordenado = [T,F,F,T,T,T,F]
    #   corte tras el valor 3 (thr=3.5, n_izq=3): q=(1,3,2,1) -> same=2, flip=5
    #   corte tras el valor 6 (thr=6.5, n_izq=6): q=(4,0,2,1) -> same=5, flip=2
    #   EMPATE de agreement: 5/7 en ambos -> argmax toma el PRIMERO (b=2):
    #   thr=3.5 con flipped=True (el surrogate izquierdo replica al derecho del
    #   primario). Suma de cuadrantes: 1+3+2+1 = 4+0+2+1 = 7 == n_used.
    x1 = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    y = pd.Series([0, 0, 0, 0, 1, 1, 1])
    x2 = pd.Series([1.0, 4.0, 5.0, 6.0, 2.0, 3.0, 7.0])
    eng = _engine()
    primario = eng.evaluate(
        x1, y, predictor="x1", predictor_type=_CONTINUOUS, target_type=_BINARY
    )
    assert primario is not None and primario.threshold == 4.5
    surr = eng.surrogate_splits(
        primario, pd.DataFrame({"x1": x1, "x2": x2}), y,
        {"x1": _CONTINUOUS, "x2": _CONTINUOUS}, target_type=_BINARY,
    )
    assert len(surr) == 1
    s = surr[0]
    assert s.n_used == 7
    assert math.isclose(s.agreement, 5.0 / 7.0, rel_tol=1e-12)
    assert math.isclose(s.majority_to_beat, 4.0 / 7.0, rel_tol=1e-12)
    assert s.flipped is True
    assert s.split.threshold == 3.5

    # verdad independiente por tabla 2x2 (crosstab primario x candidato)
    lp = (x1 <= primario.threshold).to_numpy()
    lc = (x2 <= s.split.threshold).to_numpy()
    tab = pd.crosstab(pd.Series(lp, name="p"), pd.Series(lc, name="c"))
    tp = int(tab.loc[True, True]); fp = int(tab.loc[False, True])
    fn = int(tab.loc[True, False]); tn = int(tab.loc[False, False])
    assert (tp, fn, fp, tn) == (1, 3, 2, 1)  # q_ll, q_lr, q_rl, q_rr
    assert max(tp + tn, fp + fn) / 7.0 == s.agreement


def test_surrogates_nominal_regla_estricta():
    # Caso B de la auditoria (Bloque 1, FIX 2): nominal cuyo flip real vale
    # exactamente la mayoria -> RECHAZO por regla estricta de Breiman.
    #
    # primario: x1=[1..10], y=[0]x4+[1]x6 -> thr=4.5; P_L=4, P_R=6; maj=0.6
    # candidato "A" en filas {1,2,3,6,7,8}: cuadrantes (1,3,3,3):
    #   same = 1+3 = 4 (0.4); flip = 3+3 = 6 (0.6) == majority -> descartado
    # (el codigo previo al FIX lo aceptaba con agreement=0.8 y flip)
    x1 = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    y = pd.Series([0, 0, 0, 0, 1, 1, 1, 1, 1, 1])
    debil = pd.Series(["A", "A", "A", "B", "B", "A", "A", "A", "B", "B"])
    exacto = pd.Series(["L"] * 4 + ["R"] * 6)  # replica perfecta del primario
    eng = _engine()
    primario = eng.evaluate(
        x1, y, predictor="x1", predictor_type=_CONTINUOUS, target_type=_BINARY
    )
    assert primario is not None and primario.threshold == 4.5
    surr = eng.surrogate_splits(
        primario, pd.DataFrame({"x1": x1, "debil": debil, "exacto": exacto}),
        y, {"x1": _CONTINUOUS, "debil": _NOMINAL, "exacto": _NOMINAL},
        target_type=_BINARY,
    )
    # el debil quedo descartado; solo la replica perfecta sobrevive
    assert len(surr) == 1
    s = surr[0]
    assert s.split.predictor == "exacto"
    assert s.agreement == 1.0
    assert s.flipped is False
    assert s.split.branches == (("L",), ("R",))
    # verdad independiente del rechazado:
    lp = (x1 <= 4.5).to_numpy()
    lc = debil.isin(["B"]).to_numpy()
    tab = pd.crosstab(pd.Series(lp, name="p"), pd.Series(lc, name="c"))
    tp = int(tab.loc[True, True]); fp = int(tab.loc[False, True])
    fn = int(tab.loc[True, False]); tn = int(tab.loc[False, False])
    assert (tp, fn, fp, tn) == (1, 3, 3, 3)
    assert max(tp + tn, fn + fp) / 10.0 == 0.6  # == majority -> descarte OK


def test_surrogates_primario_no_binario_rechazado():
    x1 = pd.Series([1.0, 2.0, 3.0, 4.0])
    y = pd.Series([0, 0, 1, 1])
    eng = _engine()
    primario = eng.evaluate(
        x1, y, predictor="x1", predictor_type=_CONTINUOUS, target_type=_BINARY
    )
    cfg_branches = SplitConfig(  # primario mal formado: 3 ramas
        predictor="x1", method="CHAID", statistic=5.0, statistic_name="chi2",
        df=(2,), parent_n=4, child_ns=(1, 2, 1), p_value=0.05,
        p_value_adjusted=0.1, bonferroni_multiplier=2, n_merges=1,
        branches=(("a",), ("b",), ("c",)),
    )
    _assert_raises(
        ValueError, eng.surrogate_splits,
        cfg_branches, pd.DataFrame({"x1": x1, "z": x1}), y,
        {"x1": _CONTINUOUS, "z": _CONTINUOUS}, target_type=_BINARY,
    )
    assert primario is not None  # primario legitimo sano


# ---------------------------------------------------------------------------
# 6. Coherencia exhaustiva con SplitConfig + determinismo de evaluacion
# ---------------------------------------------------------------------------


def test_coherencia_splitconfig_y_determinismo():
    x = pd.Series([1.0, 2.0, 3.0, 4.0])
    y = pd.Series([0, 0, 1, 1])
    a = _engine().evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS, target_type=_BINARY
    )
    b = _engine().evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS, target_type=_BINARY
    )
    assert a == b  # determinismo total (frozen dataclass con eq)
    assert hash(a) is not None
    assert sum(a.child_ns) == a.parent_n


# ---------------------------------------------------------------------------
# 7. Casos borde
# ---------------------------------------------------------------------------


def test_bordes():
    # x constante -> None
    assert _engine().evaluate(
        pd.Series([5.0] * 8), pd.Series([0, 1] * 4),
        predictor="c", predictor_type=_CONTINUOUS, target_type=_BINARY,
    ) is None
    # y constante -> None
    assert _engine().evaluate(
        pd.Series([1.0, 2.0, 3.0, 4.0]), pd.Series([1, 1, 1, 1]),
        predictor="yc", predictor_type=_CONTINUOUS, target_type=_BINARY,
    ) is None
    # NaN: 2 filas excluidas, resultado identico al limpio
    cfg = _engine().evaluate(
        pd.Series([1.0, 2.0, 3.0, 4.0, np.nan, np.nan]),
        pd.Series([0, 0, 1, 1, 0, 1]),
        predictor="nan", predictor_type=_CONTINUOUS, target_type=_BINARY,
    )
    assert cfg is not None
    assert cfg.parent_n == 4
    assert cfg.threshold == 2.5 and cfg.statistic == 0.5
    # min_impurity_decrease
    datos_debiles = (pd.Series([1.0, 2.0, 3.0, 4.0]), pd.Series([0, 1, 0, 1]))
    strict = _engine(min_impurity_decrease=0.3)
    assert strict.evaluate(
        *datos_debiles, predictor="d", predictor_type=_CONTINUOUS,
        target_type=_BINARY,
    ) is None  # dI_max = 1/6 < 0.3
    lax = _engine(min_impurity_decrease=0.1)
    cfg_lax = lax.evaluate(
        *datos_debiles, predictor="d", predictor_type=_CONTINUOUS,
        target_type=_BINARY,
    )
    assert cfg_lax is not None
    assert math.isclose(cfg_lax.statistic, 1.0 / 6.0, rel_tol=1e-12)


def test_guards():
    eng = _engine()
    _assert_raises(ValueError, CrtEngine, min_impurity_decrease=-0.1)
    _assert_raises(ValueError, CrtEngine, max_exhaustive_cardinality=1)
    _assert_raises(ValueError, CrtEngine, max_exhaustive_cardinality=1.5)
    _assert_raises(ValueError, CrtEngine, max_surrogates=-1)
    _assert_raises(
        ValueError, eng.evaluate,
        pd.Series([1.0, 2.0]), pd.Series([0, 1, 1]),
        predictor="len", predictor_type=_CONTINUOUS, target_type=_BINARY,
    )
    _assert_raises(
        ValueError, eng.evaluate,
        pd.Series([1.0, 2.0, np.inf, 4.0]), pd.Series([0, 1, 0, 1]),
        predictor="inf", predictor_type=_CONTINUOUS, target_type=_BINARY,
    )
    _assert_raises(
        ValueError, eng.evaluate,
        pd.Series([["a"], ["b"], ["a"], ["b"]]), pd.Series([0, 1, 0, 1]),
        predictor="nh", predictor_type=_NOMINAL, target_type=_BINARY,
    )


# ---------------------------------------------------------------------------
# 8. best_split
# ---------------------------------------------------------------------------


def test_best_split():
    # fuerte: dI = 0.5 ; debil: dI = 0.125
    X = pd.DataFrame({
        "fuerte": pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]),
        "debil": pd.Series([1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0]),
    })
    y = pd.Series([0, 0, 0, 0, 1, 1, 1, 1])
    eng = _engine()
    best = eng.best_split(
        X, y, {"fuerte": _CONTINUOUS, "debil": _CONTINUOUS},
        target_type=_BINARY,
    )
    assert best is not None
    assert best.predictor == "fuerte"
    assert math.isclose(best.statistic, 0.5, rel_tol=1e-12)
    # empate: gana el primero del spec
    X2 = pd.DataFrame({"p1": X["fuerte"], "p2": X["fuerte"]})
    best2 = eng.best_split(
        X2, y, {"p1": _CONTINUOUS, "p2": _CONTINUOUS}, target_type=_BINARY,
    )
    assert best2 is not None and best2.predictor == "p1"
    # ninguno valido -> None
    yc = pd.Series([1] * 8)
    assert eng.best_split(
        X, yc, {"fuerte": _CONTINUOUS}, target_type=_BINARY,
    ) is None


# ---------------------------------------------------------------------------
# 9. Humo N=200k (continuo + nominal)
# ---------------------------------------------------------------------------


def test_humo_n200k():
    rng = np.random.default_rng(7)
    n = 200_000
    xc = pd.Series(rng.normal(0.0, 1.0, n))
    score = 1.0 / (1.0 + np.exp(-xc.to_numpy()))
    y = pd.Series((rng.random(n) < score).astype(np.int8))
    cats = np.array([f"c{i:02d}" for i in range(10)], dtype=object)
    xn = pd.Series(cats[rng.integers(0, 10, n)])

    eng = _engine()
    t0 = time.perf_counter()
    cfg_c = eng.evaluate(
        xc, y, predictor="xc", predictor_type=_CONTINUOUS, target_type=_BINARY
    )
    cfg_n = eng.evaluate(
        xn, y, predictor="xn", predictor_type=_NOMINAL, target_type=_BINARY
    )
    dt = time.perf_counter() - t0

    for cfg in (cfg_c, cfg_n):
        assert isinstance(cfg, SplitConfig)
        assert cfg.parent_n == n
        assert sum(cfg.child_ns) == n
        assert cfg.statistic > 0.0
    assert cfg_c.threshold is not None
    assert cfg_n.branches is not None and len(cfg_n.branches) == 2
    assert dt < 10.0, f"humo 200k demasiado lento: {dt:.2f}s"
    print(f"[humo] N=200k continuo+nominal -> {dt:.3f}s "
          f"(dI_c={cfg_c.statistic:.4g}, dI_n={cfg_n.statistic:.4g})")


# ---------------------------------------------------------------------------
# 10. 3.2.c - Ponderacion por muestra (weights en evaluate/best_split/
#     surrogate_splits/_embedded_split)
# ---------------------------------------------------------------------------


def _gini_dI_manual(izq: np.ndarray, y: np.ndarray, w: np.ndarray,
                    k_cls: int = 2) -> float:
    """Ganancia de Gini ponderada de una asignacion izq/der (manual)."""
    w_total = float(w.sum())
    counts = np.array([w[y == k].sum() for k in range(k_cls)])
    p = counts / w_total
    i_parent = 1.0 - float((p * p).sum())
    d_i = i_parent
    for lado in (izq, ~izq):
        wl = w[lado]
        wl_total = float(wl.sum())
        cl = np.array([wl[y[lado] == k].sum() for k in range(k_cls)])
        pl = cl / wl_total
        d_i -= (wl_total / w_total) * (1.0 - float((pl * pl).sum()))
    return d_i


def _fixture_cls_ponderable(n=400, seed=3):
    rng = np.random.default_rng(seed)
    x = pd.Series(rng.normal(0.0, 1.0, n))
    score = 1.0 / (1.0 + np.exp(-x.to_numpy()))
    y = pd.Series((rng.random(n) < score).astype(int))
    w = rng.uniform(0.5, 2.0, n)
    return x, y, w


def test_weighted_crt_parity_classification():
    x, y, _ = _fixture_cls_ponderable()
    eng = _engine()
    ref = eng.evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS, target_type=_BINARY
    )
    res = eng.evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS,
        target_type=_BINARY, weights=np.ones(len(x)),
    )
    assert ref is not None and res is not None
    assert res.statistic == ref.statistic
    assert res.statistic_name == ref.statistic_name == "gini_gain"
    assert res.threshold == ref.threshold
    assert res.branches == ref.branches
    assert res.child_ns == ref.child_ns
    assert res.parent_n == ref.parent_n
    assert res.impurity_gain == ref.impurity_gain


def test_weighted_crt_parity_regression():
    rng = np.random.default_rng(5)
    x = pd.Series(rng.normal(0.0, 1.0, 400))
    y = pd.Series(x.to_numpy() * 2.0 + rng.normal(0.0, 0.5, 400))
    eng = _engine()
    ref = eng.evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS, target_type=_T_CONT
    )
    res = eng.evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS,
        target_type=_T_CONT, weights=np.ones(len(x)),
    )
    assert ref is not None and res is not None
    assert res.statistic == ref.statistic
    assert res.statistic_name == ref.statistic_name == "variance_gain"
    assert res.threshold == ref.threshold
    assert res.child_ns == ref.child_ns
    assert res.parent_n == ref.parent_n
    assert res.impurity_gain == ref.impurity_gain


def test_weighted_crt_child_ns_physical_continuous():
    x, y, w = _fixture_cls_ponderable()
    cfg = _engine().evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS,
        target_type=_BINARY, weights=w,
    )
    assert cfg is not None
    assert cfg.parent_n == len(y)
    assert sum(cfg.child_ns) == len(y)
    assert all(isinstance(n, int) for n in cfg.child_ns)


def test_weighted_crt_child_ns_physical_nominal():
    rng = np.random.default_rng(9)
    n = 300
    x = pd.Series(rng.choice(["a", "b", "c", "d"], n))
    rate = np.array([{"a": 0.1, "b": 0.3, "c": 0.7, "d": 0.9}[v] for v in x])
    y = pd.Series((rng.random(n) < rate).astype(int))
    w = rng.uniform(0.5, 2.0, n)
    cfg = _engine().evaluate(
        x, y, predictor="x", predictor_type=_NOMINAL,
        target_type=_BINARY, weights=w,
    )
    assert cfg is not None
    assert cfg.parent_n == len(y)
    assert sum(cfg.child_ns) == len(y)
    assert all(isinstance(nn, int) for nn in cfg.child_ns)


def test_weighted_crt_scale_invariance():
    x, y, w = _fixture_cls_ponderable()
    eng = _engine()
    a = eng.evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS,
        target_type=_BINARY, weights=w,
    )
    b = eng.evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS,
        target_type=_BINARY, weights=w * 7.5,
    )
    assert a is not None and b is not None
    assert math.isclose(a.statistic, b.statistic, rel_tol=1e-9)
    assert math.isclose(a.impurity_gain, b.impurity_gain, rel_tol=1e-9)
    assert a.threshold == b.threshold
    assert a.child_ns == b.child_ns


def test_weighted_crt_regression_scale_invariance():
    rng = np.random.default_rng(17)
    x = pd.Series(rng.normal(0.0, 1.0, 400))
    y = pd.Series(x.to_numpy() * 2.0 + rng.normal(0.0, 0.5, 400))
    w = rng.uniform(0.5, 2.0, 400)
    eng = _engine()
    a = eng.evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS,
        target_type=_T_CONT, weights=w,
    )
    b = eng.evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS,
        target_type=_T_CONT, weights=w * 7.5,
    )
    assert a is not None and b is not None
    assert math.isclose(a.statistic, b.statistic, rel_tol=1e-9)
    assert a.threshold == b.threshold
    assert a.child_ns == b.child_ns


def test_weighted_crt_continuous_matches_manual_gini():
    x = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    y = pd.Series([0, 0, 1, 0, 1, 1, 0, 1])
    w = np.array([1.0, 1.0, 2.0, 1.0, 2.0, 1.0, 1.0, 3.0])
    cfg = _engine().evaluate(
        x, y, predictor="x", predictor_type=_CONTINUOUS,
        target_type=_BINARY, weights=w,
    )
    assert cfg is not None and cfg.threshold is not None
    izq = x.to_numpy() <= float(cfg.threshold)
    manual = _gini_dI_manual(izq, y.to_numpy(), w)
    assert math.isclose(cfg.impurity_gain, manual, rel_tol=1e-12)
    assert math.isclose(cfg.statistic, manual, rel_tol=1e-12)
    # sin pesos la ganancia en ese mismo umbral seria distinta
    manual_sin = _gini_dI_manual(izq, y.to_numpy(), np.ones(8))
    assert not math.isclose(manual, manual_sin, rel_tol=1e-9)


def test_weighted_crt_nominal_matches_manual_gini():
    x = pd.Series(["a", "a", "b", "b", "c", "c", "a", "c"])
    y = pd.Series([0, 1, 0, 0, 1, 1, 0, 1])
    w = np.array([1.0, 2.0, 1.0, 3.0, 1.0, 1.0, 2.0, 2.0])
    cfg = _engine().evaluate(
        x, y, predictor="x", predictor_type=_NOMINAL,
        target_type=_BINARY, weights=w,
    )
    assert cfg is not None and cfg.branches is not None
    izq = x.isin(list(cfg.branches[0])).to_numpy()
    manual = _gini_dI_manual(izq, y.to_numpy(), w)
    assert math.isclose(cfg.impurity_gain, manual, rel_tol=1e-12)
    assert sum(cfg.child_ns) == len(y)


def test_weighted_crt_rejects_wrong_length():
    x, y, _ = _fixture_cls_ponderable()
    try:
        _engine().evaluate(
            x, y, predictor="x", predictor_type=_CONTINUOUS,
            target_type=_BINARY, weights=np.ones(len(x) - 1),
        )
    except ValueError as e:
        assert "weights" in str(e) and "longitud" in str(e)
    else:
        raise AssertionError("no lanzo ValueError")


def test_weighted_crt_rejects_nonpositive():
    x, y, _ = _fixture_cls_ponderable()
    for bad_value in (0.0, -1.0):
        w = np.ones(len(x))
        w[2] = bad_value
        try:
            _engine().evaluate(
                x, y, predictor="x", predictor_type=_CONTINUOUS,
                target_type=_BINARY, weights=w,
            )
        except ValueError as e:
            assert "positivos" in str(e)
        else:
            raise AssertionError("no lanzo ValueError")


def test_weighted_crt_surrogate_parity_with_uniform_weights():
    rng = np.random.default_rng(21)
    n = 500
    x1 = pd.Series(rng.normal(0.0, 1.0, n))
    x2 = pd.Series(x1.to_numpy() + rng.normal(0.0, 0.3, n))
    y = pd.Series(
        (rng.random(n) < 1.0 / (1.0 + np.exp(-x1.to_numpy()))).astype(int)
    )
    X = pd.DataFrame({"x1": x1, "x2": x2})
    spec = {"x1": _CONTINUOUS, "x2": _CONTINUOUS}
    eng = _engine()
    prim = eng.best_split(X, y, spec, target_type=_BINARY)
    assert prim is not None
    s0 = eng.surrogate_splits(prim, X, y, spec, target_type=_BINARY)
    s1 = eng.surrogate_splits(
        prim, X, y, spec, target_type=_BINARY, weights=np.ones(n)
    )
    assert len(s0) == len(s1) > 0
    assert s0 == s1


def test_weighted_crt_surrogate_embedded_child_ns_physical():
    rng = np.random.default_rng(23)
    n = 500
    x1 = pd.Series(rng.normal(0.0, 1.0, n))
    x2 = pd.Series(x1.to_numpy() + rng.normal(0.0, 0.3, n))
    y = pd.Series(
        (rng.random(n) < 1.0 / (1.0 + np.exp(-x1.to_numpy()))).astype(int)
    )
    w = rng.uniform(0.5, 2.0, n)
    X = pd.DataFrame({"x1": x1, "x2": x2})
    spec = {"x1": _CONTINUOUS, "x2": _CONTINUOUS}
    eng = _engine()
    prim = eng.best_split(X, y, spec, target_type=_BINARY)
    assert prim is not None
    surrogates = eng.surrogate_splits(
        prim, X, y, spec, target_type=_BINARY, weights=w
    )
    assert len(surrogates) > 0
    for sur in surrogates:
        cfg = sur.split
        n_no_nulos = int((X[cfg.predictor].notna() & y.notna()).sum())
        assert cfg.parent_n == n_no_nulos
        assert sum(cfg.child_ns) == cfg.parent_n
        assert all(isinstance(nn, int) for nn in cfg.child_ns)


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
