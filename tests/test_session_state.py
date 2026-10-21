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
        s.train("CRT", max_depth=3, min_child_size=5)
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
        s.train("QUEST", max_depth=3, min_child_size=5)
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
        s.train("QUEST", max_depth=4, min_child_size=5)
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
        s.train("CHAID", max_depth=3, min_child_size=5)
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
        s.train("CRT", max_depth=4, min_child_size=5)
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
        s.train("CHAID", max_depth=3, min_child_size=5)
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
    auc = gini = ks = 1; brier = (0.5/43)^2; hl_stat = 24/85.
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
        assert math.isclose(m.hl_stat, 24.0 / 85.0, rel_tol=1e-12)


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
        s.train("CHAID", max_depth=3, min_child_size=5)
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
        s.train("CHAID", max_depth=3, min_child_size=5)
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
            s.train("CHAID", max_depth=3, min_child_size=5)
            return s.get_classification_matrix(partition="oos", threshold=thr)

    d1 = _dto_con_threshold(0.99)
    d2 = _dto_con_threshold(0.01)
    assert d1 is not None and d2 is not None
    assert math.isnan(d1["threshold"]) and math.isnan(d2["threshold"])
    resto1 = {k: v for k, v in d1.items() if k != "threshold"}
    resto2 = {k: v for k, v in d2.items() if k != "threshold"}
    assert resto1 == resto2


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
