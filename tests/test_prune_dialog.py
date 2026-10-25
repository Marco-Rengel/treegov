"""Tests for PruneDialog (Phase 3.9 GUI). Dual: pytest or plain python.

    .venv\\Scripts\\python -m pytest tests/test_prune_dialog.py -v
    .venv\\Scripts\\python tests/test_prune_dialog.py

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so a
real display session keeps its platform).
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import language_bus, tr  # noqa: E402
from frontend_v3.prune_dialog import PruneDialog  # noqa: E402
from frontend_v3.reports_panel import ReportsPanel  # noqa: E402


def _get_app() -> QApplication:
    """Reuse the running QApplication or create one (Qt is a singleton)."""
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


class _FakeSession:
    """Stub de Session para el dialogo de poda (sin backend real).

    Expone el contrato que PruneDialog consume: get_prune_sequence()
    (DTO plano con claves alpha / n_leaves / r_subtree) y prune(alpha).
    """

    def __init__(self, sequence):
        self._sequence = sequence
        self.pruned_with = None

    def get_prune_sequence(self):
        return list(self._sequence)

    def prune(self, alpha):
        self.pruned_with = alpha


_SEQUENCE = [
    {"alpha": 0.0, "n_leaves": 5, "r_subtree": 10.0},
    {"alpha": 0.05, "n_leaves": 2, "r_subtree": 40.0},
    {"alpha": 0.5, "n_leaves": 1, "r_subtree": 100.0},
]


def test_prune_dialog_copy_tsv_to_clipboard():
    """REGLA CRITICA 4.1.1 del Design System: la tabla del PruneDialog
    soporta Ctrl+C -> TSV (cableado 25/10/2026 via el helper generico
    de ReportsPanel, ahora staticmethod)."""
    _get_app()
    dlg = PruneDialog(_FakeSession(_SEQUENCE), language_bus)
    # la tabla se puebla con la secuencia completa
    assert dlg._table.rowCount() == 3
    assert dlg._table.columnCount() == 3
    # el shortcut Ctrl+C existe, vive sobre la tabla y con el contexto
    # acotado (no secuestra el Ctrl+C de otros widgets)
    assert dlg._copy_shortcut.parent() is dlg._table

    # sin seleccion previa: copia toda la tabla con cabeceras
    dlg._table.clearSelection()
    ReportsPanel._copy_selection_to_clipboard(dlg._table)
    lines = QApplication.clipboard().text().split("\n")
    assert len(lines) == 4  # cabecera + 3 filas
    header = lines[0].split("\t")
    assert header == [
        tr("prune_col_alpha"),
        tr("prune_col_terminal_nodes"),
        tr("prune_col_error"),
    ]
    assert "Terminal" in lines[0]          # EN/ES: nunca "leaf/hoja"
    assert lines[1].split("\t") == ["0", "5", "10"]
    assert lines[2].split("\t") == ["0.05", "2", "40"]
    assert lines[3].split("\t") == ["0.5", "1", "100"]
    dlg.close()
    dlg.deleteLater()


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
