"""Headless GUI tests for the Phase 6 scoring dialogs and menu actions."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from unittest.mock import patch  # noqa: E402

from backend_v3.session_state import Session  # noqa: E402
from backend_v3.types import PredictorType, TargetType  # noqa: E402
from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import set_language, tr  # noqa: E402
from frontend_v3.main_window import MainWindow  # noqa: E402
from frontend_v3.scoring_dialogs import (  # noqa: E402
    BatchScoringDialog,
    ChampionChallengerDialog,
)


def _get_app() -> QApplication:
    """Reuse the QApplication singleton or create it for headless tests."""
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _setup_session(tmp_path) -> tuple[Session, object]:
    """Build a deterministic trained session and its source CSV."""
    rng = np.random.default_rng(42)
    edad = rng.integers(20, 61, size=100)
    seg = rng.choice(["A", "B", "C"], size=100, p=[0.2, 0.2, 0.6])
    target = ((edad >= 40) | (seg == "C")).astype(int)
    csv_path = tmp_path / "train.csv"
    pd.DataFrame({"edad": edad, "seg": seg, "target": target}).to_csv(
        csv_path, index=False
    )

    session = Session()
    session.load_dataset(str(csv_path))
    session.fix_spec(
        target="target",
        spec={
            "edad": PredictorType.CONTINUOUS,
            "seg": PredictorType.NOMINAL,
        },
        target_class=1,
        class_labels={0: "Non-event", 1: "Event"},
    )
    session.partition(train_frac=0.7, seed=42)
    session.train(
        "CRT",
        target_type=TargetType.BINARY,
        max_depth=3,
        min_child_size=5,
    )
    return session, csv_path


def test_batch_dialog_creation(tmp_path):
    """The batch form exists and starts without an executable run action."""
    _get_app()
    set_language("en")
    session, _ = _setup_session(tmp_path)
    dialog = BatchScoringDialog(session)
    try:
        assert dialog._input_edit is not None
        assert dialog._output_edit is not None
        assert dialog._policy_combo.count() == 3
        assert dialog._chunksize_spin.value() == 50000
        assert dialog._rules_check.isChecked()
        assert not dialog._run_button.isEnabled()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_batch_dialog_run_mocked(tmp_path):
    """Run disables the form and starts a mocked worker, never a real thread."""
    _get_app()
    set_language("en")
    session, csv_path = _setup_session(tmp_path)
    dialog = BatchScoringDialog(session)
    try:
        with patch("frontend_v3.scoring_dialogs.BatchWorker") as worker_type:
            worker = worker_type.return_value
            dialog._input_edit.setText(str(csv_path))
            dialog._output_edit.setText(str(tmp_path / "scored.csv"))
            assert dialog._run_button.isEnabled()

            dialog._run_button.click()

            worker_type.assert_called_once_with(
                session,
                str(csv_path),
                str(tmp_path / "scored.csv"),
                "exclude",
                50000,
                True,
            )
            worker.start.assert_called_once_with()
            assert not dialog._input_edit.isEnabled()
            assert not dialog._output_edit.isEnabled()
            assert not dialog._policy_combo.isEnabled()
            assert not dialog._chunksize_spin.isEnabled()
            assert not dialog._rules_check.isEnabled()
            assert not dialog._run_button.isEnabled()
            assert not dialog._progress.isHidden()
            assert dialog._progress.minimum() == 0
            assert dialog._progress.maximum() == 0
    finally:
        dialog._set_running(False)
        dialog.close()
        dialog.deleteLater()


def test_cc_dialog_table_population(tmp_path):
    """The comparison slot renders metrics and maps missing values to em dash."""
    _get_app()
    set_language("en")
    session, _ = _setup_session(tmp_path)
    dialog = ChampionChallengerDialog(session)
    try:
        dialog._on_worker_finished(
            {
                "champion_fingerprint": "fp-champion",
                "challenger_fingerprint": "fp-challenger",
                "n_common_routed": 97,
                "metrics": (
                    ("AUC", 0.70, 0.75, 0.05),
                    ("KS", None, None, None),
                ),
            }
        )

        assert dialog._table.rowCount() == 2
        assert dialog._table.columnCount() == 4
        assert dialog._table.item(0, 0).text() == "AUC"
        assert dialog._table.item(0, 1).text() == "0.7"
        assert dialog._table.item(0, 2).text() == "0.75"
        assert dialog._table.item(0, 3).text() == "0.05"
        assert dialog._table.item(1, 1).text() == "—"
        assert dialog._table.item(1, 2).text() == "—"
        assert dialog._table.item(1, 3).text() == "—"
        assert not dialog._table.isHidden()
        assert "fp-champion" in dialog._result_label.text()
        assert "fp-challenger" in dialog._result_label.text()
        assert "97" in dialog._result_label.text()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_mainwindow_actions(tmp_path):
    """Both Phase 6 actions become enabled for a window with a trained tree."""
    _get_app()
    session, _ = _setup_session(tmp_path)
    window = MainWindow(session=session)
    try:
        set_language("en")
        window.retranslate_ui()
        assert window._session.state.tree is not None
        assert window._act_batch.isEnabled()
        assert window._act_cc.isEnabled()
        assert window._act_batch.text() == tr("menu_analysis_batch")
        assert window._act_cc.text() == tr("menu_analysis_cc")
    finally:
        window.close()
        window.deleteLater()
