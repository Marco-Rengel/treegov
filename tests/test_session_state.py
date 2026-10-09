"""Tests de backend_v3/session_state.py (Fase 1). Dual: pytest o python directo.

Fixture: CSV sintetico en tempfile (fuera del repo; ninguna escritura en
data/). y = 1_{edad >= 40} con 120 filas: la particion por defecto es
determinista y los cortes del arbol quedan asegurados por CRT.
"""

import logging
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.crt_engine import CrtEngine  # noqa: E402
from backend_v3.session_state import FlowState, Session, SessionState  # noqa: E402
from backend_v3.types import PredictorType  # noqa: E402


def _quiet_logger(name="treegov.session.tests"):
    lg = logging.getLogger(name)
    if not lg.handlers:
        lg.addHandler(logging.NullHandler())
    lg.propagate = False
    return lg


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


def _csv(tmp: Path) -> Path:
    n = 120
    edad = np.tile(np.arange(20, 60), 3)  # 40 valores distintos x 3
    seg = np.tile(["a", "b", "c"], 40)
    y = (edad >= 40).astype(int)
    df = pd.DataFrame({"edad": edad, "seg": seg, "default": y})
    p = tmp / "mini.csv"
    df.to_csv(p, index=False)
    return p


# ---------------------------------------------------------------------------
# estado cero y transiciones
# ---------------------------------------------------------------------------


def test_estado_cero_formal():
    s = Session(logger=_quiet_logger())
    st = s.state
    assert st.state is FlowState.EMPTY
    assert st.csv_path is None and st.tree is None and st.spec is None
    assert st.train_idx is None and st.test_idx is None
    assert st.event_log == ("init/state=EMPTY",)


def test_transiciones_ilegales():
    s = Session(logger=_quiet_logger())
    _assert_raises(ValueError, s.fix_spec, "default",
                   target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
    _assert_raises(ValueError, s.partition)
    _assert_raises(ValueError, s.train, CrtEngine())


def test_flujo_completo_y_bitacora():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())

        st1 = s.load_dataset(str(csv_path))
        assert st1.state is FlowState.DATA_LOADED
        assert st1.n_rows == 120 and st1.n_cols == 3

        st2 = s.fix_spec("default", target_class=1,
                         class_labels={0: "Bueno", 1: "Malo"})
        assert st2.state is FlowState.SPEC_FIXED
        assert st2.spec is not None
        spec_d = dict(st2.spec)
        assert spec_d["edad"] == PredictorType.CONTINUOUS
        assert spec_d["seg"] == PredictorType.NOMINAL
        assert isinstance(st2.spec, tuple)  # inmutable (OBS 4)

        st3 = s.partition(train_frac=0.7, seed=42)
        assert st3.state is FlowState.PARTITIONED
        assert st3.train_idx is not None and st3.test_idx is not None
        assert len(st3.train_idx) == 84 and len(st3.test_idx) == 36

        st4 = s.train(CrtEngine(), max_depth=4, min_child_size=5)
        assert st4.state is FlowState.TRAINED
        assert st4.tree is not None
        assert st4.tree.method == "CRT"
        assert st4.tree.nodes[0].split is not None

        # bitacora: init + 4 transiciones, en orden
        assert len(st4.event_log) == 5
        assert st4.event_log[0] == "init/state=EMPTY"
        assert st4.event_log[1].startswith("load_dataset:")
        assert st4.event_log[2].startswith("fix_spec:default")
        assert st4.event_log[3].startswith("partition:")
        assert st4.event_log[4].startswith("train:CRT")


def test_atomicidad_fallo_no_corrompe_estado():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        # target invalido -> ValueError; el estado debe quedar DATA_LOADED
        _assert_raises(ValueError, s.fix_spec, "no_existe",
                       target_class=1,
                       class_labels={0: "Bueno", 1: "Malo"})
        assert s.state.state is FlowState.DATA_LOADED
        # reintento valido tiene que funcionar
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        assert s.state.state is FlowState.SPEC_FIXED


def test_guards_target():
    with tempfile.TemporaryDirectory() as td:
        # target con NaN
        df2 = pd.DataFrame({"edad": [1.0, 2.0, 3.0], "yn": [0.0, np.nan, 1.0]})
        p2 = Path(td) / "mnan.csv"
        df2.to_csv(p2, index=False)
        s2 = Session(logger=_quiet_logger())
        s2.load_dataset(str(p2))
        _assert_raises(ValueError, s2.fix_spec, "yn",
                       target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        # target no 0/1 (p. ej. 1/2)
        df3 = pd.DataFrame({"edad": [1.0, 2.0, 3.0, 4.0], "y12": [1, 1, 2, 2]})
        p3 = Path(td) / "m12.csv"
        df3.to_csv(p3, index=False)
        s3 = Session(logger=_quiet_logger())
        s3.load_dataset(str(p3))
        _assert_raises(ValueError, s3.fix_spec, "y12",
                       target_class=1, class_labels={0: "Bueno", 1: "Malo"})


def test_determinismo_dos_sesiones():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        arboles = []
        for _ in range(2):
            s = Session(logger=_quiet_logger())
            s.load_dataset(str(csv_path))
            s.fix_spec("default", target_class=1,
                       class_labels={0: "Bueno", 1: "Malo"})
            s.partition(train_frac=0.7, seed=42)
            s.train(CrtEngine(), max_depth=4, min_child_size=5)
            arboles.append(s.state.tree)
        assert arboles[0] is not None and arboles[0] == arboles[1]
        assert (
            arboles[0].params_fingerprint == arboles[1].params_fingerprint
        )


def test_partition_guard_frac():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        _assert_raises(ValueError, s.partition, 1.5)


# ---------------------------------------------------------------------------
# Fase 1.2: evaluate_oos + prune
# ---------------------------------------------------------------------------


def test_evaluate_oos_e2e_valores_exactos():
    """Modelo CRT sobre y = 1_{edad>=40}: OOS perfecto. Valores a mano:
    pd hoja baja = 0.5/43, pd alta = 42.5/43; AUC=KS=Gini=PR=1;
    BS = (0.5/43)^2 ; BSS = 1 - BS/0.25."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        st = s.evaluate_oos(n_groups=3)

        m = st.oos_metrics
        assert m is not None
        assert m.n_test == 36 and m.n_events == 18
        assert m.auc == 1.0 and m.gini == 1.0 and m.ks == 1.0
        assert m.pr_auc == 1.0
        esperado_bs = (0.5 / 43.0) ** 2  # 0.25/1849
        assert math.isclose(m.brier, esperado_bs, rel_tol=1e-9)
        assert math.isclose(m.brier_ref, 0.25, rel_tol=1e-12)
        assert math.isclose(m.brier_skill, 1.0 - esperado_bs / 0.25, rel_tol=1e-9)
        assert m.hl_df == 1
        assert math.isclose(m.hl_stat, 24.0 / 85.0, rel_tol=1e-12)
        # ROC de separacion perfecta: (0,0,inf) -> (0,1,pd_alta) -> (1,1,pd_baja)
        assert m.roc_points[0] == (0.0, 0.0, math.inf)
        assert m.roc_points[1] == (0.0, 1.0, 42.5 / 43.0)
        # event_log sigue siendo determinista (sin timestamps)
        assert st.event_log[-1].startswith("evaluate_oos:")


def test_transiciones_oos_requieren_trained():
    s = Session(logger=_quiet_logger())
    _assert_raises(ValueError, s.evaluate_oos)
    _assert_raises(ValueError, s.prune, 1.0)


def test_prune_flujo_completo():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        st0 = s.state
        # el fixture produce raiz con 2 hijos puros: alpha de la secuencia > 0
        st = s.prune(0.0)  # alpha 0: si ningun paso es 0, modelo intacto
        assert st.pruned_tree is not None
        assert st.prune_alpha == 0.0
        assert st.event_log[-1].startswith("prune:alpha=0")
        # poda fuerte colapsa a raiz sola
        st2 = s.prune(999999.0)
        assert len(st2.pruned_tree.nodes) == 1
        assert st2.pruned_tree.nodes[0].is_leaf
        # idempotencia sobre el ORIGINAL: no apila (sigue 1 nodo)
        st3 = s.prune(999999.0)
        assert len(st3.pruned_tree.nodes) == 1
        # tree original sigue intacto (inmutable)
        assert len(st3.tree.nodes) == len(st0.tree.nodes)


# ---------------------------------------------------------------------------
# Fase 1.3: OOT + estabilidad
# ---------------------------------------------------------------------------


def _csv_seg_driven(tmp: Path) -> Path:
    """Dev donde el target depende de la categorica 'seg' (y=1 si seg=='b'):
    el arbol DEBE cortar por seg; la categoria nueva en OOT no enruta."""
    n = 120
    seg = np.tile(["a", "b", "c"], 40)
    edad = np.tile(np.arange(20, 60), 3)
    df = pd.DataFrame({"edad": edad, "seg": seg,
                       "default": (seg == "b").astype(int)})
    p = tmp / "dev2.csv"
    df.to_csv(p, index=False)
    return p


def _csv_oot(tmp: Path, *, temporal: bool, con_nueva_cat: bool = False) -> Path:
    """Cohorte OOT: con seg-driven dev, la categoria 'd' (nueva) no enruta."""
    n = 60
    seg = np.tile(["a", "b", "d"], 20)            # 'd' no existe en train
    if not con_nueva_cat:
        seg = np.tile(["a", "b", "c"], 20)
    edad = np.tile(np.arange(20, 60), 2)[:n]
    df = pd.DataFrame({"edad": edad, "seg": seg,
                       "default": (seg == "b").astype(int)})
    if temporal:
        df["fecha"] = pd.Series(
            pd.date_range("2026-03-01", periods=n, freq="D")
        ).astype(str)
    p = tmp / "oot.csv"
    df.to_csv(p, index=False)
    return p


def test_load_oot_y_evaluate_oot_e2e():
    """Dev seg-driven (120 filas) -> train (arbol corta por seg) -> OOT con
    categoria nueva 'd': no aborta, n_excluded == 20 (un tercio de 60)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        csv_dev = _csv_seg_driven(tmp)
        csv_oot = _csv_oot(tmp, temporal=False, con_nueva_cat=True)

        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)

        st = s.load_oot(str(csv_oot))
        assert st.state.name == "OOT_LOADED"
        assert st.n_oot == 60
        assert st.temporal_verified is False     # sin time_col -> WARNING

        st2 = s.evaluate_oot(n_groups=3)
        assert st2.state.name == "OOT_EVALUATED"
        rep = st2.oot_report
        assert rep is not None
        # la categoria nueva 'd' no enruta -> exactamente 20 filas excluidas
        assert rep.n_excluded == 20
        assert rep.metrics is not None
        # PSI de hojas incluye el bin UNSEEN con eps -> psi > 0 (deriva nueva)
        assert rep.psi.psi > 0.0
        # CSI de 'seg' contiene <OTHER> con contribucion positiva
        seg_rows = [r for r in rep.csi if r.predictor == "seg"]
        assert seg_rows and seg_rows[0].csi > 0.0
        etiquetas = [e for (e, _, _, _) in seg_rows[0].per_bin]
        assert "<OTHER>" in etiquetas
        # CSI de 'edad': mismas distribuciones base, pero el train es un
        # subset estratificado por target (Hamilton-Hare); los deciles del
        # train distan un poco del OOT completo. Senal correcta: STABLE.
        edad_rows = [r for r in rep.csi if r.predictor == "edad"]
        assert edad_rows and edad_rows[0].flag in ("STABLE", "MODERATE")
        # narrative verifiable
        assert rep.drop.temporal_verified is False
        assert "excluidas" in st2.event_log[-1]


def test_load_oot_temporal_verificado():
    """Con time_col presente en AMBOS datasets: OOT posterior -> True;
    solapamiento -> ValueError."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # dev con columna temporal febrero
        n = 120
        edad = np.tile(np.arange(20, 60), 3)
        seg = np.tile(["a", "b", "c"], 40)
        y = (edad >= 40).astype(int)
        df = pd.DataFrame({"edad": edad, "seg": seg, "default": y})
        df["fecha"] = pd.Series(
            pd.date_range("2026-01-01", periods=n, freq="D")
        ).astype(str)
        csv_dev = tmp / "dev_t.csv"
        df.to_csv(csv_dev, index=False)

        # OOT con febrero/marzo posterior
        n2 = 60
        edad2 = np.tile(np.arange(20, 60), 2)[:n2]
        seg2 = np.tile(["a", "b", "c"], 20)
        df2 = pd.DataFrame({
            "edad": edad2, "seg": seg2, "default": (edad2 >= 40).astype(int),
        })
        df2["fecha"] = pd.Series(
            pd.date_range("2026-05-01", periods=n2, freq="D")
        ).astype(str)
        csv_oot = tmp / "oot_t.csv"
        df2.to_csv(csv_oot, index=False)

        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        s.fix_spec("default", spec={"edad": PredictorType.CONTINUOUS,
                                    "seg": PredictorType.NOMINAL},
                   target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        # time_col es metadato (fuera del spec): fecha presente en ambos
        st = s.load_oot(str(csv_oot), time_col="fecha")
        assert st.temporal_verified is True

        # fuga temporal: dev tiene mayo en un CSV aparte...
        s2 = Session(logger=_quiet_logger())
        s2.load_dataset(str(csv_oot))            # este archivo es "posterior"
        s2.fix_spec("default", spec={"edad": PredictorType.CONTINUOUS,
                                     "seg": PredictorType.NOMINAL},
                    target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s2.partition(train_frac=0.7, seed=42)
        s2.train(CrtEngine(), max_depth=4, min_child_size=5)
        # OOT = el dev (enero) es mas viejo que el "train" (mayo) -> ValueError
        _assert_raises(ValueError, s2.load_oot, str(csv_dev), time_col="fecha")


def test_load_oot_guards():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        csv_dev = _csv(tmp)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        # archivo inexistente
        _assert_raises(FileNotFoundError, s.load_oot, str(tmp / "no.csv"))
        # columnas que no coinciden
        mal = pd.DataFrame({"edad": [30, 40], "seg": ["a", "b"], "otra": [1, 2]})
        pm = tmp / "mal.csv"
        mal.to_csv(pm, index=False)
        _assert_raises(ValueError, s.load_oot, str(pm))
        # target no binario
        mal2 = pd.DataFrame({"edad": [30, 40], "seg": ["a", "b"], "default": [1, 2]})
        pm2 = tmp / "mal2.csv"
        mal2.to_csv(pm2, index=False)
        _assert_raises(ValueError, s.load_oot, str(pm2))


# ---------------------------------------------------------------------------
# Fase 2.1: describe_dataset / fix_spec(predictors) / train(str) / reset
# ---------------------------------------------------------------------------


def test_describe_dataset():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        # sin dataset -> RuntimeError (lectura pura, no hay transicion)
        _assert_raises(RuntimeError, s.describe_dataset)
        s.load_dataset(str(csv_path))
        cols, tipos = s.describe_dataset()
        assert cols == ("edad", "seg", "default")
        # edad: 40 valores > 20 -> CONTINUOUS; seg: texto -> NOMINAL;
        # default: numerico binario (2 <= 20) -> ORDINAL
        assert tipos == {"edad": "CONTINUOUS", "seg": "NOMINAL",
                         "default": "ORDINAL"}
        # lectura pura: el estado no cambia
        assert s.state.state is FlowState.DATA_LOADED


def test_fix_spec_predictors_subset():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        st = s.fix_spec("default", predictors=["edad"], target_class=1,
                        class_labels={0: "Bueno", 1: "Malo"})
        spec_d = dict(st.spec)
        assert list(spec_d) == ["edad"]            # solo el predictor elegido
        assert spec_d["edad"] is PredictorType.CONTINUOUS
        # el flujo completo funciona con el subset
        s.partition(train_frac=0.7, seed=42)
        st4 = s.train("CRT", max_depth=4, min_child_size=5)
        assert st4.tree is not None
        assert st4.tree.nodes[0].split.predictor == "edad"


def test_fix_spec_predictors_invalidos():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        # predictor inexistente
        _assert_raises(ValueError, s.fix_spec, "default", predictors=["no_existe"],
                       target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        # target no puede ser predictor
        _assert_raises(ValueError, s.fix_spec, "default", predictors=["edad", "default"],
                       target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        # subset vacio -> spec vacio
        _assert_raises(ValueError, s.fix_spec, "default", predictors=[],
                       target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        # atomicidad: tras los fallos el estado sigue DATA_LOADED
        assert s.state.state is FlowState.DATA_LOADED


def test_train_engine_por_string():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        arboles = []
        for eng in ("CRT", CrtEngine()):
            s = Session(logger=_quiet_logger())
            s.load_dataset(str(csv_path))
            s.fix_spec("default", target_class=1,
                       class_labels={0: "Bueno", 1: "Malo"})
            s.partition(train_frac=0.7, seed=42)
            s.train(eng, max_depth=4, min_child_size=5)
            arboles.append(s.state.tree)
        # factory por nombre == instancia manual (mismo fingerprint)
        assert arboles[0] == arboles[1]
        assert arboles[0].params_fingerprint == arboles[1].params_fingerprint
        assert arboles[0].method == "CRT"


def test_train_engine_string_invalido():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        _assert_raises(ValueError, s.train, "XGBOOST")
        assert s.state.state is FlowState.PARTITIONED   # atomicidad


def test_reset_to_data_loaded():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        # en EMPTY no hay nada que resetear
        _assert_raises(ValueError, s.reset_to_data_loaded)
        s.load_dataset(str(csv_path))
        df_ref = s._df                       # cache interno (privado, test ok)
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        assert s.state.state is FlowState.TRAINED

        st = s.reset_to_data_loaded()
        assert st.state is FlowState.DATA_LOADED
        assert st.csv_path == str(csv_path)
        assert st.n_rows == 120 and st.n_cols == 3
        # artefactos posteriores descartados
        assert st.spec is None and st.tree is None and st.train_idx is None
        assert s._df is df_ref               # CSV NO releido (mismo objeto)
        assert s._X_train is None and s._imputer is None
        assert st.event_log[-1] == "reset_to_data_loaded"
        # el flujo puede rehacerse sin releer el archivo
        s.fix_spec("default", predictors=["seg"], target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        assert dict(s.state.spec) == {"seg": PredictorType.NOMINAL}


# ---------------------------------------------------------------------------
# Fase 2.4.c.1: get_gains_table / get_classification_matrix
# ---------------------------------------------------------------------------


def test_get_gains_table_returns_dict():
    """Gains table OOS sobre fixture que separa perfecto: 36 filas, KS=AUC=Gini=1."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        gt = s.get_gains_table(partition="oos")
        assert gt is not None
        assert gt["by"] == "leaf"
        assert gt["n_total"] == 36
        assert gt["n_good"] == 18
        assert gt["n_bad"] == 18
        assert gt["n_excluded"] == 0
        assert len(gt["rows"]) >= 1
        assert sum(r["n"] for r in gt["rows"]) == 36
        assert gt["ks"] is not None and math.isclose(gt["ks"], 1.0, rel_tol=1e-9)
        assert math.isclose(gt["auc"], 1.0, rel_tol=1e-9)
        assert math.isclose(gt["gini"], 1.0, rel_tol=1e-9)


def test_get_gains_table_returns_none_without_tree():
    """Sin modelo entrenado ambos getters devuelven None (patrón get_oos_oot_report)."""
    s = Session(logger=_quiet_logger())
    assert s.get_gains_table() is None
    assert s.get_classification_matrix() is None


def test_get_gains_table_partition_oot_without_oot():
    """Partition 'oot' sin cohorte cargada: RuntimeError (caché no poblada)."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        _assert_raises(RuntimeError, s.get_gains_table, partition="oot")
        _assert_raises(RuntimeError, s.get_classification_matrix, partition="oot")


def test_get_classification_matrix_custom_threshold():
    """ClassificationMatrix con threshold=0.3: conteos suman n_total."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        cm = s.get_classification_matrix(partition="oos", threshold=0.3)
        assert cm is not None
        assert math.isclose(cm["threshold"], 0.3, rel_tol=1e-12)
        assert cm["n_total"] == 36
        assert cm["tp"] + cm["tn"] + cm["fp"] + cm["fn"] == 36
        assert cm["n_excluded"] == 0


def test_get_gains_table_invalid_partition():
    """Partition desconocida: ValueError con lista de válidas."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        _assert_raises(ValueError, s.get_gains_table, partition="foo")
        _assert_raises(ValueError, s.get_classification_matrix, partition="foo")


# ---------------------------------------------------------------------------
# Fase 3.1.c paso 3: target_class / class_labels en fix_spec; bloqueo de
# motores binarios (CRT/QUEST) con target multiclase; CHAID permitido
# ---------------------------------------------------------------------------


def _csv_k3(tmp: Path) -> Path:
    """CSV con target de 3 clases {0,1,2} (120 filas).
    Predictores categoricos: CHAID no admite continuos."""
    seg1 = np.tile(["a", "b", "c"], 40)
    seg2 = np.tile(["x", "y", "z"], 40)
    df = pd.DataFrame({"seg1": seg1, "seg2": seg2,
                       "default": np.tile([0, 1, 2], 40)})
    p = tmp / "k3.csv"
    df.to_csv(p, index=False)
    return p


def test_fix_spec_requires_target_class():
    """Paso 4 (endurecimiento): omitir target_class lanza TypeError."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _assert_raises(TypeError, s.fix_spec, "default",
                       class_labels={0: "Bueno", 1: "Malo"})
        assert s.state.state is FlowState.DATA_LOADED


def test_fix_spec_requires_class_labels():
    """Paso 4 (endurecimiento): omitir class_labels lanza TypeError."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _assert_raises(TypeError, s.fix_spec, "default", target_class=1)
        assert s.state.state is FlowState.DATA_LOADED


def test_fix_spec_persists_target_class_and_labels():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        assert s.state.target_class == 1
        assert s.state.class_labels == ((0, "Bueno"), (1, "Malo"))


def test_fix_spec_class_labels_missing_key():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        # falta la clave 1 -> ValueError
        _assert_raises(ValueError, s.fix_spec, "default",
                       target_class=1, class_labels={0: "Bueno"})


def test_fix_spec_class_labels_extra_key():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        # clave 2 no observada en el target -> ValueError
        _assert_raises(ValueError, s.fix_spec, "default",
                       target_class=1,
                       class_labels={0: "B", 1: "M", 2: "X"})


def test_fix_spec_multiclass_k3_accepted():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        assert s.state.state is FlowState.SPEC_FIXED
        assert s.state.target_class == 2
        assert len(s.state.target_classes) == 3


def test_train_blocks_crt_multiclass():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition()
        _assert_raises(ValueError, s.train, "CRT")


def test_train_blocks_quest_multiclass():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition()
        _assert_raises(ValueError, s.train, "QUEST")


def test_train_allows_chaid_multiclass():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition()
        s.train("CHAID", max_depth=3, min_child_size=5)
        assert s.state.state is FlowState.TRAINED


def test_train_allows_chaid_exhaustive_multiclass():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition()
        s.train("CHAID_EXHAUSTIVE", max_depth=3, min_child_size=5)
        assert s.state.state is FlowState.TRAINED


def test_class_labels_dict_property():
    s = Session(logger=_quiet_logger())
    assert s.class_labels_dict == {}
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        assert s.class_labels_dict == {0: "Bueno", 1: "Malo"}


def test_evaluate_oos_multiclass_raises():
    """Fase 3.1.d: evaluate_oos bloquea K>2 con ValueError."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition(train_frac=0.7, seed=42)
        s.train("CHAID", max_depth=3, min_child_size=5)
        _assert_raises(ValueError, s.evaluate_oos)


def test_evaluate_oot_multiclass_raises():
    """Fase 3.1.d: evaluate_oot bloquea K>2 con ValueError."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        csv_dev = _csv_k3(tmp)
        # Cohort OOT K=3: reusamos el mismo fixture (los tests de bloqueo
        # no dependen de la separabilidad real train/OOT).
        csv_oot = tmp / "oot_k3.csv"
        df = pd.read_csv(csv_dev)
        df.to_csv(csv_oot, index=False)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition(train_frac=0.7, seed=42)
        s.train("CHAID", max_depth=3, min_child_size=5)
        # load_oot verifica columnas contra spec+target; como el OOT es
        # el mismo CSV, coincide.
        s.load_oot(str(csv_oot))
        _assert_raises(ValueError, s.evaluate_oot)


def test_classification_matrix_multiclass_raises():
    """Fase 3.1.d: get_classification_matrix bloquea K>2 con ValueError."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition(train_frac=0.7, seed=42)
        s.train("CHAID", max_depth=3, min_child_size=5)
        _assert_raises(ValueError, s.get_classification_matrix)


def test_gains_table_multiclass_raises():
    """Fase 3.1.d: get_gains_table bloquea K>2 (delegado al builder)."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition(train_frac=0.7, seed=42)
        s.train("CHAID", max_depth=3, min_child_size=5)
        _assert_raises(ValueError, s.get_gains_table, partition="oos")


def test_describe_target_returns_counts():
    """describe_target devuelve {valor: freq} ordenado por valor."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        counts = s.describe_target("default")
        # Fixture _csv: y = 1_{edad >= 40}, 120 filas, edad en [20,60).
        # 60 filas con y=0, 60 con y=1.
        assert counts == {0: 60, 1: 60}


def test_describe_target_multiclass():
    """describe_target con K=3."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        counts = s.describe_target("default")
        assert counts == {0: 40, 1: 40, 2: 40}


def test_describe_target_unknown_column():
    """Columna inexistente -> ValueError."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _assert_raises(ValueError, s.describe_target, "no_existe")


def test_describe_target_without_dataset():
    """Sin dataset cargado -> RuntimeError."""
    s = Session(logger=_quiet_logger())
    _assert_raises(RuntimeError, s.describe_target, "default")


def test_describe_target_does_not_mutate_state():
    """Lectura pura: no cambia de estado ni modifica el event_log."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        st_before = s.state
        s.describe_target("default")
        st_after = s.state
        assert st_before is st_after
        assert st_after.state is FlowState.DATA_LOADED
        assert st_after.event_log == st_before.event_log


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
