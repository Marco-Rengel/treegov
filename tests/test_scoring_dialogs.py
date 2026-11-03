"""Headless GUI tests for the Phase 6 scoring dialogs and menu actions."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from unittest.mock import patch  # noqa: E402

from backend_v3.session_state import Session  # noqa: E402
from backend_v3.types import PredictorType, TargetType  # noqa: E402
from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import (  # noqa: E402
    get_language,
    language_bus,
    set_language,
    tr,
)
from frontend_v3.main_window import MainWindow  # noqa: E402
from frontend_v3.scoring_dialogs import (  # noqa: E402
    BatchScoringDialog,
    BatchWorker,
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


def test_batch_dialog_run_real_worker(tmp_path):
    """N7: a real BatchWorker scores a CSV and reports GUI success."""
    _get_app()
    set_language("en")
    session, _ = _setup_session(tmp_path)
    input_path = tmp_path / "score_input.csv"
    output_path = tmp_path / "scored_real.csv"
    pd.DataFrame(
        {"edad": [25, 45, 55], "seg": ["A", "B", "C"]}
    ).to_csv(input_path, index=False)

    dialog = BatchScoringDialog(session)
    worker = None
    try:
        dialog._input_edit.setText(str(input_path))
        dialog._output_edit.setText(str(output_path))
        assert dialog._run_button.isEnabled()

        with patch(
            "frontend_v3.scoring_dialogs.QMessageBox.information"
        ) as information:
            dialog._run_button.click()
            worker = dialog._worker
            assert worker is not None
            assert worker.wait(5000)
            QTest.qWait(100)

            information.assert_called_once()
            args = information.call_args.args
            assert args[0] is dialog
            assert args[1] == tr("batch_success_title")
            assert output_path.name in args[2]

        assert output_path.exists()
        assert len(pd.read_csv(output_path)) == 3
        assert not dialog._running
    finally:
        if worker is not None and worker.isRunning():
            assert worker.wait(5000)
        dialog._set_running(False)
        dialog.close()
        dialog.deleteLater()


def test_batch_dialog_missing_file_shows_critical(tmp_path):
    """N6: a real worker failure reaches the critical error message box."""
    _get_app()
    set_language("en")
    session, _ = _setup_session(tmp_path)
    missing_path = tmp_path / "missing_input.csv"
    output_path = tmp_path / "unused_output.csv"

    dialog = BatchScoringDialog(session)
    worker = None
    try:
        dialog._input_edit.setText(str(missing_path))
        dialog._output_edit.setText(str(output_path))
        assert dialog._run_button.isEnabled()

        with patch(
            "frontend_v3.scoring_dialogs.QMessageBox.critical"
        ) as critical:
            dialog._run_button.click()
            worker = dialog._worker
            assert worker is not None
            assert worker.wait(5000)
            QTest.qWait(100)

            critical.assert_called_once()
            args = critical.call_args.args
            assert args[0] is dialog
            assert args[1] == tr("msg_error_title")
            assert missing_path.name in args[2]

        assert not dialog._running
        assert dialog._run_button.isEnabled()
    finally:
        if worker is not None and worker.isRunning():
            assert worker.wait(5000)
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


def test_batch_worker_progress_signal_removed():
    """T7: the indeterminate progress bar has no dead worker signal."""
    assert "progress" not in BatchWorker.__dict__


def test_scoring_dialogs_retranslate():
    """Both dialogs switch language without changing canonical combo data."""
    _get_app()
    previous = get_language()
    set_language("en")
    session = Session()
    batch = BatchScoringDialog(session)
    champion = ChampionChallengerDialog(session)
    try:
        batch._policy_combo.setCurrentIndex(2)
        champion._policy_combo.setCurrentIndex(1)
        champion._engine_combo.setCurrentIndex(2)
        result = {
            "champion_fingerprint": "fp-champion",
            "challenger_fingerprint": "fp-challenger",
            "n_common_routed": 97,
            "metrics": (),
        }
        champion._on_worker_finished(result)
        batch_policy_en = batch._policy_combo.currentText()
        champion_policy_en = champion._policy_combo.currentText()

        set_language("es")
        language_bus.language_changed.emit("es")

        assert batch.windowTitle() == tr("batch_dialog_title", "es")
        assert batch._lbl_input.text() == tr("batch_input_label", "es")
        assert batch._lbl_output.text() == tr("batch_output_label", "es")
        assert batch._lbl_policy.text() == tr("scoring_policy_label", "es")
        assert batch._lbl_chunksize.text() == tr("batch_chunksize_label", "es")
        assert batch._lbl_rules.text() == tr("batch_include_rules_label", "es")
        assert batch._input_button.text() == tr("scoring_btn_browse", "es")
        assert batch._output_button.text() == tr("scoring_btn_browse", "es")
        assert batch._cancel_button.text() == tr("wizard_cancel", "es")
        assert batch._run_button.text() == tr("scoring_btn_execute", "es")
        assert batch._policy_combo.currentData() == "majority"
        assert batch._policy_combo.currentText() == tr(
            "unseen_policy_majority", "es"
        )
        assert batch._policy_combo.currentText() != batch_policy_en

        assert champion.windowTitle() == tr("cc_dialog_title", "es")
        assert champion._lbl_eval.text() == tr("cc_eval_label", "es")
        assert champion._lbl_engine.text() == tr("cc_engine_label", "es")
        assert champion._lbl_target.text() == tr("cc_target_label", "es")
        assert champion._lbl_weight.text() == tr("cc_weight_label", "es")
        assert champion._lbl_policy.text() == tr("scoring_policy_label", "es")
        assert champion._lbl_n_groups.text() == tr("cc_n_groups_label", "es")
        assert champion._lbl_params.text() == tr("cc_params_label", "es")
        assert champion._eval_button.text() == tr("scoring_btn_browse", "es")
        assert champion._cancel_button.text() == tr("wizard_cancel", "es")
        assert champion._run_button.text() == tr("scoring_btn_execute", "es")
        assert champion._policy_combo.currentData() == "error"
        assert champion._policy_combo.currentText() == tr(
            "unseen_policy_error", "es"
        )
        assert champion._policy_combo.currentText() != champion_policy_en
        assert champion._engine_combo.currentData() == "CHAID_EXHAUSTIVE"
        assert [
            champion._table.horizontalHeaderItem(column).text()
            for column in range(4)
        ] == [
            tr("cc_col_metric", "es"),
            tr("cc_col_champion", "es"),
            tr("cc_col_challenger", "es"),
            tr("cc_col_delta", "es"),
        ]
        assert champion._result_label.text() == tr(
            "cc_result_summary", "es"
        ).format(
            champion="fp-champion",
            challenger="fp-challenger",
            common=97,
        )

        set_language("en")
        language_bus.language_changed.emit("en")
        assert batch._policy_combo.currentData() == "majority"
        assert batch._policy_combo.currentText() == batch_policy_en
        assert champion._policy_combo.currentData() == "error"
        assert champion._policy_combo.currentText() == champion_policy_en
        assert champion._engine_combo.currentData() == "CHAID_EXHAUSTIVE"
    finally:
        batch.close()
        champion.close()
        batch.deleteLater()
        champion.deleteLater()
        set_language(previous)
        language_bus.language_changed.emit(previous)


def test_cc_dialog_engine_combo():
    """T8: all backend engines are offered in canonical order."""
    _get_app()
    set_language("en")
    dialog = ChampionChallengerDialog(Session())
    try:
        assert [
            dialog._engine_combo.itemData(index)
            for index in range(dialog._engine_combo.count())
        ] == ["CRT", "CHAID", "CHAID_EXHAUSTIVE", "QUEST"]
    finally:
        dialog.close()
        dialog.deleteLater()


def test_cc_dialog_n_groups_forwarded():
    """The spinbox and parsed overrides reach the worker unchanged."""
    _get_app()
    set_language("en")
    session = Session()
    dialog = ChampionChallengerDialog(session)
    try:
        assert dialog._n_groups_spin.minimum() == 3
        assert dialog._n_groups_spin.maximum() == 20
        assert dialog._n_groups_spin.value() == 10
        dialog._eval_edit.setText("evaluation.csv")
        dialog._n_groups_spin.setValue(7)
        dialog._params_edit.setText("max_depth=4,alpha=0.25,mode=fast")

        with patch("frontend_v3.scoring_dialogs.CCWorker") as worker_type:
            dialog._execute()

            worker_type.assert_called_once_with(
                session,
                "evaluation.csv",
                "CRT",
                None,
                None,
                "exclude",
                7,
                {"max_depth": 4, "alpha": 0.25, "mode": "fast"},
            )
            worker_type.return_value.start.assert_called_once_with()
    finally:
        dialog._set_running(False)
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
