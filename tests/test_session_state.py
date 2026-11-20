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
from backend_v3.types import PredictorType, TargetType  # noqa: E402


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
        assert m.hl_groups == 2
        assert m.hl_df == 2
        assert math.isclose(m.hl_stat, 36.0 / 85.0, rel_tol=1e-12)
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


def test_get_prune_sequence_returns_dicts():
    """Fase 3.9: Session.get_prune_sequence devuelve DTO plano (dicts).

    El frontend no importa dataclasses del backend: cada paso debe ser
    un dict con claves alpha/n_leaves/r_subtree y valores nativos
    (float/int), no objetos PruneStep.
    """
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        seq = s.get_prune_sequence()
        assert isinstance(seq, list)
        assert seq, "el fixture debe producir al menos un paso de poda"
        for paso in seq:
            assert isinstance(paso, dict)
            assert set(paso) == {"alpha", "n_leaves", "r_subtree"}
            assert type(paso["alpha"]) is float
            assert type(paso["n_leaves"]) is int
            assert type(paso["r_subtree"]) is float
        # solo lectura: no commitea eventos ni muta el estado
        assert s.state.event_log[-1].startswith("train:")
    # guard: requiere TRAINED
    s2 = Session(logger=_quiet_logger())
    _assert_raises(ValueError, s2.get_prune_sequence)


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


def test_train_allows_crt_multiclass():
    """Fase 3.4.a: C&RT se abre a K>2. Reemplaza al pre-3.4
    test_train_blocks_crt_multiclass."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition()
        s.train("CRT", max_depth=3, min_child_size=5, target_type=TargetType.CATEGORICAL)
        assert s.state.state is FlowState.TRAINED
        assert s.state.tree is not None
        assert s.state.tree.method == "CRT"
        # Coherencia: cada nodo del arbol tiene PD vector de K=3 componentes
        # que suma 1.
        for nd in s.state.tree.nodes:
            assert len(nd.pd_final) == 3
            assert abs(sum(nd.pd_final) - 1.0) <= 1e-12


def test_train_allows_quest_multiclass():
    """Fase 3.4.b: QUEST se abre a K>2. Reemplaza al pre-3.4
    test_train_blocks_quest_multiclass."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition()
        s.train("QUEST", max_depth=3, min_child_size=5, target_type=TargetType.CATEGORICAL)
        assert s.state.state is FlowState.TRAINED
        assert s.state.tree is not None
        assert s.state.tree.method == "QUEST"
        for nd in s.state.tree.nodes:
            assert len(nd.pd_final) == 3
            assert abs(sum(nd.pd_final) - 1.0) <= 1e-12


def test_quest_multiclass_k3_tree_is_coherent():
    """Fase 3.4.b: invariantes estructurales del árbol QUEST K=3
    (paralelo a test_crt_multiclass_k3_tree_is_coherent)."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition()
        s.train("QUEST", max_depth=4, min_child_size=5, target_type=TargetType.CATEGORICAL)
        tree = s.state.tree
        assert tree is not None
        assert tree.method == "QUEST"
        for nd in tree.nodes:
            assert sum(nd.n_events) == nd.n
            assert len(nd.pd_final) == 3
            assert len(nd.pd_jeffreys) == 3
            assert len(nd.class_labels) == 3
            assert abs(sum(nd.pd_final) - 1.0) <= 1e-12
            assert abs(sum(nd.pd_jeffreys) - 1.0) <= 1e-12


def test_train_allows_chaid_multiclass():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition()
        s.train("CHAID", max_depth=3, min_child_size=5, target_type=TargetType.CATEGORICAL)
        assert s.state.state is FlowState.TRAINED


def test_train_allows_chaid_exhaustive_multiclass():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition()
        s.train("CHAID_EXHAUSTIVE", max_depth=3, min_child_size=5, target_type=TargetType.CATEGORICAL)
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


def test_gains_table_multiclass_works():
    """Fase 3.5.b: get_gains_table NO bloquea K>2 (delegado al builder
    multiclase). Reemplaza al pre-3.5.b test_gains_table_multiclass_raises.

    El bloqueo anterior era transitivo desde reporting.build_gains_table,
    no un check explícito en Session. La Fase 3.5 §5.1 planifica esta
    apertura como consecuencia de abrir reporting en 3.5.b.
    """
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition(train_frac=0.7, seed=42)
        s.train("CHAID", max_depth=3, min_child_size=5, target_type=TargetType.CATEGORICAL)
        dto = s.get_gains_table(partition="oos")
        assert dto is not None
        # En K>2 el DTO lleva class_labels canónicos (target_class primero)
        # y los conteos por clase.
        assert dto["class_labels"] == ("alto", "bajo", "medio")
        assert len(dto["n_per_class_global"]) == 3
        # El path multiclase del builder no lanza
        assert dto["by"] == "leaf"


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


# ---------------------------------------------------------------------------
# 3.2.f - Ponderacion por muestra
# ---------------------------------------------------------------------------


def _csv_weighted(tmp: Path, *, peso_dtype: str = "float") -> Path:
    """CSV con columna de pesos positiva. y = 1_{edad >= 40}, 120 filas."""
    n = 120
    edad = np.tile(np.arange(20, 60), 3)
    seg = np.tile(["a", "b", "c"], 40)
    y = (edad >= 40).astype(int)
    if peso_dtype == "float":
        # Pesos moderados: la cuota ponderada W_k*frac no puede exceder
        # el numero de filas de la clase (algoritmo de splitting.py).
        peso = np.where(edad >= 40, 1.2, 1.0)
    elif peso_dtype == "bool":
        peso = edad >= 40
    else:
        raise ValueError(peso_dtype)
    df = pd.DataFrame({"edad": edad, "seg": seg, "peso": peso, "default": y})
    p = tmp / "mini_w.csv"
    df.to_csv(p, index=False)
    return p


def _fix_spec_weighted(s: Session, **kwargs) -> None:
    s.fix_spec(
        "default",
        predictors=["edad", "seg"],
        target_class=1,
        class_labels={0: "Bueno", 1: "Malo"},
        **kwargs,
    )


def test_weighted_session_fix_spec_rejects_missing_weight_col():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _assert_raises(ValueError, _fix_spec_weighted, s,
                       weight_col="no_existe")


def test_weighted_session_fix_spec_rejects_weight_col_equals_target():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _assert_raises(ValueError, _fix_spec_weighted, s,
                       weight_col="default")


def test_weighted_session_fix_spec_rejects_weight_col_as_predictor():
    # Defensa en profundidad (diseno v2 §1.2): la columna de pesos no
    # puede ser predictor.
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        try:
            s.fix_spec(
                "default",
                predictors=["edad", "seg", "peso"],
                target_class=1,
                class_labels={0: "Bueno", 1: "Malo"},
                weight_col="peso",
            )
        except ValueError as e:
            assert "predictor" in str(e)
            return
        raise AssertionError("fix_spec no lanzo ValueError (colision)")


def test_weighted_session_fix_spec_rejects_bool_weights():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td), peso_dtype="bool")
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _assert_raises(ValueError, _fix_spec_weighted, s, weight_col="peso")


def test_weighted_session_fix_spec_rejects_nonpositive_weights():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td))
        # Caso cero
        df = pd.read_csv(csv_path)
        df.loc[5, "peso"] = 0.0
        df.to_csv(csv_path, index=False)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        try:
            _fix_spec_weighted(s, weight_col="peso")
        except ValueError as e:
            assert "1" in str(e)  # conteo de infractores
            assert "5" in str(e)  # primer indice infractor
        else:
            raise AssertionError("fix_spec no lanzo ValueError (peso 0)")
        # Caso negativo
        df.loc[5, "peso"] = 2.0
        df.loc[7, "peso"] = -1.0
        df.to_csv(csv_path, index=False)
        s2 = Session(logger=_quiet_logger())
        s2.load_dataset(str(csv_path))
        try:
            _fix_spec_weighted(s2, weight_col="peso")
        except ValueError as e:
            assert "7" in str(e)
        else:
            raise AssertionError("fix_spec no lanzo ValueError (peso -1)")


def test_weighted_session_partition_populates_w_caches():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _fix_spec_weighted(s, weight_col="peso")
        st = s.partition(train_frac=0.7, seed=42)
        assert s._w_train is not None and s._w_test is not None
        assert len(s._w_train) == len(st.train_idx)
        assert len(s._w_test) == len(st.test_idx)
        assert s._w_col == "peso"


def test_weighted_session_reset_clears_w_caches():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _fix_spec_weighted(s, weight_col="peso")
        s.partition(train_frac=0.7, seed=42)
        s.reset_to_data_loaded()
        assert s._w_train is None
        assert s._w_test is None
        assert s._w_oot is None
        assert s._w_col is None


def test_weighted_session_train_propagates_to_builder():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td))
        # Sesion ponderada
        s_w = Session(logger=_quiet_logger())
        s_w.load_dataset(str(csv_path))
        _fix_spec_weighted(s_w, weight_col="peso")
        s_w.partition(train_frac=0.7, seed=42)
        st_w = s_w.train(CrtEngine(), max_depth=4, min_child_size=5)
        # Sesion sin pesos, mismos datos y parametros
        s_0 = Session(logger=_quiet_logger())
        s_0.load_dataset(str(csv_path))
        _fix_spec_weighted(s_0)
        s_0.partition(train_frac=0.7, seed=42)
        st_0 = s_0.train(CrtEngine(), max_depth=4, min_child_size=5)
        # El fingerprint registra el modo de ponderacion
        assert st_w.tree.params_fingerprint != st_0.tree.params_fingerprint


def test_weighted_session_load_oot_uses_oot_weights():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        csv_path = _csv_weighted(td_path)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _fix_spec_weighted(s, weight_col="peso")
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        # OOT con pesos propios, distintos de los de train
        edad = np.arange(60, 80)
        seg = np.tile(["a", "b"], 10)
        y = np.ones(20, dtype=int)
        y[:5] = 0
        peso_oot = np.full(20, 3.5)
        df_oot = pd.DataFrame(
            {"edad": edad, "seg": seg, "peso": peso_oot, "default": y}
        )
        oot_path = td_path / "oot_w.csv"
        df_oot.to_csv(oot_path, index=False)
        st = s.load_oot(str(oot_path))
        assert s._w_oot is not None
        assert len(s._w_oot) == st.n_oot == 20
        # Son los pesos del OOT, no los del train
        assert math.isclose(float(s._w_oot[0]), 3.5, rel_tol=1e-9)
        assert math.isclose(float(s._w_oot.sum()), 70.0, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# 3.2.g - Ponderacion por muestra (propagacion a metricas y reportes)
# ---------------------------------------------------------------------------


def _oot_pair(td_path: Path) -> tuple[Path, Path]:
    """Devuelve (oot_con_peso, oot_sin_peso) de 20 filas enrutables."""
    edad = np.arange(60, 80)
    seg = np.tile(["a", "b"], 10)
    y = np.ones(20, dtype=int)
    y[:5] = 0
    base = {"edad": edad, "seg": seg, "default": y}
    p_w = td_path / "oot_g_w.csv"
    pd.DataFrame({**base, "peso": np.where(edad >= 70, 1.5, 1.0)}).to_csv(
        p_w, index=False
    )
    p_0 = td_path / "oot_g_0.csv"
    pd.DataFrame(base).to_csv(p_0, index=False)
    return p_w, p_0


def _session_trained(csv_path: Path, weighted: bool) -> Session:
    s = Session(logger=_quiet_logger())
    s.load_dataset(str(csv_path))
    _fix_spec_weighted(s, weight_col="peso" if weighted else None)
    s.partition(train_frac=0.7, seed=42)
    s.train(CrtEngine(), max_depth=4, min_child_size=5)
    return s


def test_weighted_session_g_evaluate_oos_propagates_weights():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td))
        s_w = _session_trained(csv_path, weighted=True)
        st_w = s_w.evaluate_oos(n_groups=5)
        assert st_w.oos_metrics is not None
        s_0 = _session_trained(csv_path, weighted=False)
        st_0 = s_0.evaluate_oos(n_groups=5)
        assert st_0.oos_metrics is not None
        # Pesos no triviales (1.0/1.2) afectan al resultado
        assert st_w.oos_metrics != st_0.oos_metrics


def test_weighted_session_g_evaluate_oot_propagates_weights():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        csv_path = _csv_weighted(td_path)
        oot_w, oot_0 = _oot_pair(td_path)
        s_w = _session_trained(csv_path, weighted=True)
        s_w.load_oot(str(oot_w))
        st_w = s_w.evaluate_oot()
        assert st_w.oot_report is not None
        assert st_w.oot_report.metrics is not None
        s_0 = _session_trained(csv_path, weighted=False)
        s_0.load_oot(str(oot_0))
        st_0 = s_0.evaluate_oot()
        assert st_0.oot_report is not None
        assert st_0.oot_report.metrics is not None
        # Las metricas OOT difieren: el flujo ponderado usa pesos
        assert st_w.oot_report.metrics != st_0.oot_report.metrics


def test_weighted_session_g_get_gains_table_propagates_weights():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td))
        s = _session_trained(csv_path, weighted=True)
        dto = s.get_gains_table(partition="oos")
        assert dto is not None
        assert "w_n" in dto["rows"][0]
        assert "w_bad" in dto["rows"][0]
        assert "w_bad_rate_cum" in dto["rows"][0]
        # Pesos no triviales: la masa total difiere del conteo de filas
        assert not math.isclose(dto["w_total"], float(dto["n_total"]),
                                rel_tol=1e-12)
        assert not math.isclose(
            dto["w_bad_rate_global"], dto["bad_rate_global"], rel_tol=1e-12
        )


def test_weighted_session_g_get_classification_matrix_propagates_weights():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_weighted(Path(td))
        s = _session_trained(csv_path, weighted=True)
        dto = s.get_classification_matrix(partition="oos")
        assert dto is not None
        for clave in ("w_tp", "w_tn", "w_fp", "w_fn",
                      "w_precision", "w_recall", "w_f1",
                      "w_bad_capture_rate"):
            assert clave in dto
        # La suma de las celdas ponderadas difiere del conteo de filas
        suma_w = dto["w_tp"] + dto["w_tn"] + dto["w_fp"] + dto["w_fn"]
        assert not math.isclose(suma_w, float(dto["n_total"]), rel_tol=1e-12)


# ---------------------------------------------------------------------------
# 3.2.h - Ponderacion por muestra
# ---------------------------------------------------------------------------


def test_weighted_session_h_evaluate_oot_with_weights():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        csv_path = _csv_weighted(td_path)
        oot_w, oot_0 = _oot_pair(td_path)
        s_w = _session_trained(csv_path, weighted=True)
        s_w.load_oot(str(oot_w))
        st_w = s_w.evaluate_oot()  # weight_oot=True (default)
        assert st_w.oot_report is not None
        assert "weighted=true,weight_col=" in st_w.event_log[-1]
        s_0 = _session_trained(csv_path, weighted=False)
        s_0.load_oot(str(oot_0))
        st_0 = s_0.evaluate_oot()
        assert st_0.oot_report is not None
        # Las metricas del modelo ponderado difieren de las del no ponderado
        assert st_w.oot_report.metrics != st_0.oot_report.metrics


def test_weighted_session_h_weight_oot_false_uses_uniform_oot_weights():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        csv_path = _csv_weighted(td_path)
        # OOT que cae en AMBAS hojas (edad 30-49 cruza el corte ~40), con
        # pesos dependientes de la hoja: el PSI ponderado difiere del
        # uniforme (con _oot_pair todo cae en una hoja y el PSI no
        # cambiaria).
        edad = np.arange(30, 50)
        seg = np.tile(["a", "b"], 10)
        y = (edad >= 40).astype(int)
        peso = np.where(edad >= 40, 3.0, 1.0)
        oot_w = td_path / "oot_h.csv"
        pd.DataFrame(
            {"edad": edad, "seg": seg, "peso": peso, "default": y}
        ).to_csv(oot_w, index=False)
        s_t = _session_trained(csv_path, weighted=True)
        s_t.load_oot(str(oot_w))
        st_t = s_t.evaluate_oot(weight_oot=True)
        s_f = _session_trained(csv_path, weighted=True)
        s_f.load_oot(str(oot_w))
        st_f = s_f.evaluate_oot(weight_oot=False)
        assert "weight_oot=false" in st_f.event_log[-1]
        assert "weight_oot=false" not in st_t.event_log[-1]
        # El PSI difiere: con weight_oot=True el OOT pesa con sus propios
        # pesos; con False usa pesos uniformes (mide solo drift del modelo)
        assert not math.isclose(
            st_t.oot_report.psi.psi, st_f.oot_report.psi.psi, rel_tol=1e-12
        )


def _csv_population(tmp: Path) -> Path:
    """CSV con columna de poblacion. y = 1_{edad >= 40}, 120 filas.
    Distribucion de la columna pop: 70 OK, 30 INDET, 20 INSUF.
    """
    n = 120
    edad = np.tile(np.arange(20, 60), 3)
    seg = np.tile(["a", "b", "c"], 40)
    y = (edad >= 40).astype(int)
    pop = np.array(["OK"] * 70 + ["INDET"] * 30 + ["INSUF"] * 20)
    df = pd.DataFrame(
        {"edad": edad, "seg": seg, "pop": pop, "default": y}
    )
    p = tmp / "mini_pop.csv"
    df.to_csv(p, index=False)
    return p


def _pop_fix_spec(s: Session, **kwargs) -> None:
    s.fix_spec(
        "default",
        predictors=["edad", "seg"],
        target_class=1,
        class_labels={0: "Bueno", 1: "Malo"},
        **kwargs,
    )


def test_population_fix_spec_rejects_missing_column():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _assert_raises(ValueError, _pop_fix_spec, s,
                       population_col="no_existe",
                       population_ok_values=("OK",))


def test_population_fix_spec_rejects_col_equals_target():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _assert_raises(ValueError, _pop_fix_spec, s,
                       population_col="default",
                       population_ok_values=("OK",))


def test_population_fix_spec_rejects_col_as_predictor():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        try:
            s.fix_spec(
                "default",
                predictors=["edad", "seg", "pop"],
                target_class=1,
                class_labels={0: "Bueno", 1: "Malo"},
                population_col="pop",
                population_ok_values=("OK",),
            )
        except ValueError as e:
            assert "predictor" in str(e)
            return
        raise AssertionError("fix_spec no lanzo ValueError")


def test_population_fix_spec_rejects_nan_in_column():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        df = pd.read_csv(csv_path)
        df.loc[5, "pop"] = np.nan
        df.to_csv(csv_path, index=False)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        try:
            _pop_fix_spec(s, population_col="pop",
                          population_ok_values=("OK",))
        except ValueError as e:
            assert "NaN" in str(e)
            return
        raise AssertionError("fix_spec no lanzo ValueError (NaN)")


def test_population_fix_spec_rejects_empty_ok_values():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _assert_raises(ValueError, _pop_fix_spec, s,
                       population_col="pop",
                       population_ok_values=())


def test_population_fix_spec_rejects_k_ok_below_2():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        # whitelist con solo "NOEXISTE": deja 0 filas -> K_ok = 0
        try:
            _pop_fix_spec(s, population_col="pop",
                          population_ok_values=("NOEXISTE",))
        except ValueError as e:
            assert "K_ok" in str(e) or "clases" in str(e)
            return
        raise AssertionError("fix_spec no lanzo ValueError (K_ok=0)")


def test_population_fix_spec_persists_col_and_ok_values():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _pop_fix_spec(s, population_col="pop",
                      population_ok_values=("OK",))
        assert s.state.population_col == "pop"
        assert s.state.population_ok_values == ("OK",)
        assert s._pop_col == "pop"
        assert s._pop_ok_values == ("OK",)


def test_population_fix_spec_logs_warning_when_class_dropped():
    """Caso: whitelist deja fuera una clase entera del target."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        # Clase 1 (y=1) es edad>=40. Filas con edad>=40 y pop=OK: 40-59
        # (20 filas). Clase 0 (y=0) es edad<40. Con OK tenemos ambas.
        # Ahora forzamos que OK solo contenga filas con y=1: creamos un
        # dataset donde pop="OK" SOLO en y=1.
        df = pd.read_csv(csv_path)
        df["pop"] = np.where(df["default"] == 1, "OK", "INDET")
        df.to_csv(csv_path, index=False)
        captura = []

        class _H(logging.Handler):
            def emit(self, r):
                captura.append(r.getMessage())

        lg = logging.getLogger("treegov.session.pop.warn")
        lg.handlers = [_H()]
        lg.propagate = False
        lg.setLevel(logging.DEBUG)
        s = Session(logger=lg)
        s.load_dataset(str(csv_path))
        try:
            _pop_fix_spec(s, population_col="pop",
                          population_ok_values=("OK",))
        except ValueError:
            # K_ok = 1 -> rechazado (correcto). Verificamos el warning.
            pass
        mensajes = "\n".join(captura)
        assert ("no aparece tras el filtro" in mensajes.lower()
                or "k_ok" in mensajes.lower())


def test_population_partition_excludes_rows_and_reports_counts():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _pop_fix_spec(s, population_col="pop",
                      population_ok_values=("OK",))
        st = s.partition(train_frac=0.7, seed=42)
        assert st.n_excluded_population == 50
        # breakdown: INSUF=20, INDET=30 (orden por count desc)
        assert st.population_breakdown == (("INDET", 30), ("INSUF", 20))


def test_population_partition_train_test_idx_relative_to_original_df():
    """Los indices siguen siendo posiciones relativas al _df original."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _pop_fix_spec(s, population_col="pop",
                      population_ok_values=("OK",))
        st = s.partition(train_frac=0.7, seed=42)
        n_total = s.state.n_rows
        assert n_total is not None
        # La suma de train + test + excluidos == n_total
        assert (len(st.train_idx) + len(st.test_idx)
                + st.n_excluded_population) == n_total
        # Todos los indices son < n_total (relativos al original)
        assert all(0 <= i < n_total for i in st.train_idx)
        assert all(0 <= i < n_total for i in st.test_idx)


def test_population_partition_breakdown_ordered_deterministically():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _pop_fix_spec(s, population_col="pop",
                      population_ok_values=("OK",))
        st = s.partition(train_frac=0.7, seed=42)
        # Verificar orden: por count descendente, empate por valor ascendente
        bs = st.population_breakdown
        for i in range(len(bs) - 1):
            c_i = bs[i][1]
            c_n = bs[i + 1][1]
            assert c_i > c_n or (c_i == c_n and bs[i][0] < bs[i + 1][0])


def test_population_partition_without_filter_c1_parity():
    """Invariante C1: sin filtro, el split es identico al pre-3.3."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        # Sesion sin filtro
        s0 = Session(logger=_quiet_logger())
        s0.load_dataset(str(csv_path))
        _pop_fix_spec(s0)
        st0 = s0.partition(train_frac=0.7, seed=42)
        # Sesion con filtro declarado pero excluyendo cero filas
        s1 = Session(logger=_quiet_logger())
        s1.load_dataset(str(csv_path))
        _pop_fix_spec(s1, population_col="pop",
                      population_ok_values=("OK", "INDET", "INSUF"))
        st1 = s1.partition(train_frac=0.7, seed=42)
        assert st0.train_idx == st1.train_idx
        assert st0.test_idx == st1.test_idx
        assert st1.n_excluded_population == 0


def test_population_load_oot_requires_column_in_oot_csv():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        csv_dev = _csv_population(tmp)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        _pop_fix_spec(s, population_col="pop",
                      population_ok_values=("OK",))
        s.partition(train_frac=0.7, seed=42)
        s.train("CRT", max_depth=4, min_child_size=5)
        # OOT sin columna pop
        df_oot = pd.DataFrame(
            {"edad": np.arange(60, 80), "seg": ["a", "b"] * 10,
             "default": np.ones(20, dtype=int)}
        )
        oot_path = tmp / "oot_sin_pop.csv"
        df_oot.to_csv(oot_path, index=False)
        try:
            s.load_oot(str(oot_path))
        except ValueError as e:
            assert "pop" in str(e)
            return
        raise AssertionError("load_oot no lanzo ValueError")


def test_population_load_oot_excludes_rows_and_reports_counts():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        csv_dev = _csv_population(tmp)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        _pop_fix_spec(s, population_col="pop",
                      population_ok_values=("OK",))
        s.partition(train_frac=0.7, seed=42)
        s.train("CRT", max_depth=4, min_child_size=5)
        # OOT con 10 OK, 6 INDET, 4 INSUF
        edad = np.arange(60, 80)
        seg = np.tile(["a", "b"], 10)
        y = np.array([0] * 5 + [1] * 15, dtype=int)
        pop = np.array(["OK"] * 10 + ["INDET"] * 6 + ["INSUF"] * 4)
        df_oot = pd.DataFrame(
            {"edad": edad, "seg": seg, "pop": pop, "default": y}
        )
        oot_path = tmp / "oot_pop.csv"
        df_oot.to_csv(oot_path, index=False)
        st = s.load_oot(str(oot_path))
        assert st.n_excluded_population_oot == 10
        assert st.population_breakdown_oot == (("INDET", 6), ("INSUF", 4))


def test_population_reset_to_data_loaded_clears_caches():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _pop_fix_spec(s, population_col="pop",
                      population_ok_values=("OK",))
        s.partition(train_frac=0.7, seed=42)
        s.reset_to_data_loaded()
        assert s._pop_col is None
        assert s._pop_ok_values is None
        assert s.state.population_col is None
        assert s.state.population_ok_values == ()


def test_describe_population_column_returns_values_with_counts():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        dto = s.describe_population_column("pop")
        assert dto["exists"] is True
        assert dto["n"] == 120
        # Orden: count desc, valor asc -> INDET(30), INSUF(20), OK(70)
        # 70 > 30, 30 > 20, orden real: OK(70), INDET(30), INSUF(20)
        vals = dto["values"]
        assert vals[0] == ("OK", 70)
        assert vals[1] == ("INDET", 30)
        assert vals[2] == ("INSUF", 20)


def test_describe_population_column_missing_column_returns_exists_false():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        dto = s.describe_population_column("no_existe")
        assert dto == {"exists": False, "n": 0, "values": ()}


def test_describe_population_column_without_dataset_raises():
    s = Session(logger=_quiet_logger())
    _assert_raises(RuntimeError, s.describe_population_column, "pop")


def test_describe_population_column_does_not_mutate_state():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        before = s.state
        s.describe_population_column("pop")
        after = s.state
        assert before is after


def test_get_oos_oot_report_renames_n_excluded_to_n_excluded_routing():
    """Fase 3.3.c: el DTO plano del OOT expone n_excluded_routing, no
    n_excluded. Y añade n_excluded_population + population_breakdown."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        csv_dev = _csv_population(tmp)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        _pop_fix_spec(s, population_col="pop",
                      population_ok_values=("OK",))
        s.partition(train_frac=0.7, seed=42)
        s.train("CRT", max_depth=4, min_child_size=5)
        edad = np.arange(60, 80)
        seg = np.tile(["a", "b"], 10)
        y = np.array([0] * 4 + [1] * 16, dtype=int)
        pop = np.array(["OK"] * 8 + ["INDET"] * 7 + ["INSUF"] * 5)
        df_oot = pd.DataFrame(
            {"edad": edad, "seg": seg, "pop": pop, "default": y}
        )
        oot_path = tmp / "oot_pop.csv"
        df_oot.to_csv(oot_path, index=False)
        s.load_oot(str(oot_path))
        s.evaluate_oot()
        dto = s.get_oos_oot_report()
        assert dto is not None
        oot = dto["oot"]
        assert "n_excluded_routing" in oot
        assert "n_excluded" not in oot
        assert oot["n_excluded_population"] == 12
        assert oot["population_breakdown"] == (("INDET", 7), ("INSUF", 5))


def test_get_oos_oot_report_includes_population_counts():
    """Fase 3.3.c: cuando el filtro de poblacion esta declarado, el DTO
    siempre expone los dos contadores y el breakdown, aunque el OOT no
    tenga filas excluidas."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        csv_dev = _csv_population(tmp)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        _pop_fix_spec(s, population_col="pop",
                      population_ok_values=("OK", "INDET", "INSUF"))
        s.partition(train_frac=0.7, seed=42)
        s.train("CRT", max_depth=4, min_child_size=5)
        edad = np.arange(60, 80)
        seg = np.tile(["a", "b"], 10)
        y = np.array([0] * 4 + [1] * 16, dtype=int)
        pop = np.full(20, "OK")
        df_oot = pd.DataFrame(
            {"edad": edad, "seg": seg, "pop": pop, "default": y}
        )
        oot_path = tmp / "oot_all_ok.csv"
        df_oot.to_csv(oot_path, index=False)
        s.load_oot(str(oot_path))
        s.evaluate_oot()
        dto = s.get_oos_oot_report()
        assert dto is not None
        oot = dto["oot"]
        assert oot["n_excluded_population"] == 0
        assert oot["population_breakdown"] == ()


def test_crt_multiclass_k3_tree_is_coherent():
    """Fase 3.4.a: arbol C&RT K=3 con clases bien separadas. Verifica
    invariantes estructurales: n_events por nodo suma n, todos los nodos
    tienen vector PD de longitud 3, y las hojas son consistentes."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_k3(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition()
        s.train("CRT", max_depth=4, min_child_size=5,
                target_type=TargetType.CATEGORICAL)
        tree = s.state.tree
        assert tree is not None
        for nd in tree.nodes:
            # n_events por nodo suma exactamente n
            assert sum(nd.n_events) == nd.n
            # vector PD coherente
            assert len(nd.pd_final) == 3
            assert len(nd.pd_jeffreys) == 3
            assert len(nd.class_labels) == 3
            assert abs(sum(nd.pd_final) - 1.0) <= 1e-12
            assert abs(sum(nd.pd_jeffreys) - 1.0) <= 1e-12


# ---------------------------------------------------------------------------
# Fase 3.5.c: desbloqueo multiclase en Session
# ---------------------------------------------------------------------------


def test_translate_y_to_internal_k3():
    """_translate_y_to_internal con target_class=2 (Fase 3.5.c).

    Orden interno canonico: (2, 0, 1) — target_class 2 primero, resto
    {0, 1} ascendente. Mapa: 2->0, 0->1, 1->2. Por tanto
    [0, 1, 2, 0, 1, 2] se traduce a [1, 2, 0, 1, 2, 0].
    No requiere entrenar: solo el estado de fix_spec.
    """
    with tempfile.TemporaryDirectory() as td:
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(_csv_k3(Path(td))))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        out = s._translate_y_to_internal(np.array([0, 1, 2, 0, 1, 2]))
        assert np.array_equal(out, np.array([1, 2, 0, 1, 2, 0]))


def test_translate_y_to_internal_k3_target_zero():
    """_translate_y_to_internal con target_class=0 es la identidad.

    Orden interno canonico: (0, 1, 2) — target_class 0 primero, resto
    {1, 2} ascendente. La traduccion coincide con la entrada.
    """
    with tempfile.TemporaryDirectory() as td:
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(_csv_k3(Path(td))))
        s.fix_spec("default", target_class=0,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        entrada = np.array([0, 1, 2, 0, 1, 2])
        out = s._translate_y_to_internal(entrada)
        assert np.array_equal(out, entrada)


def test_evaluate_oos_multiclass_works():
    """Fase 3.5.c: evaluate_oos funciona con K=3.

    Fixture _csv_k3 (clases seg-driven, separacion perfecta): CHAID
    corta por seg1/seg2 y el OOS queda perfectamente separado, con las
    tres clases presentes en test (12 por clase de 36). auc = gini = 1.
    """
    with tempfile.TemporaryDirectory() as td:
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(_csv_k3(Path(td))))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        st_part = s.partition(train_frac=0.7, seed=42)
        s.train("CHAID", max_depth=3, min_child_size=5, target_type=TargetType.CATEGORICAL)
        st = s.evaluate_oos(n_groups=3)
        m = st.oos_metrics
        assert m is not None
        assert m.n_test == len(st_part.test_idx)
        assert m.auc is not None and m.gini is not None
        assert m.ks is not None and m.pr_auc is not None
        # separacion perfecta del fixture
        assert m.auc == 1.0 and m.gini == 1.0


def test_evaluate_oos_k2_parity():
    """Invariante no negociable: K=2 bit a bit igual al pre-3.5.c.

    Mismo fixture y parametros que test_evaluate_oos_e2e_valores_exactos:
    auc = gini = ks = 1; brier = (0.5/43)^2; hl_groups=2, hl_df=2, hl_stat = 36/85.
    """
    with tempfile.TemporaryDirectory() as td:
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(_csv(Path(td))))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train("CRT", max_depth=4, min_child_size=5)
        st = s.evaluate_oos(n_groups=3)
        m = st.oos_metrics
        assert m is not None
        assert m.auc == 1.0 and m.gini == 1.0 and m.ks == 1.0
        esperado_bs = (0.5 / 43.0) ** 2
        assert math.isclose(m.brier, esperado_bs, rel_tol=1e-12)
        assert m.hl_groups == 2 and m.hl_df == 2
        assert math.isclose(m.hl_stat, 36.0 / 85.0, rel_tol=1e-12)


def test_evaluate_oot_multiclass_works():
    """Fase 3.5.c: evaluate_oot funciona con K=3 y Gini Drop multiclase.

    Fixture _csv_k3 como dev y como OOT (dos copias del mismo CSV; el
    fixture no tiene senal temporal, es solo plumbing). Misma
    distribucion en ambas cohortes: metricas computables, PSI ~0.
    El drop usa el Gini multiclase (Hand & Till) con la formula intacta.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        csv_dev = _csv_k3(tmp)
        csv_oot = tmp / "oot_k3.csv"
        pd.read_csv(csv_dev).to_csv(csv_oot, index=False)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition(train_frac=0.7, seed=42)
        s.train("CHAID", max_depth=3, min_child_size=5, target_type=TargetType.CATEGORICAL)
        s.load_oot(str(csv_oot))
        st = s.evaluate_oot()
        r = st.oot_report
        assert r is not None
        assert r.metrics is not None
        assert r.metrics.auc is not None
        assert isinstance(r.drop.gini_oot, float)
        assert r.drop.alert_oot in ("NONE", "WARNING", "CRITICAL")
        assert r.psi.flag in ("STABLE", "MODERATE", "UNSTABLE", "UNDETERMINED")


def test_get_classification_matrix_multiclass_works():
    """Fase 3.5.c: get_classification_matrix funciona con K=3.

    Fixture _csv_k3 separable: matriz 3x3, accuracy = 1 (separacion
    perfecta), 3 clases en n_per_class, y los campos binarios heredados
    (clase 0 = positivo) suman n_total.
    """
    with tempfile.TemporaryDirectory() as td:
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(_csv_k3(Path(td))))
        s.fix_spec("default", target_class=2,
                   class_labels={0: "bajo", 1: "medio", 2: "alto"})
        s.partition(train_frac=0.7, seed=42)
        s.train("CHAID", max_depth=3, min_child_size=5, target_type=TargetType.CATEGORICAL)
        dto = s.get_classification_matrix(partition="oos")
        assert dto is not None
        assert isinstance(dto["confusion_matrix"], tuple)
        assert len(dto["confusion_matrix"]) == 3
        assert all(len(fila) == 3 for fila in dto["confusion_matrix"])
        assert dto["accuracy"] is not None
        assert dto["accuracy"] == 1.0
        assert len(dto["n_per_class"]) == 3
        assert (dto["tp"] + dto["tn"] + dto["fp"] + dto["fn"]
                ) == dto["n_total"]


def test_get_classification_matrix_k2_parity():
    """K=2: la matriz binaria queda bit a bit igual al pre-3.5.c.

    Fixture _csv (separacion perfecta): n_test=36, 18 bads y 18 goods,
    todos bien clasificados con threshold=0.5 (pd hojas 0.5/43 y
    42.5/43). accuracy = 1. Los campos nuevos 3.5.b quedan vacios.
    """
    with tempfile.TemporaryDirectory() as td:
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(_csv(Path(td))))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train("CRT", max_depth=4, min_child_size=5)
        dto = s.get_classification_matrix(partition="oos", threshold=0.5)
        assert dto is not None
        assert dto["tp"] == 18 and dto["tn"] == 18
        assert dto["fp"] == 0 and dto["fn"] == 0
        assert dto["accuracy"] == 1.0
        assert dto["confusion_matrix"] == ()
        assert dto["n_per_class"] == ()


def test_get_classification_matrix_multiclass_threshold_ignored():
    """K=3: el threshold se ignora (asignacion argmax); resultado identico.

    Dos sesiones identicas salvo threshold=0.99 vs 0.01: los DTOs son
    iguales campo a campo (excluyendo el propio threshold, que se
    registra como NaN en ambos para trazabilidad).
    """
    def _dto_con_threshold(thr):
        with tempfile.TemporaryDirectory() as td:
            s = Session(logger=_quiet_logger())
            s.load_dataset(str(_csv_k3(Path(td))))
            s.fix_spec("default", target_class=2,
                       class_labels={0: "bajo", 1: "medio", 2: "alto"})
            s.partition(train_frac=0.7, seed=42)
            s.train("CHAID", max_depth=3, min_child_size=5, target_type=TargetType.CATEGORICAL)
            return s.get_classification_matrix(partition="oos", threshold=thr)

    d1 = _dto_con_threshold(0.99)
    d2 = _dto_con_threshold(0.01)
    assert d1 is not None and d2 is not None
    assert math.isnan(d1["threshold"]) and math.isnan(d2["threshold"])
    resto1 = {k: v for k, v in d1.items() if k != "threshold"}
    resto2 = {k: v for k, v in d2.items() if k != "threshold"}
    assert resto1 == resto2


# ---------------------------------------------------------------------------
# Fase 3.11.b.1: get_data_preview (backend del Data Viewer, diseno D3)
# ---------------------------------------------------------------------------


def test_get_data_preview_without_dataset():
    """Sin load_dataset: dict vacio (divergencia consciente con describe_*,
    que lanzan RuntimeError; el visor necesita un estado vacio simple)."""
    s = Session(logger=_quiet_logger())
    dto = s.get_data_preview()
    assert dto == {"columns": [], "rows": [], "n_total": 0,
                   "truncated": False}


def test_get_data_preview_truncated():
    """120 filas con n_rows=50: n_total=120, len(rows)=50, truncated=True."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        dto = s.get_data_preview(n_rows=50)
        assert dto["n_total"] == 120
        assert len(dto["rows"]) == 50
        assert dto["truncated"] is True


def test_get_data_preview_native_types():
    """Toda celda es tipo nativo Python: cero np.int64 / np.nan en rows.

    El fixture _csv tiene edad (int), seg (str) y default (int): se
    verifican los tipos concretos de la primera fila y el invariante
    global type(val) in (int, float, str, bool, NoneType).
    """
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        dto = s.get_data_preview(n_rows=50)
        assert dto["columns"] == ["edad", "seg", "default"]
        for row in dto["rows"]:
            assert isinstance(row, tuple)
            for val in row:
                assert type(val) in (int, float, str, bool, type(None))
        primera = dto["rows"][0]
        assert type(primera[0]) is int      # edad
        assert type(primera[1]) is str      # seg
        assert type(primera[2]) is int      # default


def test_get_data_preview_no_truncation():
    """n_rows=200 > 120 filas del fixture: truncated=False, rows completo."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        dto = s.get_data_preview(n_rows=200)
        assert dto["n_total"] == 120
        assert len(dto["rows"]) == 120
        assert dto["truncated"] is False


def test_get_univariate_trees():
    """Fase 3.11.c.1: un arbol por predictor, con metricas y puntos de corte.

    El fixture _csv tiene senal real en edad (default = 1_{edad >= 40}),
    asi que el Gini univariado de edad debe ser alto y tener cortes; seg
    es nominal sin senal (metricas bajas o cero, sin exigencia de cortes).
    """
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", predictors=["edad", "seg"], target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)

        trees = s.get_univariate_trees(max_depth=2)
        assert len(trees) == 2
        assert trees[0]["predictor"] == "edad"
        assert trees[1]["predictor"] == "seg"
        # El fixture tiene senal real en edad (>=40), asi que el Gini
        # debe ser alto.
        assert trees[0]["gini"] > 0.5
        assert len(trees[0]["cut_points"]) > 0
        assert isinstance(trees[0]["cut_points"][0], tuple)


def test_fix_spec_with_cost_matrix():
    """Fase 3.11.c.3: fix_spec almacena la matriz N x N como tupla de tuplas.

    La matriz es inmutable y NO entra en params_fingerprint en esta fase
    (design doc §3.2); se valida antes de la transicion (cuadrada,
    diagonal 0, valores finitos >= 0).
    """
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        mat = ((0.0, 5.0), (1.0, 0.0))
        st = s.fix_spec("default", predictors=["edad", "seg"], target_class=1,
                        class_labels={0: "Bueno", 1: "Malo"},
                        cost_matrix=mat)
        assert st.cost_matrix == mat
        assert isinstance(st.cost_matrix, tuple)
        assert all(isinstance(fila, tuple) for fila in st.cost_matrix)

        # Default: sin matriz -> ()
        s2 = Session(logger=_quiet_logger())
        s2.load_dataset(str(csv_path))
        st2 = s2.fix_spec("default", predictors=["edad"], target_class=1,
                          class_labels={0: "Bueno", 1: "Malo"})
        assert st2.cost_matrix == ()

        # Endurecimiento: diagonal != 0 y valores negativos se rechazan
        s3 = Session(logger=_quiet_logger())
        s3.load_dataset(str(csv_path))
        _assert_raises(
            ValueError, s3.fix_spec, "default", predictors=["edad"],
            target_class=1, class_labels={0: "Bueno", 1: "Malo"},
            cost_matrix=((1.0, 0.0), (0.0, 0.0)),
        )
        s4 = Session(logger=_quiet_logger())
        s4.load_dataset(str(csv_path))
        _assert_raises(
            ValueError, s4.fix_spec, "default", predictors=["edad"],
            target_class=1, class_labels={0: "Bueno", 1: "Malo"},
            cost_matrix=((0.0, -2.0), (0.0, 0.0)),
        )


def test_intervene_prune():
    """Fase 3.11.d.1: intervene_node("prune_branch") sobre la raiz.

    Podar la raiz deja un arbol de un solo nodo (hoja), con fingerprint
    sufijado "-i1" y un registro en el Manual Override Log.
    """
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)

        tree_original = s.state.tree
        assert len(tree_original.nodes) > 1
        fp_original = tree_original.params_fingerprint

        # Encontrar un nodo interno (raiz)
        root_id = tree_original.root_id

        # Intervenir
        st = s.intervene_node(root_id, "prune_branch")
        tree_nuevo = st.tree

        assert len(tree_nuevo.nodes) == 1  # Solo queda la raiz
        assert tree_nuevo.nodes[0].is_leaf
        assert tree_nuevo.params_fingerprint == f"{fp_original}-i1"
        assert len(st.manual_overrides) == 1
        assert st.manual_overrides[0][1] == root_id
        assert st.manual_overrides[0][2] == "prune_branch"


def _cv_session(tmp: Path, k: int = 3) -> Session:
    csv_path = _csv(tmp)
    s = Session(logger=_quiet_logger())
    s.load_dataset(str(csv_path))
    s.fix_spec("default", target_class=1,
               class_labels={0: "Bueno", 1: "Malo"})
    s.partition(seed=42, scheme="cv", k=k)
    return s


def test_partition_cv_mode():
    with tempfile.TemporaryDirectory() as td:
        s = _cv_session(Path(td), k=3)
        st = s.state
        assert s._X_train is not None and len(s._X_train) == 120
        assert s._X_test is None and s._y_test is None
        assert st.validation_scheme == "cv"
        assert st.cv_k == 3
        assert len(st.cv_folds) == 3
        assert st.train_idx is None and st.test_idx is None


def test_partition_cv_preserves_holdout_fingerprints():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        fingerprints = []
        for explicit in (False, True):
            s = Session(logger=_quiet_logger())
            s.load_dataset(str(csv_path))
            s.fix_spec("default", target_class=1,
                       class_labels={0: "Bueno", 1: "Malo"})
            kwargs = {"scheme": "holdout"} if explicit else {}
            s.partition(train_frac=0.7, seed=42, **kwargs)
            s.train(CrtEngine(), max_depth=4, min_child_size=5)
            assert s.state.tree is not None
            fingerprints.append(s.state.tree.params_fingerprint)
        assert fingerprints[0] == fingerprints[1]


def test_train_cv_mode_uses_100pct_data():
    with tempfile.TemporaryDirectory() as td:
        s = _cv_session(Path(td), k=3)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        assert s.state.tree is not None
        root = s.state.tree.nodes[0]
        assert root.n == 120
        assert root.n_events == (60, 60)


def test_evaluate_oos_cv_returns_dto_with_mean_std():
    with tempfile.TemporaryDirectory() as td:
        s = _cv_session(Path(td), k=3)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        report = s.evaluate_oos()
        assert isinstance(report, dict)
        assert report["scheme"] == "cv" and report["k"] == 3
        assert len(report["metrics_per_fold"]) == 3
        for key in ("auc", "gini", "ks"):
            assert key in report["metrics_mean"]
            assert key in report["metrics_std"]
        assert s.state.oos_metrics is None


def test_fingerprint_differs_between_holdout_and_cv():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        s_cv = _cv_session(tmp, k=3)
        s_cv.train(CrtEngine(), max_depth=4, min_child_size=5)
        assert s_cv.state.tree is not None

        s_holdout = Session(logger=_quiet_logger())
        s_holdout.load_dataset(str(tmp / "mini.csv"))
        s_holdout.fix_spec("default", target_class=1,
                           class_labels={0: "Bueno", 1: "Malo"})
        s_holdout.partition(train_frac=0.7, seed=42)
        s_holdout.train(CrtEngine(), max_depth=4, min_child_size=5)
        assert s_holdout.state.tree is not None
        assert (
            s_cv.state.tree.params_fingerprint
            != s_holdout.state.tree.params_fingerprint
        )


def test_get_cv_report_returns_none_without_cv():
    s = Session(logger=_quiet_logger())
    assert s.get_cv_report() is None


def test_get_cv_report_returns_dto_after_evaluate():
    with tempfile.TemporaryDirectory() as td:
        s = _cv_session(Path(td), k=3)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        expected = s.evaluate_oos()
        report = s.get_cv_report()
        assert isinstance(report, dict)
        assert report == expected


# ---------------------------------------------------------------------------
# Fase 3.12.a: Session.get_rules (fachada de los exportadores)
# ---------------------------------------------------------------------------


def _csv_deep(tmp: Path) -> Path:
    """480 filas con y = 1_{edad >= 40 AND importe >= 50}.

    La interaccion fuerza un arbol de profundidad 2: la raiz parte por
    ``importe`` y un hijo INTERNO parte por ``edad``. Ese hijo interno es
    el nodo que usan las pruebas de filtrado por nodo. Fixture
    determinista, sin RNG: 40 edades x 4 niveles de importe x 3 repes.
    """
    edad = np.repeat(np.arange(20, 60), 12)
    importe = np.tile(np.repeat([10, 30, 60, 90], 3), 40)
    y = ((edad >= 40) & (importe >= 50)).astype(int)
    df = pd.DataFrame({"edad": edad, "importe": importe, "default": y})
    p = tmp / "deep.csv"
    df.to_csv(p, index=False)
    return p


def _deep_trained(tmp: Path) -> Session:
    s = Session(logger=_quiet_logger())
    s.load_dataset(str(_csv_deep(tmp)))
    s.fix_spec("default", target_class=1,
               class_labels={0: "Bueno", 1: "Malo"})
    s.partition(train_frac=0.7, seed=42)
    s.train(CrtEngine(), max_depth=4, min_child_size=5)
    assert s.state.tree is not None
    return s


def test_get_rules_returns_none_without_model():
    s = Session(logger=_quiet_logger())
    assert s.get_rules() is None
    assert s.get_rules("markdown") is None
    assert s.get_rules("sql") is None
    assert s.get_rules("python") is None


def test_get_rules_without_node_matches_exporters():
    with tempfile.TemporaryDirectory() as td:
        s = _deep_trained(Path(td))
        assert s.get_rules() == s.export_to_markdown()
        assert s.get_rules("markdown") == s.export_to_markdown()
        assert s.get_rules("sql") == s.export_to_sql()
        assert s.get_rules("python") == s.export_to_python()


def test_get_rules_node_filter_is_shorter_and_distinct():
    with tempfile.TemporaryDirectory() as td:
        s = _deep_trained(Path(td))
        tree = s.state.tree
        assert tree is not None
        internos = [
            nd for nd in tree.nodes
            if not nd.is_leaf and nd.node_id != tree.root_id
        ]
        assert internos, "el fixture debe producir un nodo interno no raiz"
        nid = internos[0].node_id

        for fmt in ("markdown", "sql", "python"):
            full = s.get_rules(fmt)
            sub = s.get_rules(fmt, node_id=nid)
            assert full is not None and sub is not None
            assert sub != full
            assert len(sub) < len(full)

        md_sub = s.get_rules("markdown", node_id=nid)
        assert md_sub is not None
        assert f"- **Node {nid}** (Split on" in md_sub
        assert "- **Node 0**" not in md_sub


def test_get_rules_forwards_unseen_policy():
    with tempfile.TemporaryDirectory() as td:
        s = _deep_trained(Path(td))
        for fmt in ("markdown", "sql", "python"):
            assert s.get_rules(fmt, unseen_policy="error") != s.get_rules(fmt)


def test_get_rules_invalid_format_raises():
    with tempfile.TemporaryDirectory() as td:
        s = _deep_trained(Path(td))
        _assert_raises(ValueError, s.get_rules, "xml")
        _assert_raises(KeyError, s.get_rules, "markdown", 99)


# ---------------------------------------------------------------------------
# Fase 3.12.b: Session.get_summary (acta del modelo)
# ---------------------------------------------------------------------------


def _assert_native_summary(obj, path="summary"):
    """Falla si el DTO contiene cualquier escalar/array de numpy o pandas."""
    assert not isinstance(
        obj, (np.generic, np.ndarray, pd.DataFrame, pd.Series)
    ), f"{path} es {type(obj)}"
    assert not type(obj).__module__.startswith(("numpy", "pandas")), (
        f"{path} es {type(obj)}"
    )
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert isinstance(k, str), f"{path}: clave no str {k!r}"
            _assert_native_summary(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_native_summary(v, f"{path}[{i}]")


def _summary_trained(tmp: Path, **train_kwargs) -> Session:
    s = Session(logger=_quiet_logger())
    s.load_dataset(str(_csv(tmp)))
    s.fix_spec("default", target_class=1,
               class_labels={0: "Bueno", 1: "Malo"})
    s.partition(train_frac=0.7, seed=42)
    params = {"max_depth": 4, "min_child_size": 5}
    params.update(train_kwargs)
    s.train(CrtEngine(), **params)
    return s


def test_get_summary_returns_none_without_tree():
    s = Session(logger=_quiet_logger())
    assert s.get_summary() is None


def test_get_summary_structure_matches_contract():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = _summary_trained(Path(td))
        s.evaluate_oos(n_groups=3)
        summary = s.get_summary()
        st = s.state
        tree = st.tree
        assert isinstance(summary, dict)
        assert tree is not None

        assert set(summary) == {
            "model", "dataset", "partition", "governance",
            "validation", "manual_overrides", "event_log",
        }

        model = summary["model"]
        assert set(model) == {
            "method", "fingerprint", "n_nodes", "n_terminal",
            "max_depth", "class_labels", "target_class", "governance_mode",
        }
        assert model["method"] == "CRT"
        assert model["fingerprint"] == tree.params_fingerprint
        assert model["n_nodes"] == len(tree.nodes)
        assert model["n_terminal"] == sum(
            1 for nd in tree.nodes if nd.is_leaf
        )
        assert model["max_depth"] == max(nd.depth for nd in tree.nodes)
        assert model["class_labels"] == list(tree.class_labels)
        assert model["target_class"] == 1
        assert model["governance_mode"] == "BANKING"

        dataset = summary["dataset"]
        assert set(dataset) == {
            "path", "n_rows", "n_cols", "target", "predictors",
            "weights_col", "population_col", "population_ok_values",
            "cost_matrix",
        }
        assert dataset["path"] == str(csv_path)
        assert dataset["n_rows"] == 120
        assert dataset["n_cols"] == 3
        assert dataset["target"] == "default"
        assert dataset["predictors"] == ["edad", "seg"]
        assert dataset["weights_col"] is None
        assert dataset["population_col"] is None
        assert dataset["population_ok_values"] == []
        assert dataset["cost_matrix"] == []

        partition = summary["partition"]
        assert set(partition) == {
            "scheme", "train_frac", "seed", "cv_k", "n_train",
            "n_test", "n_oot", "n_excluded_population",
        }
        assert partition["scheme"] == "holdout"
        assert partition["train_frac"] == 0.7
        assert partition["seed"] == 42
        assert partition["cv_k"] is None
        assert partition["n_train"] == 84
        assert partition["n_test"] == 36
        assert partition["n_oot"] is None
        assert partition["n_excluded_population"] == 0

        governance = summary["governance"]
        assert set(governance) == {
            "apply_jeffreys", "pd_floor", "min_child_size",
            "min_child_weight", "max_depth_param",
        }
        assert governance["apply_jeffreys"] is True
        assert governance["pd_floor"] == 0.0005
        assert governance["min_child_size"] == 5
        assert governance["min_child_weight"] is None
        assert governance["max_depth_param"] == 4

        report = s.get_oos_oot_report()
        assert report is not None
        validation = summary["validation"]
        assert set(validation) == {"oos_metrics", "oot_report", "cv_report"}
        assert validation["oos_metrics"] == report["oos"]
        assert validation["oot_report"] is None
        assert validation["cv_report"] is None

        assert summary["manual_overrides"] == list(st.manual_overrides)
        assert summary["manual_overrides"] == []
        assert summary["event_log"] == list(st.event_log)
        assert summary["event_log"][-1].startswith("evaluate_oos:")


def test_get_summary_research_mode_has_no_pd_floor():
    with tempfile.TemporaryDirectory() as td:
        s = _summary_trained(
            Path(td), apply_jeffreys=False, pd_floor=None
        )
        summary = s.get_summary()
        assert summary is not None
        assert summary["model"]["governance_mode"] == "RESEARCH"
        assert summary["governance"]["apply_jeffreys"] is False
        assert summary["governance"]["pd_floor"] is None


def test_get_summary_returns_only_native_types():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(_csv_seg_driven(tmp)))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        s.evaluate_oos(n_groups=3)
        s.load_oot(str(_csv_oot(tmp, temporal=False, con_nueva_cat=True)))
        s.evaluate_oot(n_groups=3)

        summary = s.get_summary()
        assert summary is not None
        assert summary["validation"]["oos_metrics"] is not None
        assert summary["validation"]["oot_report"] is not None
        _assert_native_summary(summary)

        s_cv = _cv_session(tmp, k=3)
        s_cv.train(CrtEngine(), max_depth=4, min_child_size=5)
        s_cv.evaluate_oos(n_groups=3)
        summary_cv = s_cv.get_summary()
        assert summary_cv is not None
        assert summary_cv["partition"]["scheme"] == "cv"
        assert summary_cv["partition"]["n_train"] == 120
        assert summary_cv["partition"]["n_test"] == 0
        assert summary_cv["validation"]["cv_report"] is not None
        _assert_native_summary(summary_cv)


# ---------------------------------------------------------------------------
# Fase 3.12.c: Session.get_node_cases (casos crudos por nodo)
# ---------------------------------------------------------------------------


def _node_cases_trained(tmp: Path) -> Session:
    s = Session(logger=_quiet_logger())
    s.load_dataset(str(_csv(tmp)))
    s.fix_spec("default", target_class=1,
               class_labels={0: "Bueno", 1: "Malo"})
    s.partition(train_frac=0.7, seed=42)
    s.train(CrtEngine(), max_depth=4, min_child_size=5)
    assert s.state.tree is not None
    return s


def _csv_nan(tmp: Path) -> Path:
    """120 filas con y = 1_{edad >= 40} y 12 edades NaN (una de cada 10).

    El target se calcula ANTES de enmascarar la edad: las filas con NaN
    conservan su clase, de modo que el arbol se entrena igual y solo
    cambia la representacion CRUDA de la celda (NaN -> None).
    """
    base = np.tile(np.arange(20, 60), 3)
    edad = base.astype(float)
    edad[::10] = np.nan
    seg = np.tile(["a", "b", "c"], 40)
    df = pd.DataFrame(
        {"edad": edad, "seg": seg, "default": (base >= 40).astype(int)}
    )
    p = tmp / "mini_nan.csv"
    df.to_csv(p, index=False)
    return p


def test_get_node_cases_requires_trained_model():
    s = Session(logger=_quiet_logger())
    _assert_raises(ValueError, s.get_node_cases, 0)


def test_get_node_cases_rejects_unknown_node_and_partition():
    with tempfile.TemporaryDirectory() as td:
        s = _node_cases_trained(Path(td))
        tree = s.state.tree
        assert tree is not None
        _assert_raises(ValueError, s.get_node_cases, len(tree.nodes))
        _assert_raises(ValueError, s.get_node_cases, -1)
        _assert_raises(
            ValueError, s.get_node_cases, 0, partition="validation"
        )


def test_get_node_cases_root_matches_partition_total():
    with tempfile.TemporaryDirectory() as td:
        s = _node_cases_trained(Path(td))
        st = s.state
        assert st.tree is not None
        root = st.tree.root_id

        train = s.get_node_cases(root, partition="train", n_rows=10**6)
        assert set(train) == {"columns", "rows", "n_total", "truncated"}
        assert train["columns"] == ["edad", "seg", "default"]
        assert train["n_total"] == len(st.train_idx or ())
        assert len(train["rows"]) == train["n_total"]
        assert train["truncated"] is False

        oos = s.get_node_cases(root, partition="oos", n_rows=10**6)
        assert oos["n_total"] == len(st.test_idx or ())
        assert oos["truncated"] is False

        todos = s.get_node_cases(root, partition="all", n_rows=10**6)
        assert todos["n_total"] == st.n_rows
        assert len(todos["rows"]) == st.n_rows
        assert todos["truncated"] is False


def test_get_node_cases_leaf_sum_matches_partition():
    with tempfile.TemporaryDirectory() as td:
        s = _node_cases_trained(Path(td))
        tree = s.state.tree
        st = s.state
        assert tree is not None
        hojas = [nd.node_id for nd in tree.nodes if nd.is_leaf]
        assert len(hojas) >= 2
        total = sum(
            s.get_node_cases(nid, n_rows=10**6)["n_total"] for nid in hojas
        )
        assert total == len(st.train_idx or ())
        for nid in hojas:
            dto = s.get_node_cases(nid, n_rows=10**6)
            assert dto["n_total"] == tree.nodes[nid].n


def test_get_node_cases_internal_node_matches_children_sum():
    with tempfile.TemporaryDirectory() as td:
        s = _deep_trained(Path(td))
        tree = s.state.tree
        assert tree is not None
        internos = [nd for nd in tree.nodes if not nd.is_leaf]
        assert internos
        assert any(nd.node_id != tree.root_id for nd in internos), (
            "el fixture debe tener un nodo interno que no sea la raiz"
        )
        for nd in internos:
            padre = s.get_node_cases(nd.node_id, n_rows=10**6)["n_total"]
            hijos = sum(
                s.get_node_cases(cid, n_rows=10**6)["n_total"]
                for cid in nd.child_ids
            )
            assert padre == hijos


def test_get_node_cases_returns_native_types_and_truncates():
    with tempfile.TemporaryDirectory() as td:
        s = _node_cases_trained(Path(td))
        assert s.state.tree is not None
        root = s.state.tree.root_id

        dto = s.get_node_cases(root, n_rows=5)
        assert set(dto) == {"columns", "rows", "n_total", "truncated"}
        assert type(dto["n_total"]) is int
        assert type(dto["truncated"]) is bool
        assert dto["n_total"] == len(s.state.train_idx or ())
        assert dto["truncated"] is True
        assert len(dto["rows"]) == 5
        assert all(type(c) is str for c in dto["columns"])
        assert all(isinstance(r, tuple) for r in dto["rows"])
        _assert_native_summary(dto)


def test_get_node_cases_nan_raw_cell_becomes_none():
    with tempfile.TemporaryDirectory() as td:
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(_csv_nan(Path(td))))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        st = s.state
        assert st.tree is not None

        dto = s.get_node_cases(
            st.tree.root_id, partition="train", n_rows=10**6
        )
        assert dto["n_total"] == len(st.train_idx or ())
        assert len(dto["rows"]) == dto["n_total"]
        pos = dto["columns"].index("edad")
        assert any(fila[pos] is None for fila in dto["rows"]), (
            "el fixture debe dejar al menos un NaN crudo en train"
        )
        assert all(
            not (isinstance(fila[pos], float) and math.isnan(fila[pos]))
            for fila in dto["rows"]
        )
        _assert_native_summary(dto)


def test_get_node_cases_oot_before_and_after_load():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(_csv_seg_driven(tmp)))
        s.fix_spec("default", target_class=1,
                   class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        st = s.state
        assert st.tree is not None
        root = st.tree.root_id

        antes = s.get_node_cases(root, partition="oot")
        assert antes == {
            "columns": ["edad", "seg", "default"],
            "rows": [], "n_total": 0, "truncated": False,
        }

        s.load_oot(str(_csv_oot(tmp, temporal=False, con_nueva_cat=True)))
        despues = s.get_node_cases(root, partition="oot", n_rows=10**6)
        assert despues["n_total"] == 40  # 60 filas OOT - 20 con 'd'
        assert len(despues["rows"]) == 40
        pos_seg = despues["columns"].index("seg")
        assert all(fila[pos_seg] in ("a", "b") for fila in despues["rows"])
        hojas = [nd.node_id for nd in s.state.tree.nodes if nd.is_leaf]
        assert sum(
            s.get_node_cases(nid, partition="oot", n_rows=10**6)["n_total"]
            for nid in hojas
        ) == 40
        _assert_native_summary(despues)


def test_get_node_cases_cv_train_and_empty_oos():
    with tempfile.TemporaryDirectory() as td:
        s = _cv_session(Path(td), k=3)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        st = s.state
        assert st.tree is not None
        root = st.tree.root_id

        train = s.get_node_cases(root, partition="train", n_rows=10**6)
        assert train["n_total"] == st.n_rows
        hojas = [nd.node_id for nd in st.tree.nodes if nd.is_leaf]
        assert sum(
            s.get_node_cases(nid, partition="train", n_rows=10**6)["n_total"]
            for nid in hojas
        ) == st.n_rows

        oos = s.get_node_cases(root, partition="oos")
        assert oos == {
            "columns": ["edad", "seg", "default"],
            "rows": [], "n_total": 0, "truncated": False,
        }


def test_get_node_cases_cv_respects_population_filter():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_population(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _pop_fix_spec(s, population_col="pop",
                      population_ok_values=("OK",))
        s.partition(seed=42, scheme="cv", k=3)
        s.train(CrtEngine(), max_depth=4, min_child_size=5)
        st = s.state
        assert st.tree is not None

        dto = s.get_node_cases(
            st.tree.root_id, partition="train", n_rows=10**6
        )
        assert dto["n_total"] == 70  # solo las filas OK de la poblacion
        assert len(dto["rows"]) == 70
        pos_pop = dto["columns"].index("pop")
        assert all(fila[pos_pop] == "OK" for fila in dto["rows"])
        hojas = [nd.node_id for nd in st.tree.nodes if nd.is_leaf]
        assert sum(
            s.get_node_cases(nid, partition="train", n_rows=10**6)["n_total"]
            for nid in hojas
        ) == 70


# ---------------------------------------------------------------------------
# Bloque 2B (CRIT-05, CRIT-03, CRIT-06, CRIT-07)
# ---------------------------------------------------------------------------


def test_fix_spec_excludes_weight_and_population_inferred_and_rejects_explicit():
    """CRIT-05: spec inferido excluye weight_col/population_col; explicito falla."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        edad = np.tile(np.arange(20, 60), 3)
        seg = np.tile(["a", "b", "c"], 40)
        y = (edad >= 40).astype(int)
        w = np.full(len(edad), 1.5, dtype=float)
        pop = np.array(["OK"] * 90 + ["INDET"] * 30)
        csv_path = tmp / "wpop.csv"
        pd.DataFrame({
            "edad": edad, "seg": seg, "w": w, "pop": pop, "default": y,
        }).to_csv(csv_path, index=False)

        # Inferido (spec=None, predictors=None): excluye w y pop automaticamente
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        st = s.fix_spec(
            "default",
            target_class=1,
            class_labels={0: "Bueno", 1: "Malo"},
            weight_col="w",
            population_col="pop",
            population_ok_values=("OK",),
        )
        spec_keys = set(dict(st.spec or ()).keys())
        assert "w" not in spec_keys
        assert "pop" not in spec_keys
        assert spec_keys == {"edad", "seg"}

        # Explicito con weight_col en spec -> ValueError
        s2 = Session(logger=_quiet_logger())
        s2.load_dataset(str(csv_path))
        _assert_raises(
            ValueError,
            s2.fix_spec,
            "default",
            spec={"edad": PredictorType.CONTINUOUS, "w": PredictorType.CONTINUOUS},
            target_class=1,
            class_labels={0: "Bueno", 1: "Malo"},
            weight_col="w",
        )
        assert s2.state.state is FlowState.DATA_LOADED

        # Explicito con population_col en spec -> ValueError
        _assert_raises(
            ValueError,
            s2.fix_spec,
            "default",
            spec={"edad": PredictorType.CONTINUOUS, "pop": PredictorType.NOMINAL},
            target_class=1,
            class_labels={0: "Bueno", 1: "Malo"},
            population_col="pop",
            population_ok_values=("OK",),
        )
        assert s2.state.state is FlowState.DATA_LOADED

        # weight_col == population_col -> ValueError
        _assert_raises(
            ValueError,
            s2.fix_spec,
            "default",
            target_class=1,
            class_labels={0: "Bueno", 1: "Malo"},
            weight_col="w",
            population_col="w",
            population_ok_values=("1.5",),
        )


def test_fix_spec_rejects_inf_weight_and_describe_counts_nonfinite():
    """CRIT-05: +inf en weight_col rechazado en fix_spec y contado en describe."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        edad = np.tile(np.arange(20, 60), 3)
        y = (edad >= 40).astype(int)
        w = np.ones(len(edad), dtype=float)
        w[0] = float("inf")
        w[1] = float("-inf")
        csv_path = tmp / "inf_w.csv"
        pd.DataFrame({"edad": edad, "w": w, "default": y}).to_csv(
            csv_path, index=False
        )

        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        diag = s.describe_weight_column("w")
        assert diag["exists"] is True
        assert diag["n_nonpositive"] == 2
        _assert_raises(
            ValueError,
            s.fix_spec,
            "default",
            target_class=1,
            class_labels={0: "Bueno", 1: "Malo"},
            weight_col="w",
        )
        assert s.state.state is FlowState.DATA_LOADED
        assert s._w_col is None


def test_fix_spec_atomicity_on_invalid_cost_matrix():
    """CRIT-05: fallo en cost_matrix no deja mutados _w_col/_pop_col/_pop_ok_values."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        edad = np.tile(np.arange(20, 60), 3)
        y = (edad >= 40).astype(int)
        w = np.ones(len(edad), dtype=float)
        pop = np.array(["OK"] * 90 + ["INDET"] * 30)
        csv_path = tmp / "atomic_cost.csv"
        pd.DataFrame({
            "edad": edad, "w": w, "pop": pop, "default": y,
        }).to_csv(csv_path, index=False)

        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        _assert_raises(
            ValueError,
            s.fix_spec,
            "default",
            target_class=1,
            class_labels={0: "Bueno", 1: "Malo"},
            weight_col="w",
            population_col="pop",
            population_ok_values=("OK",),
            cost_matrix=((1.0, 2.0), (3.0, 0.0)),  # diagonal != 0
        )
        assert s.state.state is FlowState.DATA_LOADED
        assert s._w_col is None
        assert s._pop_col is None
        assert s._pop_ok_values is None


def test_load_oot_atomicity_on_temporal_leak_nat_and_invalid_weight():
    """CRIT-05: load_oot fallido no contamina caches OOT ni lectores."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        edad = np.tile(np.arange(20, 60), 3)
        seg = np.tile(["a", "b", "c"], 40)
        y = (edad >= 40).astype(int)
        w = np.ones(len(edad), dtype=float)
        fechas_dev = pd.date_range("2025-01-01", periods=len(edad), freq="D")

        dev_csv = tmp / "dev.csv"
        pd.DataFrame({
            "edad": edad, "seg": seg, "w": w, "fecha": fechas_dev, "default": y,
        }).to_csv(dev_csv, index=False)

        s = Session(logger=_quiet_logger())
        s.load_dataset(str(dev_csv))
        s.fix_spec(
            "default",
            predictors=["edad", "seg"],
            target_class=1,
            class_labels={0: "Bueno", 1: "Malo"},
            weight_col="w",
        )
        s.partition(train_frac=0.7, seed=42)
        s.train(CrtEngine(), max_depth=3, min_child_size=5)

        def _assert_oot_untouched():
            assert s.state.state is FlowState.TRAINED
            assert s._X_oot is None
            assert s._y_oot is None
            assert s._df_oot is None
            assert s._w_oot is None
            _assert_raises(RuntimeError, s.get_gains_table, partition="oot")
            assert s.get_node_cases(0, partition="oot")["n_total"] == 0

        # 1) Fuga temporal (t_oot_min <= t_train_max)
        oot_leak = tmp / "oot_leak.csv"
        pd.DataFrame({
            "edad": edad[:40],
            "seg": seg[:40],
            "w": np.ones(40),
            "fecha": pd.date_range("2025-02-01", periods=40, freq="D"),
            "default": y[:40],
        }).to_csv(oot_leak, index=False)
        _assert_raises(ValueError, s.load_oot, str(oot_leak), time_col="fecha")
        _assert_oot_untouched()

        # 2) Fecha NaT en columna temporal OOT
        oot_nat = tmp / "oot_nat.csv"
        fechas_nat = list(
            pd.date_range("2026-01-01", periods=40, freq="D").astype(str)
        )
        fechas_nat[5] = ""
        pd.DataFrame({
            "edad": edad[:40],
            "seg": seg[:40],
            "w": np.ones(40),
            "fecha": fechas_nat,
            "default": y[:40],
        }).to_csv(oot_nat, index=False)
        _assert_raises(ValueError, s.load_oot, str(oot_nat), time_col="fecha")
        _assert_oot_untouched()

        # 3) Peso invalido en OOT
        oot_bad_w = tmp / "oot_bad_w.csv"
        w_bad = np.ones(40)
        w_bad[3] = -1.0
        pd.DataFrame({
            "edad": edad[:40],
            "seg": seg[:40],
            "w": w_bad,
            "fecha": pd.date_range("2026-01-01", periods=40, freq="D"),
            "default": y[:40],
        }).to_csv(oot_bad_w, index=False)
        _assert_raises(ValueError, s.load_oot, str(oot_bad_w), time_col="fecha")
        _assert_oot_untouched()


def test_fingerprint_distinguishes_population_filter_in_session():
    """CRIT-03: Session propaga population_col/population_ok_values al fingerprint."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        edad = np.tile(np.arange(20, 60), 6)  # 240 filas
        seg = np.tile(["a", "b", "c"], 80)
        y = (edad >= 40).astype(int)
        pop = np.array(["OK"] * 120 + ["OK2"] * 80 + ["INDET"] * 40)
        csv_path = tmp / "pop_fp.csv"
        pd.DataFrame({
            "edad": edad, "seg": seg, "pop": pop, "default": y,
        }).to_csv(csv_path, index=False)

        def _fp(pop_col, ok_vals):
            s = Session(logger=_quiet_logger())
            s.load_dataset(str(csv_path))
            s.fix_spec(
                "default",
                predictors=["edad", "seg"],
                target_class=1,
                class_labels={0: "Bueno", 1: "Malo"},
                population_col=pop_col,
                population_ok_values=ok_vals,
            )
            s.partition(train_frac=0.7, seed=42)
            st = s.train(CrtEngine(), max_depth=3, min_child_size=5)
            assert st.tree is not None
            return st.tree.params_fingerprint

        fp_none = _fp(None, None)
        fp_ok = _fp("pop", ("OK",))
        fp_both = _fp("pop", ("OK", "OK2"))
        assert len({fp_none, fp_ok, fp_both}) == 3


def test_session_governance_banking_vs_research_and_custom_zero_floor():
    """CRIT-03: contraste numerico real BANKING vs RESEARCH y floor=0.0 -> CUSTOM."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))

        # 1) BANKING (Jeffreys + pd_floor=0.0005)
        s.fix_spec("default", target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        st_b = s.train(
            CrtEngine(),
            max_depth=4,
            min_child_size=5,
            apply_jeffreys=True,
            pd_floor=0.0005,
        )
        assert st_b.tree is not None
        leaves_b = [nd for nd in st_b.tree.nodes if nd.is_leaf]
        assert len(leaves_b) == 2
        for leaf in leaves_b:
            expected_j = (leaf.n_events[0] + 0.5) / (leaf.n + 1.0)
            assert math.isclose(leaf.pd_jeffreys[0], expected_j, rel_tol=1e-12)
            assert leaf.pd_final[0] >= 0.0005
            assert leaf.pd_final[0] <= 1.0 - 0.0005
        assert s.get_summary()["model"]["governance_mode"] == "BANKING"

        # 2) RESEARCH (sin Jeffreys ni pd_floor): hojas puras = 0.0 y 1.0 exactos
        s.reset_to_data_loaded()
        s.fix_spec("default", target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        st_r = s.train(
            CrtEngine(),
            max_depth=4,
            min_child_size=5,
            apply_jeffreys=False,
            pd_floor=None,
        )
        assert st_r.tree is not None
        leaves_r = sorted(
            (nd.pd_final[0] for nd in st_r.tree.nodes if nd.is_leaf)
        )
        assert leaves_r == [0.0, 1.0]
        assert s.get_summary()["model"]["governance_mode"] == "RESEARCH"

        # 3) pd_floor=0.0 con apply_jeffreys=True -> CUSTOM (nunca BANKING)
        s.reset_to_data_loaded()
        s.fix_spec("default", target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train(
            CrtEngine(),
            max_depth=4,
            min_child_size=5,
            apply_jeffreys=True,
            pd_floor=0.0,
        )
        assert s.get_summary()["model"]["governance_mode"] == "CUSTOM"


def test_prune_connects_downstream_consumers_and_invalidates_metrics():
    """CRIT-06: prune() activa pruned_tree en todo el pipeline e invalida OOS."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        st0 = s.train(CrtEngine(), max_depth=4, min_child_size=5)
        assert st0.tree is not None and len(st0.tree.nodes) >= 3

        s.evaluate_oos(n_groups=5)
        assert s.state.oos_metrics is not None

        st_p = s.prune(999999.0)
        assert st_p.pruned_tree is not None
        assert s.active_tree is st_p.pruned_tree
        assert st_p.oos_metrics is None

        summary = s.get_summary()
        assert summary is not None
        assert summary["model"]["n_nodes"] == 1
        assert summary["model"]["fingerprint"] == st_p.pruned_tree.params_fingerprint

        gains = s.get_gains_table(partition="oos")
        assert gains is not None and len(gains["rows"]) == 1

        fp_p = st_p.pruned_tree.params_fingerprint
        assert fp_p in (s.export_to_sql() or "")
        assert fp_p in (s.export_to_python() or "")
        assert fp_p in (s.export_to_markdown() or "")
        assert fp_p in (s.get_rules("markdown") or "")
        assert fp_p in (s.get_rules("sql") or "")
        assert fp_p in (s.get_rules("python") or "")

        # Re-evaluar OOS evalua sobre el arbol podado (1 hoja -> Gini == 0.0)
        st_eval = s.evaluate_oos(n_groups=5)
        assert st_eval.oos_metrics is not None
        assert st_eval.oos_metrics.gini is not None
        assert math.isclose(st_eval.oos_metrics.gini, 0.0, abs_tol=1e-12)


def test_intervene_node_depth_ge_3_reindexes_parent_ids_and_invalidates():
    """CRIT-07: intervene_node en nodo interno no raiz (profundidad >= 3)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # 8 celdas deterministas (50 filas c/u = 400 filas) garantizan arbol
        # binario completo de profundidad 3 (15 nodos) en CRT.
        cell_events = [
            (0.0, 0.0, 0.0, 2),
            (0.0, 0.0, 1.0, 18),
            (0.0, 1.0, 0.0, 10),
            (0.0, 1.0, 1.0, 30),
            (1.0, 0.0, 0.0, 22),
            (1.0, 0.0, 1.0, 42),
            (1.0, 1.0, 0.0, 32),
            (1.0, 1.0, 1.0, 48),
        ]
        rows = []
        for x1, x2, x3, n_ev in cell_events:
            for i in range(50):
                rows.append((x1, x2, x3, 1 if i < n_ev else 0))
        csv_path = tmp / "depth3.csv"
        pd.DataFrame(rows, columns=["x1", "x2", "x3", "default"]).to_csv(
            csv_path, index=False
        )

        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        st0 = s.train(CrtEngine(), max_depth=4, min_child_size=5)
        assert st0.tree is not None
        assert max(nd.depth for nd in st0.tree.nodes) >= 3

        # Elegir un hijo interno no raiz cuyos hermanos tambien tengan descendientes
        root_children = st0.tree.nodes[0].child_ids
        internal_children = [
            cid for cid in root_children if not st0.tree.nodes[cid].is_leaf
        ]
        assert len(internal_children) >= 2
        target_node = internal_children[0]

        s.prune(0.0)
        assert s.state.pruned_tree is not None
        s.evaluate_oos()
        assert s.state.oos_metrics is not None

        # Rechazar bool en node_id
        _assert_raises(ValueError, s.intervene_node, True, "prune_branch")

        # Intervenir nodo interno no raiz: no debe fallar por parent_id incoherente
        st_int = s.intervene_node(target_node, "prune_branch")
        assert st_int.tree is not None
        assert st_int.oos_metrics is None
        assert st_int.pruned_tree is None
        assert s.active_tree is st_int.tree
        for nd in st_int.tree.nodes:
            for cid in nd.child_ids:
                assert st_int.tree.nodes[cid].parent_id == nd.node_id


def test_multiclass_string_target_e2e_holdout_cv_and_oot():
    """CRIT-08: soporte multiclase K>=3 con target de texto extremo a extremo.

    Verifica holdout, CV, auto-resolucion de target_type=None y string
    target_type='CATEGORICAL', get_gains_table (n_bad corresponde a 'High'),
    get_classification_matrix (matriz 3x3 + class_labels en orden canonico)
    y load_oot/evaluate_oot.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # 180 filas: 30 High (seg='h'), 60 Mid (seg='m'), 90 Low (seg='l')
        # Asimetrico para confirmar que n_bad == count('High') != count('Low')
        segs = ["h"] * 30 + ["m"] * 60 + ["l"] * 90
        edades = (
            list(np.linspace(55, 65, 30))
            + list(np.linspace(35, 45, 60))
            + list(np.linspace(20, 30, 90))
        )
        y_str = ["High"] * 30 + ["Mid"] * 60 + ["Low"] * 90
        df = pd.DataFrame({"edad": edades, "seg": segs, "riesgo": y_str})
        csv_dev = tmp / "multi_str_dev.csv"
        df.to_csv(csv_dev, index=False)

        # --- Holdout + target_type=None (auto-resuelto a CATEGORICAL) ---
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        s.fix_spec(
            "riesgo",
            target_class="High",
            class_labels={"High": "High", "Low": "Low", "Mid": "Mid"},
        )
        s.partition(train_frac=0.7, seed=42)
        st = s.train("CRT", max_depth=4, min_child_size=5)
        assert st.tree is not None
        assert st.tree.class_labels == ("High", "Low", "Mid")
        assert s._last_train_params is not None
        assert s._last_train_params["target_type"] is TargetType.CATEGORICAL

        st_oos = s.evaluate_oos(n_groups=3)
        assert st_oos.oos_metrics is not None
        assert st_oos.oos_metrics.auc == 1.0
        assert st_oos.oos_metrics.gini == 1.0

        # Gains table: n_bad debe contar exactamente 'High' (9 en 30% OOS de 30),
        # NO 'Low' (27 en 30% OOS de 90) ni 'Mid' (18 en 30% OOS de 60).
        expected_high_oos = int(np.sum(s._y_test == "High"))
        assert expected_high_oos == 9
        gains = s.get_gains_table(partition="oos")
        assert gains is not None
        assert gains["n_bad"] == expected_high_oos
        assert gains["class_labels"] == ("High", "Low", "Mid")
        assert gains["n_per_class_global"][0] == expected_high_oos

        # Classification matrix: 3x3 con class_labels reales en orden canonico
        cm_dto = s.get_classification_matrix(partition="oos")
        assert cm_dto is not None
        assert cm_dto["class_labels"] == ("High", "Low", "Mid")
        assert len(cm_dto["confusion_matrix"]) == 3
        assert all(len(row) == 3 for row in cm_dto["confusion_matrix"])
        assert cm_dto["accuracy"] == 1.0
        assert cm_dto["n_bad"] == expected_high_oos

        # OOT con target de texto
        csv_oot = tmp / "multi_str_oot.csv"
        df.to_csv(csv_oot, index=False)
        st_oot_l = s.load_oot(str(csv_oot))
        assert st_oot_l.state is FlowState.OOT_LOADED
        st_oot_e = s.evaluate_oot(n_groups=3)
        assert st_oot_e.oot_report is not None
        assert st_oot_e.oot_report.metrics is not None
        assert st_oot_e.oot_report.metrics.auc == 1.0

        # --- CV + target_type="CATEGORICAL" (string plano) ---
        s_cv = Session(logger=_quiet_logger())
        s_cv.load_dataset(str(csv_dev))
        s_cv.fix_spec(
            "riesgo",
            target_class="High",
            class_labels={"High": "High", "Low": "Low", "Mid": "Mid"},
        )
        s_cv.partition(scheme="cv", k=3, seed=42)
        s_cv.train("CRT", target_type="CATEGORICAL", max_depth=4, min_child_size=5)
        assert s_cv._last_train_params is not None
        assert s_cv._last_train_params["target_type"] is TargetType.CATEGORICAL
        cv_rep = s_cv.evaluate_oos(n_groups=3)
        assert isinstance(cv_rep, dict)
        assert cv_rep["scheme"] == "cv" and cv_rep["k"] == 3
        assert cv_rep["metrics_mean"]["auc"] == 1.0


def test_get_gains_table_multiclass_int_target_class_2():
    """CRIT-08: en K=3 entero {0,1,2} con target_class=2, n_bad cuenta clase 2."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Conteos asimetricos: 20 de clase 2, 40 de clase 1, 60 de clase 0
        df = pd.DataFrame({
            "edad": list(range(20)) + list(range(40, 80)) + list(range(100, 160)),
            "seg": ["c2"] * 20 + ["c1"] * 40 + ["c0"] * 60,
            "default": [2] * 20 + [1] * 40 + [0] * 60,
        })
        csv_path = tmp / "int_k3_asym.csv"
        df.to_csv(csv_path, index=False)

        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec(
            "default",
            target_class=2,
            class_labels={0: "Bajo", 1: "Medio", 2: "Alto"},
        )
        s.partition(train_frac=0.7, seed=42)
        s.train("CRT", max_depth=4, min_child_size=5)

        expected_c2_oos = int(np.sum(s._y_test == 2))
        expected_c0_oos = int(np.sum(s._y_test == 0))
        assert expected_c2_oos != expected_c0_oos
        gains = s.get_gains_table(partition="oos")
        assert gains is not None
        assert gains["n_bad"] == expected_c2_oos
        assert gains["class_labels"] == ("Alto", "Bajo", "Medio")
        assert gains["n_per_class_global"][0] == expected_c2_oos


def test_load_oot_rejects_unseen_target_class_atomically():
    """CRIT-08: load_oot rechaza clases no vistas en OOT preservando atomicidad."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        df = pd.DataFrame({
            "edad": np.arange(90),
            "seg": ["h"] * 30 + ["m"] * 30 + ["l"] * 30,
            "riesgo": ["High"] * 30 + ["Mid"] * 30 + ["Low"] * 30,
        })
        csv_dev = tmp / "dev_str.csv"
        df.to_csv(csv_dev, index=False)

        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_dev))
        s.fix_spec(
            "riesgo",
            target_class="High",
            class_labels={"High": "High", "Low": "Low", "Mid": "Mid"},
        )
        s.partition(train_frac=0.7, seed=42)
        s.train("CRT", max_depth=4, min_child_size=5)

        df_bad_oot = pd.DataFrame({
            "edad": [10, 20, 30, 40],
            "seg": ["h", "m", "l", "h"],
            "riesgo": ["High", "Mid", "Low", "UnknownClass"],
        })
        csv_bad = tmp / "oot_unseen_cls.csv"
        df_bad_oot.to_csv(csv_bad, index=False)

        _assert_raises(ValueError, s.load_oot, str(csv_bad))
        assert s.state.state is FlowState.TRAINED
        assert s._X_oot is None and s._y_oot is None and s._df_oot is None


def test_session_train_rejects_invalid_target_type():
    """CRIT-08: Session.train rechaza target_type string o tipo invalido."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv(Path(td))
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(csv_path))
        s.fix_spec("default", target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        _assert_raises(ValueError, s.train, "CRT", target_type="invalid")
        _assert_raises(ValueError, s.train, "CRT", target_type=123)
        assert s.state.state is FlowState.PARTITIONED


def test_evaluate_oot_cv_mode_without_oos_or_after_prune():
    """CRIT-12: evaluate_oot en modo CV sin evaluate_oos ni _X_test no crashea."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dev_csv = _csv(tmp)
        oot_csv = tmp / "oot_cv.csv"
        pd.read_csv(dev_csv).to_csv(oot_csv, index=False)

        # Caso 1: CV sin evaluate_oos previo
        s = Session(logger=_quiet_logger())
        s.load_dataset(str(dev_csv))
        s.fix_spec("default", target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s.partition(scheme="cv", k=5, seed=42)
        s.train("CRT", max_depth=4, min_child_size=5)
        assert s._X_test is None
        s.load_oot(str(oot_csv))
        st = s.evaluate_oot(n_groups=3)
        r = st.oot_report
        assert r is not None
        assert r.drop.gini_oos is None
        assert r.drop.drop_oos is None
        assert r.drop.alert_oos == "UNDETERMINED"
        assert r.drop.gini_oot is not None

        # Caso 2: CV tras evaluate_oos() + prune() -> load_oot() -> evaluate_oot()
        s2 = Session(logger=_quiet_logger())
        s2.load_dataset(str(dev_csv))
        s2.fix_spec("default", target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s2.partition(scheme="cv", k=5, seed=42)
        s2.train("CRT", max_depth=4, min_child_size=5)
        s2.evaluate_oos(n_groups=3)
        s2.prune(0.0)
        s2.load_oot(str(oot_csv))
        st2 = s2.evaluate_oot(n_groups=3)
        r2 = st2.oot_report
        assert r2 is not None
        assert r2.drop.gini_oos is None
        assert r2.drop.drop_oos is None
        assert r2.drop.alert_oos == "UNDETERMINED"
        assert r2.drop.gini_oot is not None


def test_evaluate_oot_nonpositive_gini_train_returns_undetermined():
    """CRIT-12: con gini_train <= 0, drop_oot es None y alert_oot=UNDETERMINED."""
    from dataclasses import replace as dc_replace

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dev_csv = _csv(tmp)
        oot_csv = tmp / "oot_inv.csv"
        pd.read_csv(dev_csv).to_csv(oot_csv, index=False)

        s = Session(logger=_quiet_logger())
        s.load_dataset(str(dev_csv))
        s.fix_spec("default", target_class=1, class_labels={0: "Bueno", 1: "Malo"})
        s.partition(train_frac=0.7, seed=42)
        s.train("CRT", max_depth=4, min_child_size=5)
        s.load_oot(str(oot_csv))

        # Invertir PDs de las hojas en un TreeModel inmutable -> gini_train < 0
        orig = s.active_tree
        assert orig is not None
        inv_nodes = tuple(
            dc_replace(nd, pd_final=(nd.pd_final[1], nd.pd_final[0]))
            if nd.is_leaf else nd
            for nd in orig.nodes
        )
        inv_tree = dc_replace(orig, nodes=inv_nodes)
        s._state = dc_replace(s._state, tree=inv_tree, pruned_tree=None, oos_metrics=None)

        st = s.evaluate_oot(n_groups=3)
        r = st.oot_report
        assert r is not None
        assert r.drop.gini_train < 0.0
        assert r.drop.drop_oot is None
        assert r.drop.alert_oot == "UNDETERMINED"
        assert r.drop.drop_oos is None
        assert r.drop.alert_oos == "UNDETERMINED"


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
