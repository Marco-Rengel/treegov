"""Tests del Manual Override Log (frontend_v3/manual_override_dialog.py +
boton "Ver Auditoria" del HUD en frontend_v3/main_window.py, Fase
3.11.d.3). Dual: pytest o python directo.

    .venv\\Scripts\\python -m pytest tests/test_manual_override.py -v
    .venv\\Scripts\\python tests\\test_manual_override.py

Headless: QT_QPA_PLATFORM=offscreen por defecto (setdefault). Los tests
de integracion usan un CSV sintetico en tempfile; NADA se escribe en
data/ (zona protegida).
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402  (tests/ SI puede importar)
import pandas as pd  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import set_language  # noqa: E402
from frontend_v3.main_window import MainWindow  # noqa: E402
from frontend_v3.manual_override_dialog import (  # noqa: E402
    ManualOverrideDialog,
)


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _make_csv(path: Path) -> Path:
    """120 filas; y = 1_{edad >= 40} -> raiz con split garantizado."""
    edad = np.tile(np.arange(20, 60), 3)
    seg = np.tile(["a", "b", "c"], 40)
    df = pd.DataFrame({
        "edad": edad, "seg": seg, "default": (edad >= 40).astype(int),
    })
    df.to_csv(path, index=False)
    return path


def _cfg() -> dict:
    return {
        "engine": "CRT",
        "target": "default",
        "predictors": ["edad", "seg"],
        "target_class": 1,
        "class_labels": {0: "Non-event", 1: "Event"},
        "weight_col": None,
        "population_col": None,
        "population_ok_values": (),
        "train_frac": 0.7,
        "seed": 42,
        "max_depth": 4,
        "min_child_size": 5,
        "min_child_weight": None,
        "governance_mode": "BANKING",
        "apply_jeffreys": True,
        "pd_floor": 0.0005,
    }


def test_manual_override_dialog_empty_and_data():
    """Construccion del dialogo: vacio (label) y con datos (tabla)."""
    _get_app()
    dlg = ManualOverrideDialog()
    # vacio: etiqueta visible, tabla oculta y copia deshabilitada
    dlg.set_data(())
    assert dlg._table.rowCount() == 0
    assert dlg._table.isHidden()
    assert not dlg._lbl_empty.isHidden()
    assert not dlg._btn_copy.isEnabled()

    # con datos: una fila por intervencion, 5 columnas en orden
    overrides = (
        ("2026-10-25T10:00:00", 0, "prune_branch", "", "abc123", "abc123-p1"),
    )
    dlg.set_data(overrides)
    assert dlg._table.rowCount() == 1
    assert dlg._table.item(0, 0).text() == "2026-10-25T10:00:00"
    assert dlg._table.item(0, 1).text() == "0"
    assert dlg._table.item(0, 2).text() == "prune_branch"
    assert dlg._table.item(0, 3).text() == "abc123"
    assert dlg._table.item(0, 4).text() == "abc123-p1"
    assert not dlg._table.isHidden()
    assert dlg._lbl_empty.isHidden()
    assert dlg._btn_copy.isEnabled()
    dlg.close()
    dlg.deleteLater()


def test_view_audit_button_flow():
    """El boton Ver Auditoria se habilita tras entrenar y abre el
    dialogo con el contenido de SessionState.manual_overrides."""
    with tempfile.TemporaryDirectory() as td:
        csv_path = _make_csv(Path(td) / "mini.csv")
        _get_app()
        w = MainWindow()
        set_language("en")
        w.retranslate_ui()
        assert w._load_dataset_path(str(csv_path)) is True
        # sin modelo: deshabilitado
        assert not w._hud_btn_view_audit.isEnabled()

        w._on_wizard_finished(_cfg())
        assert w._session.state.tree is not None
        assert len(w._session.state.tree.nodes) > 1
        # tras entrenar: habilitado
        assert w._hud_btn_view_audit.isEnabled()

        # intervenir la raiz -> un registro en el Manual Override Log
        w._session.intervene_node(0, "prune_branch")
        assert len(w._session.state.manual_overrides) == 1

        vistos = []
        with patch.object(
            ManualOverrideDialog, "exec", lambda self: vistos.append(self)
        ):
            w._hud_btn_view_audit.click()
        assert len(vistos) == 1
        assert vistos[0]._table.rowCount() == 1
        assert vistos[0]._table.item(0, 2).text() == "prune_branch"
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
    print(f"\nOK - {len(tests)} tests superados")
