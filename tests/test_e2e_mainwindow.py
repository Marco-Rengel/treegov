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


def _cfg() -> dict:
    """Minimal valid wizard config for a 300-row synthetic dataset."""
    return {
        "engine": "CRT",
        "target": "default",
        "predictors": ["edad", "seg", "ratio"],
        "target_class": 1,
        "class_labels": {0: "Non-event", 1: "Event"},
        "train_frac": 0.7,
        "seed": 42,
        "max_depth": 3,
        "min_child_size": 20,
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