"""E2E tests for ReportsPanel flow (Phase 2.4.d).

Cover the full reports integration path:
- Simulated wizard finish -> gains table populated, OOS partition default.
- Partition switch to "train" -> gains recomputed for the train partition.
- Export click -> HTML report built and handed to the export dialog.
- Save-to-file (mocked dialog) -> HTML written to disk.

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so a
real display session keeps its platform). Dialog-free by mocking
QFileDialog.getSaveFileName and QMessageBox.information where needed.

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


def _quiet_logger(name: str = "treegov.e2e.reports") -> logging.Logger:
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


# ---------------------------------------------------------------------------
# E2E tests (4)
# ---------------------------------------------------------------------------


def test_e2e_train_populates_reports_table():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg())
            assert w._session.state.tree is not None, "model must be trained"
            assert w._reports_panel._gains is not None, (
                "gains table must be populated after training"
            )
            assert w._reports_panel._table.rowCount() > 0, "table must have rows"
            assert w._reports_panel.current_partition() == "oos"
        finally:
            w.close()
            w.deleteLater()


def test_e2e_partition_switch_recomputes():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg())
            assert w._session.state.tree is not None
            combo = w._reports_panel._partition_combo
            idx = combo.findData("train")
            assert idx >= 0, "train option must exist in the partition combo"
            assert combo.model().item(idx).isEnabled(), (
                "train option must be enabled after training"
            )
            combo.setCurrentIndex(idx)
            assert w._reports_panel.current_partition() == "train"
            assert w._reports_panel._gains is not None, (
                "gains must be recomputed for train"
            )
            assert w._reports_panel._table.rowCount() > 0
        finally:
            w.close()
            w.deleteLater()


def test_e2e_export_clicked_builds_html():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg())
            assert w._reports_panel._gains is not None, (
                "gains must be populated before export"
            )
            captured = {}
            with patch.object(
                w._reports_panel,
                "_open_export_dialog",
                side_effect=lambda html: captured.update({"html": html}),
            ):
                w._reports_panel._on_export_clicked()
            assert "html" in captured, "_open_export_dialog must have been called"
            assert captured["html"].startswith("<!DOCTYPE html>")
            assert "L" in captured["html"], (
                "HTML must contain at least one leaf label"
            )
        finally:
            w.close()
            w.deleteLater()


def test_e2e_save_html_writes_file():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        w = _open_window(csv)
        try:
            w._on_wizard_finished(_cfg())
            assert w._reports_panel._gains is not None
            html = w._reports_panel._build_report_html()
            out_path = Path(td) / "report.html"
            with patch(
                "frontend_v3.reports_panel.QFileDialog.getSaveFileName",
                return_value=(str(out_path), ""),
            ):
                with patch("frontend_v3.reports_panel.QMessageBox.information"):
                    w._reports_panel._save_html_to_file(None, html)
            assert out_path.exists(), "file must be written"
            content = out_path.read_text(encoding="utf-8")
            assert content.startswith("<!DOCTYPE html>")
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
