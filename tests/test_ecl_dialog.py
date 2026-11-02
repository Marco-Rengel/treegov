"""Headless GUI tests for the Phase 7 ECL dialog and menu action."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend_v3.session_state import Session  # noqa: E402
from backend_v3.types import PredictorType, TargetType  # noqa: E402
from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.ecl_dialog import ECLDialog  # noqa: E402
from frontend_v3.main_window import MainWindow  # noqa: E402


def _get_app() -> QApplication:
    """Reuse the QApplication singleton or create it for headless tests."""
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _setup_session(tmp_path) -> tuple[Session, object]:
    """Create a valid scoring CSV and a session with a trained tree."""
    csv_path = tmp_path / "ecl_scoring.csv"
    pd.DataFrame(
        {
            "exposure_id": ["A", "B", "C", "D", "E", "F"],
            "ead": [1000, 2000, 500, 1200, 800, 600],
            "lgd": [0.45, 0.45, 0.45, 0.40, 0.50, 0.45],
            "days_past_due": [0, 45, 100, 0, 40, 95],
            "pd_initial": [0.02, 0.02, 0.05, 0.01, 0.02, 0.04],
            "pd_current": [0.02, 0.05, 0.20, 0.01, 0.05, 0.15],
            "pd_lifetime": [0.10, 0.20, 0.80, 0.08, 0.20, 0.70],
            "age": [20, 25, 30, 50, 55, 60],
            "target": [0, 0, 0, 1, 1, 1],
        }
    ).to_csv(csv_path, index=False)

    session = Session()
    session.load_dataset(str(csv_path))
    session.fix_spec(
        target="target",
        spec={"age": PredictorType.CONTINUOUS},
        target_class=1,
        class_labels={0: "Non-event", 1: "Event"},
    )
    session.partition(train_frac=0.75, seed=42)
    session.train(
        "CRT",
        target_type=TargetType.BINARY,
        max_depth=2,
        min_child_size=1,
    )
    return session, csv_path


def test_ecl_dialog_creation(tmp_path):
    """The calculate action is enabled only after entering a CSV path."""
    _get_app()
    session, csv_path = _setup_session(tmp_path)
    dialog = ECLDialog(session)
    try:
        assert not dialog._calculate_button.isEnabled()
        dialog._csv_edit.setText(str(csv_path))
        assert dialog._calculate_button.isEnabled()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_ecl_dialog_table_population(tmp_path):
    """The result slot renders five ordered and formatted summary rows."""
    _get_app()
    session, _ = _setup_session(tmp_path)
    dialog = ECLDialog(session)
    try:
        dialog._on_finished(
            {
                "total_ecl_12m": 99.0,
                "total_ecl_lifetime": 405.0,
                "stage_counts": (1, 2, 3),
            }
        )

        assert dialog._table.rowCount() == 5
        assert dialog._table.columnCount() == 2
        assert not dialog._table.isHidden()
        assert dialog._calculate_button.isHidden()
        assert [dialog._table.item(row, 0).text() for row in range(5)] == [
            "ECL 12m",
            "ECL Lifetime",
            "Etapa 1",
            "Etapa 2",
            "Etapa 3",
        ]
        assert [dialog._table.item(row, 1).text() for row in range(5)] == [
            "99.00",
            "405.00",
            "1",
            "2",
            "3",
        ]
    finally:
        dialog.close()
        dialog.deleteLater()


def test_mainwindow_ecl_action(tmp_path):
    """The ECL menu action becomes enabled with a trained model."""
    _get_app()
    session, _ = _setup_session(tmp_path)
    window = MainWindow(session=session)
    try:
        window._refresh_session_indicator()
        assert session.state.tree is not None
        assert window._act_ecl.isEnabled()
    finally:
        window.close()
        window.deleteLater()
