"""E2E tests for the File > Export menu wiring (Phase 4.0.c).

Offscreen tests that verify: (a) the three export actions start
disabled when no model has been trained; (b) they become enabled
after a successful _on_wizard_finished; (c) MainWindow._export_payload
returns a well-formed tuple whose first element carries the model
fingerprint as its leading comment, without ever opening a QFileDialog.

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so
a real display session keeps its platform).
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import set_language  # noqa: E402
from frontend_v3.main_window import MainWindow  # noqa: E402


def _get_app() -> QApplication:
    """Reuse the running QApplication or create one (Qt is a singleton)."""
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _quiet_logger() -> logging.Logger:
    lg = logging.getLogger("treegov.e2e_exporters")
    if not lg.handlers:
        lg.addHandler(logging.NullHandler())
    lg.propagate = False
    return lg


def _make_csv(path: Path, n: int = 300, seed: int = 42) -> Path:
    """Deterministic synthetic CSV: target is `default` = 1_{edad >= 40}."""
    rng = np.random.default_rng(seed)
    edad = rng.integers(20, 60, size=n)
    df = pd.DataFrame(
        {
            "edad": edad,
            "seg": rng.choice(["a", "b", "c"], size=n),
            "ratio": rng.uniform(0.1, 0.9, size=n),
            "default": (edad >= 40).astype(int),
        }
    )
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
        "pd_floor": 0.0005,
        "cost_matrix": (),
    }


def _open_window(csv_path: Path) -> MainWindow:
    """Build a MainWindow with a fresh Session + loaded CSV. Ready to train.

    Note: MainWindow.__init__ sets the language from the system locale.
    We force English AFTER construction and call retranslate_ui() so all
    widget texts use the "en" strings.
    """
    _get_app()
    w = MainWindow(logger=_quiet_logger())
    set_language("en")
    w.retranslate_ui()
    ok = w._load_dataset_path(str(csv_path))
    assert ok, "dataset load must succeed"
    return w


def test_export_actions_disabled_before_train():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            assert not w._act_export_sql.isEnabled()
            assert not w._act_export_python.isEnabled()
            assert not w._act_export_markdown.isEnabled()
        finally:
            w.close()
            w.deleteLater()


def test_export_actions_enabled_after_train():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg())
            assert w._session.state.tree is not None
            assert w._act_export_sql.isEnabled()
            assert w._act_export_python.isEnabled()
            assert w._act_export_markdown.isEnabled()
        finally:
            w.close()
            w.deleteLater()


def test_export_payload_returns_well_formed_tuple_after_train():
    """After a successful train, the three payloads are non-None 3-tuples
    whose content starts with the expected comment marker and whose
    default filename is the documented one.
    """
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg())
            fp = w._session.state.tree.params_fingerprint
            payload_sql = w._export_payload("sql")
            payload_py = w._export_payload("python")
            payload_md = w._export_payload("markdown")
            for payload in (payload_sql, payload_py, payload_md):
                assert payload is not None
                assert len(payload) == 3
                content, ffilter, default_name = payload
                assert isinstance(content, str) and content.strip()
                assert isinstance(ffilter, str) and ffilter
                assert isinstance(default_name, str) and default_name
            assert payload_sql[0].startswith(
                f"-- TreeGov Model Fingerprint: {fp}"
            )
            assert payload_py[0].startswith(
                f"# TreeGov Model Fingerprint: {fp}"
            )
            assert payload_md[0].startswith("# TreeGov Decision Tree")
            assert payload_sql[2] == "treegov_model.sql"
            assert payload_py[2] == "treegov_model.py"
            assert payload_md[2] == "treegov_model.md"
        finally:
            w.close()
            w.deleteLater()


def test_export_payload_returns_none_without_model():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            assert w._export_payload("sql") is None
            assert w._export_payload("python") is None
            assert w._export_payload("markdown") is None
        finally:
            w.close()
            w.deleteLater()


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
