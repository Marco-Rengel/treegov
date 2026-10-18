"""E2E tests for MainWindow OOS/OOT flow (Phase 2.3.f).

Cover the full integration path:
- Load CSV -> wizard/train actions enabled.
- Simulated wizard finish -> tree rendered, OOS/OOT actions enabled.
- _on_evaluate_oos -> panel refreshed with OOS section.
- _on_load_oot (mocked dialog) -> panel refreshed with OOT badges.
- Reset wizard -> panel back to placeholder.

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so a
real display session keeps its platform). Dialog-free by mocking
QFileDialog.getOpenFileName where needed.

Dual: pytest or plain python (same convention as the other test files).
"""

import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import _STRINGS, set_language  # noqa: E402
from frontend_v3.main_window import MainWindow  # noqa: E402


def _get_app() -> QApplication:
    """Reuse the running QApplication or create one (Qt is a singleton)."""
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _quiet_logger(name: str = "treegov.e2e") -> logging.Logger:
    lg = logging.getLogger(name)
    if not lg.handlers:
        lg.addHandler(logging.NullHandler())
    lg.propagate = False
    return lg


def _make_csv(path: Path, n: int = 300, seed: int = 42) -> Path:
    """Deterministic synthetic CSV: target is `default` = 1_{edad >= 40}."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "edad": rng.integers(20, 60, size=n),
        "seg": rng.choice(["a", "b", "c"], size=n),
        "ratio": rng.uniform(0.1, 0.9, size=n),
        "default": (rng.integers(20, 60, size=n) >= 40).astype(int),
    })
    df.to_csv(path, index=False)
    return path


def _make_csv_population(path: Path, n: int = 300, seed: int = 42) -> Path:
    """CSV con columna de poblacion. 60% OK, 25% INDET, 15% INSUF.

    Mantiene las columnas de _make_csv (edad/seg/ratio/default) para no
    romper consumidores existentes, y añade `pop`.
    """
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "edad": rng.integers(20, 60, size=n),
        "seg": rng.choice(["a", "b", "c"], size=n),
        "ratio": rng.uniform(0.1, 0.9, size=n),
        "default": (rng.integers(20, 60, size=n) >= 40).astype(int),
    })
    n_ok = int(round(n * 0.60))
    n_indet = int(round(n * 0.25))
    n_insuf = n - n_ok - n_indet
    df["pop"] = ["OK"] * n_ok + ["INDET"] * n_indet + ["INSUF"] * n_insuf
    df.to_csv(path, index=False)
    return path


def _cfg_population(pop_col: str | None = "pop",
                    ok_values: tuple = ("OK",)) -> dict:
    """Config mínima válida con/sin filtro de población."""
    cfg = _cfg()
    cfg["predictors"] = ["edad", "seg", "ratio"]
    cfg["population_col"] = pop_col
    cfg["population_ok_values"] = ok_values
    return cfg


def _cfg() -> dict:
    """Minimal valid wizard config for a 300-row synthetic dataset."""
    return {
        "engine": "CRT",
        "target": "default",
        "predictors": ["edad", "seg", "ratio"],
        "target_class": 1,
        "class_labels": {0: "Non-event", 1: "Event"},
        "weight_col": None,
        "population_col": None,
        "population_ok_values": (),
        "train_frac": 0.7,
        "seed": 42,
        "max_depth": 3,
        "min_child_size": 20,
        "min_child_weight": None,
        "governance_mode": "BANKING",
        "apply_jeffreys": True,
        "pd_floor": 0.0003,
    }


def _all_labels(widget) -> list:
    return widget.findChildren(QLabel)


def _label_texts(widget) -> list:
    return [lbl.text() for lbl in _all_labels(widget)]


def _badges(widget) -> list:
    return [lbl for lbl in _all_labels(widget) if lbl.property("status")]


def _open_window(csv_path: Path) -> MainWindow:
    """Build a MainWindow with a fresh Session + loaded CSV. Ready to train.

    Note: MainWindow.__init__ sets the language from the system locale.
    We force English AFTER construction and call retranslate_ui() so all
    widget texts (and metrics panel labels) use the "en" strings.
    """
    _get_app()
    w = MainWindow(logger=_quiet_logger())
    set_language("en")
    w.retranslate_ui()
    ok = w._load_dataset_path(str(csv_path))
    assert ok, "dataset load must succeed"
    return w


# ---------------------------------------------------------------------------
# E2E tests (5)
# ---------------------------------------------------------------------------


def test_e2e_load_csv_enables_actions():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            assert w._act_new_wizard.isEnabled()
            assert w._act_train.isEnabled()
            # OOS/OOT still disabled until a model is trained
            assert not w._act_evaluate_oos.isEnabled()
            assert not w._act_load_oot.isEnabled()
        finally:
            w.close()
            w.deleteLater()


def test_e2e_train_enables_oos_oot_actions():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg())
            assert w._session.state.tree is not None, "tree must be trained"
            assert w._act_evaluate_oos.isEnabled()
            assert w._act_load_oot.isEnabled()
        finally:
            w.close()
            w.deleteLater()


def test_e2e_evaluate_oos_refreshes_panel():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg())
            # Trigger the handler directly (no menu click needed in headless)
            w._on_evaluate_oos()
            texts = _label_texts(w._metrics_panel)
            assert _STRINGS["en"]["oos_section_title"] in texts
            # OOT section should NOT appear (no cohort loaded yet)
            assert _STRINGS["en"]["oot_section_title"] not in texts
            # Tab switched to the metrics panel
            assert w._tabs.currentWidget() is w._metrics_panel
        finally:
            w.close()
            w.deleteLater()


def test_e2e_load_oot_via_mocked_dialog():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        oot_csv = _make_csv(Path(td) / "mini_oot.csv", seed=7)
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg())
            # Mock QFileDialog.getOpenFileName to return our OOT path
            with patch(
                "frontend_v3.main_window.QFileDialog.getOpenFileName",
                return_value=(str(oot_csv), ""),
            ):
                w._on_load_oot()
            texts = _label_texts(w._metrics_panel)
            assert _STRINGS["en"]["oot_section_title"] in texts
            # OOT report has PSI + Gini Drop badges -> at least 2 badges
            assert len(_badges(w._metrics_panel)) >= 2
            assert w._tabs.currentWidget() is w._metrics_panel
        finally:
            w.close()
            w.deleteLater()


def test_e2e_new_wizard_resets_panel():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg())
            w._on_evaluate_oos()
            # Panel has content now
            assert _badges(w._metrics_panel) or _label_texts(w._metrics_panel)
            # Reopening the wizard resets the session + panel
            w._on_new_wizard()
            # Panel back to placeholder (only the empty message)
            texts = _label_texts(w._metrics_panel)
            assert _STRINGS["en"]["oos_oot_no_model"] in texts
            assert len(_badges(w._metrics_panel)) == 0
        finally:
            w.close()
            w.deleteLater()


def test_e2e_inversion_recovery_full_flow():
    """Fase 3.1.f: el analista declaro la clase de interes al reves,
    el Gini OOS sale negativo, el badge crit y el boton aparecen, y la
    reversion via inversion_requested corrige el modelo reentrenando
    con el mismo cfg.

    Nota: el target de _make_csv es ruido independiente de los
    predictores, asi que el Gini OOS cae cerca de 0 por azar; con el
    dataset determinista (seed=42) es target_class=1 quien da gini
    negativo (-0.156) y target_class=0 el positivo (+0.156), al reves
    de lo que sugiere la intuicion. El test arranca por tanto en
    target_class=1 y la reversion corrige a target_class=0.
    """
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            cfg_invertido = dict(_cfg(), target_class=1)
            w._on_wizard_finished(cfg_invertido)
            assert w._session.state.tree is not None
            assert w._session.state.target_class == 1
            w._on_evaluate_oos()
            # Badge + boton activos (gini OOS negativo)
            assert w._metrics_panel._invert_button is not None
            crit = [b for b in _badges(w._metrics_panel)
                    if b.property("status") == "crit"]
            assert len(crit) >= 1
            fp_antes = w._session.state.tree.params_fingerprint
            # Reversion directa por senal (offscreen: sin QMessageBox)
            w._metrics_panel.inversion_requested.emit()
            st = w._session.state
            assert st.state.name == "TRAINED"
            assert st.target_class == 0
            assert st.tree is not None
            assert st.tree.params_fingerprint != fp_antes
            assert w._last_train_cfg["target_class"] == 0
        finally:
            w.close()
            w.deleteLater()


# ---------------------------------------------------------------------------
# 3.2.h - Ponderación por muestra
# ---------------------------------------------------------------------------


def test_e2e_weighted_full_flow():
    """Flujo completo con weight_col: _train_pipeline lo propaga a fix_spec
    y el fingerprint registra el modo de ponderación."""
    with tempfile.TemporaryDirectory() as td:
        rng = np.random.default_rng(42)
        n = 300
        edad = rng.integers(20, 60, size=n)
        df = pd.DataFrame({
            "edad": edad,
            "seg": rng.choice(["a", "b", "c"], size=n),
            "ratio": rng.uniform(0.1, 0.9, size=n),
            "peso": np.where(edad >= 40, 1.5, 1.0),
            "default": (rng.integers(20, 60, size=n) >= 40).astype(int),
        })
        csv = Path(td) / "mini_w.csv"
        df.to_csv(csv, index=False)

        cfg_base = {
            "engine": "CRT",
            "target": "default",
            "predictors": ["edad", "seg", "ratio"],
            "target_class": 1,
            "class_labels": {0: "Non-event", 1: "Event"},
            "population_col": None,
            "population_ok_values": (),
            "train_frac": 0.7,
            "seed": 42,
            "max_depth": 3,
            "min_child_size": 20,
            "min_child_weight": None,
            "governance_mode": "BANKING",
            "apply_jeffreys": True,
            "pd_floor": 0.0003,
        }

        w0 = _open_window(csv)
        try:
            w0._train_pipeline({**cfg_base, "weight_col": None})
            fp0 = w0._session.state.tree.params_fingerprint
        finally:
            w0.close()
            w0.deleteLater()

        w1 = _open_window(csv)
        try:
            w1._train_pipeline({**cfg_base, "weight_col": "peso"})
            tree1 = w1._session.state.tree
            assert tree1 is not None
            assert w1._session._w_col == "peso"
            assert tree1.params_fingerprint != fp0
        finally:
            w1.close()
            w1.deleteLater()


def test_e2e_population_full_flow():
    """Fase 3.3.e: flujo completo con filtro de poblacion activo.

    Verifica que:
    - el wizard cfg con population_col llega a Session.fix_spec;
    - el modelo se entrena con las filas OK;
    - n_excluded_population y population_breakdown se reportan;
    - train_idx y test_idx son posiciones relativas al _df original
      (invariante de 3.3 §1.3).
    """
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv_population(Path(td) / "mini_pop.csv")
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg_population())
            st = w._session.state
            assert st.state.name == "TRAINED"
            assert st.tree is not None
            assert st.population_col == "pop"
            assert st.population_ok_values == ("OK",)
            assert st.n_excluded_population > 0
            # breakdown por motivo, dos valores no-OK
            valores = [b[0] for b in st.population_breakdown]
            assert "INDET" in valores
            assert "INSUF" in valores
            # idx relativos al CSV original (no al filtrado)
            n_total = st.n_rows
            assert n_total is not None
            assert (len(st.train_idx) + len(st.test_idx)
                    + st.n_excluded_population) == n_total
            # fingerprint registra el filtro
            assert st.tree.params_fingerprint  # existe
            # OOS evalua sobre las filas OK de test
            w._on_evaluate_oos()
            metrics = w._session.state.oos_metrics
            assert metrics is not None
        finally:
            w.close()
            w.deleteLater()


def test_e2e_population_reset_clears_state():
    """Fase 3.3.e: reset_to_data_loaded limpia los caches de poblacion
    y permite reconfigurar sin releer el CSV."""
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv_population(Path(td) / "mini_pop.csv")
        w = _open_window(csv)
        try:
            # Primera corrida CON filtro
            w._on_wizard_finished(_cfg_population())
            st1 = w._session.state
            assert st1.n_excluded_population > 0

            # Reset y segunda corrida SIN filtro (mismo dataset)
            w._on_new_wizard()  # dispara reset_to_data_loaded internamente
            st_reset = w._session.state
            assert st_reset.state.name == "DATA_LOADED"
            assert st_reset.population_col is None
            assert st_reset.population_ok_values == ()
            assert w._session._pop_col is None
            assert w._session._pop_ok_values is None

            # Segunda corrida sin filtro -> paridad con pre-3.3
            w._on_wizard_finished(_cfg_population(pop_col=None,
                                                  ok_values=()))
            st2 = w._session.state
            assert st2.state.name == "TRAINED"
            assert st2.n_excluded_population == 0
            assert st2.population_breakdown == ()
        finally:
            w.close()
            w.deleteLater()


# ---------------------------------------------------------------------------
# Direct execution without pytest
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
    print(f"\nOK - {len(tests)} tests passed")