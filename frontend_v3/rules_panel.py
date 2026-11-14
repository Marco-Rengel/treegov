"""Rules panel (Phase 3.12.d): classification rules of the active model.

Read-only Qt presentation of `Session.get_rules()` (Phase 3.12.a). The
panel never formats rules: the backend returns the exact Markdown / SQL /
Python text of the exporter, either for the whole tree (node_id=None) or
for a single node (that node becomes the root of the exported subtree).

Clean room: zero analytical logic; the widget only displays the text.

Retraduccion en caliente via `language_bus`: `MainWindow` es el unico
propietario de la conexion (la establece al construir la pestana y la
desconecta al cerrar), para que exista una sola suscripcion. El panel
expone `retranslate_ui()` y solo reasigna etiquetas estaticas; nunca
re-invoca el backend. El texto de las reglas lo generan los exportadores
y no se traduce (mismo contrato que Archivo > Exportar).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import tr

if TYPE_CHECKING:  # pragma: no cover - typing only
    from backend_v3.session_state import Session

__all__ = ["RulesPanel"]

_FORMATS: tuple[str, ...] = ("markdown", "sql", "python")

_DEFAULT_FILENAMES: dict[str, str] = {
    "markdown": "treegov_rules.md",
    "sql": "treegov_rules.sql",
    "python": "treegov_rules.py",
}


class RulesPanel(QWidget):
    """Pestana Reglas: selector de formato + caja de texto de solo lectura.

    `refresh(session, node_id)` es el unico punto de entrada de datos:
    cachea la sesion y el nodo, llama a `session.get_rules(format,
    node_id=node_id)` y puebla la caja. Si no hay modelo (o el backend
    devuelve None) se muestra el estado vacio con `rules_empty`.

    Cambiar el formato re-consulta el backend con el nodo cacheado. Los
    botones Copiar y Exportar operan sobre el texto ya mostrado, por lo
    que quedan deshabilitados mientras la caja esta vacia.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: Session | None = None
        self._node_id: int | None = None
        # Fase 3.12.d: el modo de gobernanza no altera el texto de las
        # reglas (diseno 3.12 §2.6); se guarda por consistencia con el
        # resto de paneles.
        self._mode: str = "BANKING"
        self._build_ui()
        self.retranslate_ui()
        self._refresh_text()

    # ---------------------------------------------------------- Public API

    def set_governance_mode(self, mode: str) -> None:
        """Fija el modo de gobernanza efectivo (no cambia el texto)."""
        self._mode = mode

    def refresh(self, session: Session | None, node_id: int | None) -> None:
        """Puebla la caja con las reglas del nodo (None = arbol completo)."""
        self._session = session
        self._node_id = None if node_id is None else int(node_id)
        self._refresh_text()

    def current_format(self) -> str:
        """Codigo del formato seleccionado ("markdown" | "sql" | "python")."""
        data = self._format_combo.currentData()
        return str(data) if data is not None else "markdown"

    def retranslate_ui(self) -> None:
        """Reasigna los textos estaticos (idioma en caliente)."""
        self._title.setText(tr("rules_title"))
        self._format_label.setText(tr("rules_format_label"))
        self._refresh_button.setText(tr("rules_btn_refresh"))
        self._copy_button.setText(tr("rules_btn_copy"))
        self._export_button.setText(tr("rules_btn_export"))
        labels = {
            "markdown": tr("rules_format_markdown"),
            "sql": tr("rules_format_sql"),
            "python": tr("rules_format_python"),
        }
        for index in range(self._format_combo.count()):
            code = self._format_combo.itemData(index)
            self._format_combo.setItemText(index, labels.get(code, str(code)))
        self._update_node_label()
        if not self._text.toPlainText():
            self._empty_label.setText(tr("rules_empty"))

    # ------------------------------------------------------------ Internals

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._title = QLabel(self)
        self._title.setObjectName("panelTitle")
        layout.addWidget(self._title)

        top = QHBoxLayout()
        self._format_label = QLabel(self)
        top.addWidget(self._format_label)
        self._format_combo = QComboBox(self)
        self._format_combo.setObjectName("rulesFormat")
        for code in _FORMATS:
            self._format_combo.addItem("", userData=code)
        top.addWidget(self._format_combo)
        top.addSpacing(12)
        self._node_label = QLabel(self)
        self._node_label.setObjectName("rulesNodeLabel")
        top.addWidget(self._node_label)
        top.addStretch(1)

        self._refresh_button = QPushButton(self)
        self._refresh_button.setObjectName("rulesRefresh")
        top.addWidget(self._refresh_button)
        self._copy_button = QPushButton(self)
        self._copy_button.setObjectName("rulesCopy")
        top.addWidget(self._copy_button)
        self._export_button = QPushButton(self)
        self._export_button.setObjectName("rulesExport")
        top.addWidget(self._export_button)
        layout.addLayout(top)

        self._empty_label = QLabel(self)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        self._text = QTextEdit(self)
        self._text.setObjectName("rulesText")
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._text.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._text.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._text.setFont(font)
        layout.addWidget(self._text, 1)

        self._format_combo.currentIndexChanged.connect(
            self._on_format_changed
        )
        self._refresh_button.clicked.connect(self._refresh_text)
        self._copy_button.clicked.connect(self._on_copy_clicked)
        self._export_button.clicked.connect(self._on_export_clicked)

    def _update_node_label(self) -> None:
        value = (
            tr("rules_node_all")
            if self._node_id is None
            else f"#{self._node_id}"
        )
        self._node_label.setText(f"{tr('rules_node_filter')} {value}")

    def _refresh_text(self) -> None:
        """Re-consulta `Session.get_rules` y repinta el estado."""
        self._update_node_label()
        text = None
        if self._session is not None:
            try:
                text = self._session.get_rules(
                    self.current_format(), node_id=self._node_id
                )
            except Exception:
                logging.getLogger(__name__).exception(
                    "[rules_panel] fallo al obtener las reglas"
                )
                text = None
        # El contrato del backend es str | None; cualquier otro tipo se
        # trata como estado vacio (defensa de presentacion).
        if not isinstance(text, str) or not text:
            self._text.clear()
            self._text.setVisible(False)
            self._empty_label.setText(tr("rules_empty"))
            self._empty_label.setVisible(True)
            self._copy_button.setEnabled(False)
            self._export_button.setEnabled(False)
            return
        self._empty_label.setVisible(False)
        self._text.setVisible(True)
        self._text.setPlainText(text)
        self._text.moveCursor(QTextCursor.MoveOperation.Start)
        self._copy_button.setEnabled(True)
        self._export_button.setEnabled(True)

    def _on_format_changed(self, _index: int) -> None:
        self._refresh_text()

    def _on_copy_clicked(self) -> None:
        QApplication.clipboard().setText(self._text.toPlainText())

    def _on_export_clicked(self) -> None:
        text = self._text.toPlainText()
        if not text:
            return
        filename = _DEFAULT_FILENAMES.get(
            self.current_format(), "treegov_rules.txt"
        )
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            tr("rules_export_title"),
            filename,
            "Text files (*.txt);;Markdown (*.md);;SQL (*.sql);;"
            "Python (*.py);;All files (*)",
        )
        if not path:
            return
        self._export_to_file(path)

    def _export_to_file(self, path: str) -> bool:
        """Escribe el texto mostrado en `path` (UTF-8) y avisa al analista."""
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._text.toPlainText())
        except OSError as exc:
            QMessageBox.warning(
                self,
                tr("rules_export_title"),
                tr("rules_export_error").format(error=exc),
            )
            return False
        QMessageBox.information(
            self,
            tr("rules_export_title"),
            tr("rules_export_saved").format(path=path),
        )
        return True
