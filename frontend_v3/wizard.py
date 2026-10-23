"""Transactional 4-step model wizard (TreeGov GUI, Phase 2.1).

Clean room: this module receives the dataset profile as PLAIN Python data
(columns tuple + types dict of PredictorType.name strings) and emits a plain
dict on finish. It never sees Session, the engines, pandas or numpy; the
MainWindow orchestrates the backend calls.

Every visible string goes through frontend_v3.i18n.tr; live retranslation
arrives via language_bus (the wizard is NON-modal precisely so the user can
switch language/theme from the main menu while it is open).

Step contents follow docs/roadmap.md Phase 2.1 and the approved design
(engine subtitles carry the academic citation; Step 4 exposes the
Governance Mode BANKING/RESEARCH of backend_v3.types).
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from frontend_v3.i18n import language_bus, tr

_PREFIX = {"NOMINAL": "NOM", "ORDINAL": "ORD", "CONTINUOUS": "CONT"}

_ENGINES: tuple[tuple[str, str], ...] = (
    ("CRT", "step1_desc_crt"),
    ("CHAID", "step1_desc_chaid"),
    ("CHAID_EXHAUSTIVE", "step1_desc_chaid_exhaustive"),
    ("QUEST", "step1_desc_quest"),
)
_ENGINE_LABELS = {
    "CRT": "C&RT",
    "CHAID": "CHAID",
    "CHAID_EXHAUSTIVE": "CHAID (Exhaustive)",
    "QUEST": "QUEST",
}


# ---------------------------------------------------------------------------
# Step 1 - engine
# ---------------------------------------------------------------------------


class EnginePage(QWizardPage):
    """Engine selection (4 exclusive radio buttons; default C&RT)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._radios: dict[str, QRadioButton] = {}
        self._descs: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)
        for engine, desc_key in _ENGINES:
            radio = QRadioButton(_ENGINE_LABELS[engine])  # proper noun, fixed
            desc = QLabel()
            desc.setIndent(24)
            desc.setEnabled(False)  # descriptive text, visually muted
            self._group.addButton(radio)
            self._radios[engine] = radio
            self._descs[engine] = desc
            layout.addWidget(radio)
            layout.addWidget(desc)
        layout.addStretch(1)
        self._radios["CRT"].setChecked(True)  # most robust/generic default

    def selected_engine(self) -> str:
        for engine, radio in self._radios.items():
            if radio.isChecked():
                return engine
        return "CRT"  # unreachable (default), defensive

    def isComplete(self) -> bool:
        return True  # the C&RT default always makes this step complete

    def retranslate_ui(self) -> None:
        self.setTitle(tr("step1_title"))
        self.setSubTitle(tr("step1_subtitle"))
        for engine, desc_key in _ENGINES:
            self._descs[engine].setText(tr(desc_key))


# ---------------------------------------------------------------------------
# Step 2 - predictors and target
# ---------------------------------------------------------------------------


class PredictorsPage(QWizardPage):
    """Target combo + dual predictor lists (available / selected).

    CHAID mirror rule (backend contract, chaid_engine.py): CHAID engines
    reject CONTINUOUS predictors, so [CONT] items are disabled here when a
    CHAID engine was selected in Step 1.

    Phase 3.2.h: weight-column combo. Mirror rule: the column chosen as
    weight column disappears from the available predictor list (and is
    moved back if deselected). A non-blocking amber warning is shown when
    the chosen column has invalid values (zero, negative or missing);
    validity is delegated to the optional `weight_validator` callback
    (clean-room: the wizard never touches the DataFrame).
    """

    def __init__(
        self,
        columns: tuple[str, ...],
        types: dict[str, str],
        *,
        target_provider: Callable[[str], dict] | None = None,
        weight_validator: Callable[[str], bool] | None = None,
        population_provider: Callable[[str], dict] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not columns:
            raise ValueError("PredictorsPage requires at least one column")
        self._columns = columns
        self._types = types
        self._target_provider = target_provider
        self._weight_validator = weight_validator
        self._population_provider = population_provider

        layout = QVBoxLayout(self)

        target_row = QHBoxLayout()
        self._lbl_target = QLabel()
        self._combo_target = QComboBox()
        self._combo_target.setObjectName("comboTarget")
        # Phase 3.7.e (pre-1.0.0rc1): H2 — do NOT default to the first CSV
        # column. Add an explicit placeholder first; the analyst must choose
        # the target explicitly. This eliminates the reported defect where
        # the wizard opened with a continuous column as target (unusable for
        # CHAID and semantically wrong for classification).
        self._combo_target.addItem("", userData=None)
        for col in columns:
            self._combo_target.addItem(col, userData=col)
        target_row.addWidget(self._lbl_target)
        target_row.addWidget(self._combo_target, 1)
        layout.addLayout(target_row)

        # --- Phase 3.2.h: weight column row (debajo del target) ---
        weight_row = QHBoxLayout()
        self._lbl_weight = QLabel()
        self._combo_weight = QComboBox()
        self._combo_weight.setObjectName("comboWeight")
        self._combo_weight.addItem("", userData=None)  # retraducido
        for col in columns:
            self._combo_weight.addItem(col, userData=col)
        weight_row.addWidget(self._lbl_weight)
        weight_row.addWidget(self._combo_weight, 1)
        layout.addLayout(weight_row)

        self._lbl_weight_warning = QLabel()
        self._lbl_weight_warning.setObjectName("lblWeightWarning")
        self._lbl_weight_warning.setWordWrap(True)
        self._lbl_weight_warning.setVisible(False)
        layout.addWidget(self._lbl_weight_warning)

        self._lbl_weight_hint = QLabel()
        self._lbl_weight_hint.setWordWrap(True)
        layout.addWidget(self._lbl_weight_hint)

        # --- Phase 3.3.d: population column row + OK values table ---
        population_row = QHBoxLayout()
        self._lbl_population = QLabel()
        self._combo_population = QComboBox()
        self._combo_population.setObjectName("comboPopulation")
        self._combo_population.addItem("", userData=None)  # retraducido
        for col in columns:
            self._combo_population.addItem(col, userData=col)
        population_row.addWidget(self._lbl_population)
        population_row.addWidget(self._combo_population, 1)
        layout.addLayout(population_row)

        self._lbl_population_warning = QLabel()
        self._lbl_population_warning.setObjectName("lblPopulationWarning")
        self._lbl_population_warning.setWordWrap(True)
        self._lbl_population_warning.setVisible(False)
        layout.addWidget(self._lbl_population_warning)

        self._lbl_population_hint = QLabel()
        self._lbl_population_hint.setWordWrap(True)
        layout.addWidget(self._lbl_population_hint)

        self._group_population = QGroupBox()
        self._group_population.setObjectName("groupPopulationOK")
        self._group_population.setVisible(False)
        gpop_layout = QVBoxLayout(self._group_population)
        self._lbl_population_ok_hint = QLabel()
        self._lbl_population_ok_hint.setWordWrap(True)
        gpop_layout.addWidget(self._lbl_population_ok_hint)
        self._tbl_population = QTableWidget(0, 3)
        self._tbl_population.setObjectName("tblPopulation")
        self._tbl_population.setHorizontalHeaderLabels(["", "", ""])
        header_p = self._tbl_population.horizontalHeader()
        header_p.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tbl_population.verticalHeader().setVisible(False)
        self._tbl_population.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        gpop_layout.addWidget(self._tbl_population)
        layout.addWidget(self._group_population)

        self._group_class = QGroupBox()
        self._group_class.setObjectName("groupClassOfInterest")
        gclass_layout = QVBoxLayout(self._group_class)

        self._lbl_class_hint = QLabel()
        gclass_layout.addWidget(self._lbl_class_hint)

        self._tbl_classes = QTableWidget(0, 4)
        self._tbl_classes.setObjectName("tblClasses")
        self._tbl_classes.setHorizontalHeaderLabels(
            ["", "", "", ""]  # se retraduce en retranslate_ui
        )
        header = self._tbl_classes.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tbl_classes.verticalHeader().setVisible(False)
        self._tbl_classes.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self._tbl_classes.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._tbl_classes.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        gclass_layout.addWidget(self._tbl_classes)

        self._lbl_warning = QLabel()
        self._lbl_warning.setObjectName("lblClassWarning")
        self._lbl_warning.setWordWrap(True)
        self._lbl_warning.setVisible(False)  # se muestra si aplica
        gclass_layout.addWidget(self._lbl_warning)

        layout.addWidget(self._group_class)

        lists_row = QHBoxLayout()
        left_box = QVBoxLayout()
        self._lbl_available = QLabel()
        self._lst_available = QListWidget()
        self._lst_available.setObjectName("lstAvailable")
        left_box.addWidget(self._lbl_available)
        left_box.addWidget(self._lst_available)
        lists_row.addLayout(left_box, 1)

        btns = QVBoxLayout()
        self._btn_add = QPushButton("→")
        self._btn_add.setToolTip("Move selected")
        self._btn_remove = QPushButton("←")
        self._btn_remove.setToolTip("Move back selected")
        self._btn_add_all = QPushButton("⇒")
        self._btn_add_all.setToolTip("Move all")
        self._btn_remove_all = QPushButton("⇐")
        self._btn_remove_all.setToolTip("Move back all")
        for b in (self._btn_add, self._btn_remove,
                  self._btn_add_all, self._btn_remove_all):
            btns.addWidget(b)
        btns.addStretch(1)
        lists_row.addLayout(btns)

        right_box = QVBoxLayout()
        self._lbl_selected = QLabel()
        self._lst_selected = QListWidget()
        self._lst_selected.setObjectName("lstSelected")
        right_box.addWidget(self._lbl_selected)
        right_box.addWidget(self._lst_selected)
        lists_row.addLayout(right_box, 1)
        layout.addLayout(lists_row, 1)

        self._lbl_hint = QLabel()
        self._lbl_chaid_note = QLabel()
        layout.addWidget(self._lbl_hint)
        layout.addWidget(self._lbl_chaid_note)

        self._btn_add.clicked.connect(lambda: self._move(False, False))
        self._btn_remove.clicked.connect(lambda: self._move(True, False))
        self._btn_add_all.clicked.connect(lambda: self._move(False, True))
        self._btn_remove_all.clicked.connect(lambda: self._move(True, True))
        self._combo_target.currentIndexChanged.connect(self._on_target_change)
        self._combo_weight.currentIndexChanged.connect(self._on_weight_change)
        self._combo_population.currentIndexChanged.connect(
            self._on_population_change
        )

        self._on_weight_change(0)  # incluye el fill inicial de disponibles
        self._on_population_change(0)

    # --- data access -----------------------------------------------------

    def target(self) -> str:
        return str(self._combo_target.currentData())

    def weight_col(self) -> str | None:
        """Columna de pesos seleccionada, o None (Phase 3.2.h)."""
        data = self._combo_weight.currentData()
        return None if data is None else str(data)

    def population_col(self) -> str | None:
        """Columna de población seleccionada, o None (Phase 3.3.d)."""
        data = self._combo_population.currentData()
        return None if data is None else str(data)

    def population_ok_values(self) -> tuple[str, ...]:
        """Whitelist de valores marcados como OK en la tabla de población.

        Devuelve tupla vacía si no hay columna de población declarada.
        """
        if self.population_col() is None:
            return ()
        return tuple(
            r["value"] for r in self._population_rows if r["checkbox"].isChecked()
        )

    def selected_predictors(self) -> list[str]:
        return [
            str(self._lst_selected.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self._lst_selected.count())
        ]

    def target_class(self):
        """Valor de la clase de interés seleccionada, o None."""
        if self._tbl_classes.rowCount() == 0:
            return None
        radio_group = getattr(self, "_interest_group", None)
        if radio_group is None:
            return None
        for r in getattr(self, "_class_rows", []):
            if r["radio"].isChecked():
                return r["value"]
        return None

    def class_labels(self) -> dict:
        """Mapping {valor: etiqueta_humana} tal como está editado."""
        return {
            r["value"]: r["label_edit"].text()
            for r in getattr(self, "_class_rows", [])
        }

    # --- internals ---------------------------------------------------------

    def _make_item(self, col: str, enabled: bool = True) -> QListWidgetItem:
        item = QListWidgetItem(f"[{_PREFIX[self._types[col]]}] {col}")
        item.setData(Qt.ItemDataRole.UserRole, col)
        if not enabled:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled
                          & ~Qt.ItemFlag.ItemIsSelectable)
        return item

    def _is_chaid(self) -> bool:
        wiz = self.wizard()
        return bool(wiz and wiz.selected_engine().startswith("CHAID"))

    def _on_target_change(self, _index: int) -> None:
        target = self.target()
        weight = self.weight_col()
        pop = self.population_col()
        # Si el target o la columna de poblacion estaban como predictores
        # seleccionados, devolverlos a disponibles antes de recomputar.
        for i in range(self._lst_selected.count() - 1, -1, -1):
            item = self._lst_selected.item(i)
            col = item.data(Qt.ItemDataRole.UserRole)
            if col == target or col == pop:
                self._lst_selected.takeItem(i)
                self._lst_available.addItem(item)
        # available = columns - target - selected - weight_col - population_col
        in_selected = set(self.selected_predictors())
        self._lst_available.clear()
        for col in self._columns:
            if (col == target or col == weight or col == pop
                    or col in in_selected):
                continue
            disabled = self._is_chaid() and self._types[col] == "CONTINUOUS"
            self._lst_available.addItem(self._make_item(col, not disabled))
        self._refresh_class_table()
        self.completeChanged.emit()

    def _on_weight_change(self, _index: int) -> None:
        """Regla espejo (3.2.h): la columna de pesos sale de predictores."""
        weight = self.weight_col()
        if weight is not None:
            # Si era predictor seleccionado, devolverla a disponibles antes
            # de recomputar (el filtro de _on_target_change la excluye).
            for i in range(self._lst_selected.count() - 1, -1, -1):
                item = self._lst_selected.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == weight:
                    self._lst_selected.takeItem(i)
                    self._lst_available.addItem(item)
        self._on_target_change(self._combo_target.currentIndex())
        self._validate_weight_column()
        self.completeChanged.emit()

    def _validate_weight_column(self) -> bool:
        """Aviso ambar NO bloqueante si la columna tiene valores invalidos.

        Sin callback `weight_validator` la columna se asume valida (sala
        limpia: el wizard no toca el DataFrame; MainWindow inyecta la
        validacion contra el dataset real).
        """
        weight = self.weight_col()
        if weight is None:
            self._lbl_weight_warning.setVisible(False)
            return True
        valido = True
        if self._weight_validator is not None:
            try:
                valido = bool(self._weight_validator(weight))
            except (ValueError, RuntimeError, KeyError):
                valido = False
        self._lbl_weight_warning.setVisible(not valido)
        return valido

    def _on_population_change(self, _index: int) -> None:
        """Regla espejo: la columna de población sale de predictores
        disponibles y de la lista de pesos."""
        pop = self.population_col()
        # Si era predictor seleccionado, devolverla a disponibles.
        if pop is not None:
            for i in range(self._lst_selected.count() - 1, -1, -1):
                item = self._lst_selected.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == pop:
                    self._lst_selected.takeItem(i)
                    self._lst_available.addItem(item)
        # Si era la columna de pesos, resetear el combo de pesos.
        if pop is not None and self.weight_col() == pop:
            self._combo_weight.setCurrentIndex(0)
        self._on_target_change(self._combo_target.currentIndex())
        self._refresh_population_table()
        self.completeChanged.emit()

    def _refresh_population_table(self) -> None:
        """Puebla la tabla de OK values desde population_provider.

        Sin provider o sin columna declarada: tabla vacía y grupo oculto.
        Con provider: una fila por valor observado, con checkbox de OK
        marcado por defecto (el analista desmarca los no-OK).
        """
        self._tbl_population.setRowCount(0)
        self._population_rows: list[dict] = []
        pop = self.population_col()
        if pop is None or self._population_provider is None:
            self._group_population.setVisible(False)
            self._lbl_population_warning.setVisible(False)
            return
        try:
            dto = self._population_provider(pop)
        except (ValueError, RuntimeError, KeyError):
            self._group_population.setVisible(False)
            return
        if not dto.get("exists"):
            self._group_population.setVisible(False)
            return
        values = dto.get("values") or ()
        # Aviso ámbar si hay NaN entre los valores observados
        has_nan = any(v == "<NaN>" for v, _ in values)
        self._lbl_population_warning.setVisible(has_nan)
        # Poblar tabla
        self._tbl_population.setRowCount(len(values))
        for row_idx, (val, count) in enumerate(values):
            item_val = QTableWidgetItem(val)
            item_cnt = QTableWidgetItem(str(count))
            self._tbl_population.setItem(row_idx, 0, item_val)
            self._tbl_population.setItem(row_idx, 1, item_cnt)
            chk = QCheckBox()
            chk.setObjectName(f"chkPop_{row_idx}")
            chk.setChecked(True)  # por defecto OK
            self._tbl_population.setCellWidget(row_idx, 2, chk)
            self._population_rows.append(
                {"value": val, "count": count, "checkbox": chk}
            )
        self._group_population.setVisible(True)

    def _refresh_class_table(self) -> None:
        """Repobla la tabla de clases desde el target_provider.

        Sin callback (None): tabla vacía, sin warning.
        Con callback: una fila por clase, con QLineEdit editable para
        la etiqueta humana, el valor original y el count. La última
        fila queda seleccionada por default (default neutral; el
        analista debe elegir explícitamente en cualquier caso).
        Warning amber si la clase seleccionada es la mayoritaria y
        NO hay empate entre clases.
        """
        self._tbl_classes.setRowCount(0)
        self._lbl_warning.setVisible(False)
        if self._target_provider is None:
            return
        try:
            counts = self._target_provider(self.target())
        except (ValueError, RuntimeError):
            # Target no resuelto o dataset ausente: tabla vacía sin
            # error visible; el wizard no debe romper por esto.
            return
        if not counts:
            return

        # Orden ascendente por valor, como describe_target.
        items = sorted(counts.items(), key=lambda kv: kv[0])

        # Grupo exclusivo para el radio de "clase de interés".
        self._interest_group = QButtonGroup(self)
        self._interest_group.setExclusive(True)

        self._tbl_classes.setRowCount(len(items))
        max_count = max(c for _, c in items)
        # ¿Hay empate entre clases? Si todas las clases con count
        # máximo son iguales -> no hay "mayoría" clara.
        n_mayoritarias = sum(1 for _, c in items if c == max_count)
        hay_mayoria_clara = n_mayoritarias == 1 and len(items) >= 2

        ultimo_radio: QRadioButton | None = None
        self._class_rows: list[dict] = []

        for row_idx, (valor, count) in enumerate(items):
            # Columna 0: etiqueta humana (editable).
            edit = QLineEdit(str(valor))
            self._tbl_classes.setCellWidget(row_idx, 0, edit)

            # Columna 1: valor original (read-only).
            item_val = QTableWidgetItem(str(valor))
            item_val.setFlags(
                item_val.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self._tbl_classes.setItem(row_idx, 1, item_val)

            # Columna 2: count (read-only).
            item_cnt = QTableWidgetItem(str(count))
            item_cnt.setFlags(
                item_cnt.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self._tbl_classes.setItem(row_idx, 2, item_cnt)

            # Columna 3: radio de interés.
            radio = QRadioButton()
            radio.setObjectName(f"radioInterest_{valor}")
            radio.toggled.connect(self._on_interest_toggled)
            self._interest_group.addButton(radio)
            self._tbl_classes.setCellWidget(row_idx, 3, radio)

            self._class_rows.append({
                "value": valor,
                "label_edit": edit,
                "count": count,
                "radio": radio,
            })
            ultimo_radio = radio

        # Default: última fila seleccionada (neutral; el analista
        # debe elegir explícitamente).
        if ultimo_radio is not None:
            ultimo_radio.setChecked(True)
        # Guardar la info de mayoría para _on_interest_toggled.
        self._class_majority = max_count if hay_mayoria_clara else None

    def _on_interest_toggled(self, _checked: bool) -> None:
        """Muestra u oculta el warning de clase mayoritaria."""
        majority = getattr(self, "_class_majority", None)
        if majority is None:
            self._lbl_warning.setVisible(False)
            return
        rows = getattr(self, "_class_rows", [])
        for r in rows:
            if r["radio"].isChecked():
                if r["count"] == majority:
                    self._lbl_warning.setVisible(True)
                else:
                    self._lbl_warning.setVisible(False)
                return
        self._lbl_warning.setVisible(False)

    def _move(self, back: bool, all_items: bool) -> None:
        src = self._lst_selected if back else self._lst_available
        dst = self._lst_available if back else self._lst_selected
        rows = (
            range(src.count()) if all_items
            else sorted((src.row(i) for i in src.selectedItems()), reverse=True)
        )
        moved = False
        for row in list(rows):
            item = src.item(row)
            if item is None:
                continue
            # CHAID mirror rule: a disabled [CONT] item may only leave
            # "selected" (moving INTO selected is blocked by its flags)
            if not back and not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
                continue
            src.takeItem(src.row(item))
            dst.addItem(item)
            moved = True
        if moved:
            self.completeChanged.emit()

    # --- Qt overrides ------------------------------------------------------

    def initializePage(self) -> None:
        """Apply the CHAID mirror rule when entering the step."""
        if self._is_chaid():
            # disabled [CONT] items cannot stay selected either
            for i in range(self._lst_selected.count() - 1, -1, -1):
                item = self._lst_selected.item(i)
                col = item.data(Qt.ItemDataRole.UserRole)
                if self._types[col] == "CONTINUOUS":
                    self._lst_selected.takeItem(i)
                    self._lst_available.addItem(item)
        self._on_target_change(self._combo_target.currentIndex())

    def isComplete(self) -> bool:
        # Phase 3.7.e (pre-1.0.0rc1): H2 — Next stays disabled until the
        # analyst has chosen a target explicitly (placeholder = no target).
        if self._combo_target.currentData() is None:
            return False
        return self._lst_selected.count() >= 1

    def validateCurrentPage(self) -> bool:
        # defense in depth (Enter key / programmatic paths); the observable
        # gate for the user is the Next button, disabled via completeChanged
        return self.isComplete()

    def retranslate_ui(self) -> None:
        self.setTitle(tr("step2_title"))
        self.setSubTitle(tr("step2_subtitle"))
        self._lbl_target.setText(tr("step2_target_label"))
        self._combo_target.setItemText(0, tr("step2_target_placeholder"))
        self._lbl_available.setText(tr("step2_available"))
        self._lbl_selected.setText(tr("step2_selected"))
        self._lbl_hint.setText(tr("step2_hint_min_one"))
        self._lbl_chaid_note.setText(
            tr("step2_chaid_cont_note") if self._is_chaid() else ""
        )
        self._group_class.setTitle(tr("step2_class_group_title"))
        self._lbl_class_hint.setText(tr("step2_class_hint"))
        self._tbl_classes.setHorizontalHeaderLabels([
            tr("step2_class_col_label"),
            tr("step2_class_col_value"),
            tr("step2_class_col_count"),
            tr("step2_class_col_interest"),
        ])
        self._lbl_warning.setText(tr("step2_class_warning_majority"))
        self._lbl_weight.setText(tr("wizard_weight_label"))
        self._combo_weight.setItemText(0, tr("wizard_weight_none"))
        self._lbl_weight_warning.setText(tr("wizard_weight_warning"))
        self._lbl_weight_hint.setText(tr("wizard_weight_hint"))
        self._lbl_population.setText(tr("wizard_population_label"))
        self._combo_population.setItemText(0, tr("wizard_population_none"))
        self._lbl_population_hint.setText(tr("wizard_population_hint"))
        self._lbl_population_warning.setText(tr("wizard_population_warning"))
        self._group_population.setTitle(tr("wizard_population_ok_title"))
        self._lbl_population_ok_hint.setText(tr("wizard_population_ok_hint"))
        self._tbl_population.setHorizontalHeaderLabels([
            tr("wizard_population_ok_col_value"),
            tr("wizard_population_ok_col_count"),
            tr("wizard_population_ok_col_ok"),
        ])


# ---------------------------------------------------------------------------
# Step 3 - validation scheme
# ---------------------------------------------------------------------------


class ValidationPage(QWizardPage):
    """Holdout fraction (slider) + seed; CV slot prepared for Phase 2.1.b."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QFormLayout(self)

        self._combo_scheme = QComboBox()
        model = QStandardItemModel(self._combo_scheme)
        self._item_holdout = QStandardItem()
        self._item_cv = QStandardItem()
        self._item_cv.setEnabled(False)  # deferred to Phase 2.1.b
        model.appendRow(self._item_holdout)
        model.appendRow(self._item_cv)
        self._combo_scheme.setModel(model)
        self._combo_scheme.setToolTip(tr("step3_cv_tooltip"))

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setObjectName("sliderTrainFrac")
        self._slider.setRange(50, 90)
        self._slider.setSingleStep(1)
        self._slider.setValue(70)
        self._lbl_split = QLabel()
        self._slider.valueChanged.connect(self._refresh_split_label)

        self._spin_seed = QSpinBox()
        self._spin_seed.setObjectName("spinSeed")
        self._spin_seed.setRange(0, 999999)
        self._spin_seed.setValue(42)

        self._lbl_scheme = QLabel()
        self._lbl_seed = QLabel()
        layout.addRow(self._lbl_scheme, self._combo_scheme)
        layout.addRow(self._slider, self._lbl_split)
        layout.addRow(self._lbl_seed, self._spin_seed)

    def train_frac(self) -> float:
        return self._slider.value() / 100.0

    def seed(self) -> int:
        return int(self._spin_seed.value())

    def _refresh_split_label(self, value: int) -> None:
        self._lbl_split.setText(
            f"{tr('step3_train_label')}: {value}% | "
            f"{tr('step3_test_label')}: {100 - value}%"
        )

    def isComplete(self) -> bool:
        return True  # slider/spinbox ranges are valid by construction

    def retranslate_ui(self) -> None:
        self.setTitle(tr("step3_title"))
        self.setSubTitle(tr("step3_subtitle"))
        self._lbl_scheme.setText(tr("step3_scheme_label"))
        self._item_holdout.setText(tr("step3_scheme_holdout"))
        self._item_cv.setText(tr("step3_scheme_cv_todo"))
        self._lbl_seed.setText(tr("step3_seed_label"))
        self._refresh_split_label(self._slider.value())


# ---------------------------------------------------------------------------
# Step 4 - MRM governance
# ---------------------------------------------------------------------------


class GovernancePage(QWizardPage):
    """Governance mode (BANKING default / RESEARCH) + hyper-parameters.

    Banking -> Research: Jeffreys/PD-floor controls disabled and the config
    emits apply_jeffreys=False, pd_floor=None. Research -> Banking: the
    controls come back with their regulatory defaults.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._group_mode = QGroupBox()
        mode_box = QVBoxLayout(self._group_mode)
        self._rb_banking = QRadioButton()
        self._rb_banking.setObjectName("rbBanking")
        self._rb_research = QRadioButton()
        self._rb_research.setObjectName("rbResearch")
        self._lbl_banking_desc = QLabel()
        self._lbl_banking_desc.setIndent(24)
        self._lbl_research_desc = QLabel()
        self._lbl_research_desc.setIndent(24)
        btn_group = QButtonGroup(self)
        btn_group.setExclusive(True)
        btn_group.addButton(self._rb_banking)
        btn_group.addButton(self._rb_research)
        mode_box.addWidget(self._rb_banking)
        mode_box.addWidget(self._lbl_banking_desc)
        mode_box.addWidget(self._rb_research)
        mode_box.addWidget(self._lbl_research_desc)
        self._rb_banking.setChecked(True)  # Banking is the default mode
        layout.addWidget(self._group_mode)

        form = QFormLayout()
        self._chk_jeffreys = QCheckBox()
        self._chk_jeffreys.setObjectName("chkJeffreys")
        self._chk_jeffreys.setChecked(True)
        self._spin_floor = QDoubleSpinBox()
        self._spin_floor.setObjectName("spinPdFloor")
        self._spin_floor.setDecimals(4)
        self._spin_floor.setRange(0.0, 0.05)
        self._spin_floor.setSingleStep(0.0001)
        self._spin_floor.setValue(0.0005)  # Basel PD floor (BCBS CRE 32.4, non-sovereign)
        self._spin_depth = QSpinBox()
        self._spin_depth.setObjectName("spinMaxDepth")
        self._spin_depth.setRange(2, 10)
        self._spin_depth.setValue(4)
        self._spin_child = QSpinBox()
        self._spin_child.setObjectName("spinMinChild")
        self._spin_child.setRange(10, 50000)
        self._spin_child.setValue(50)
        self._spin_min_child_weight = QDoubleSpinBox()
        self._spin_min_child_weight.setObjectName("spinMinChildWeight")
        self._spin_min_child_weight.setDecimals(2)
        self._spin_min_child_weight.setRange(0.0, 100000.0)
        self._spin_min_child_weight.setSingleStep(1.0)
        self._spin_min_child_weight.setValue(0.0)
        self._lbl_jeffreys = QLabel()
        self._lbl_floor = QLabel()
        self._lbl_depth = QLabel()
        self._lbl_child = QLabel()
        self._lbl_min_child_weight = QLabel()
        self._lbl_min_child_weight_hint = QLabel()
        self._lbl_min_child_weight_hint.setWordWrap(True)
        form.addRow(self._lbl_jeffreys, self._chk_jeffreys)
        form.addRow(self._lbl_floor, self._spin_floor)
        form.addRow(self._lbl_depth, self._spin_depth)
        form.addRow(self._lbl_child, self._spin_child)
        form.addRow(self._lbl_min_child_weight, self._spin_min_child_weight)
        form.addRow("", self._lbl_min_child_weight_hint)
        layout.addLayout(form)

        self._lbl_summary_title = QLabel()
        self._lbl_summary_title.setObjectName("panelTitle")
        self._lbl_summary = QLabel()
        self._lbl_summary.setObjectName("lblSummary")
        layout.addWidget(self._lbl_summary_title)
        layout.addWidget(self._lbl_summary)
        layout.addStretch(1)

        self._rb_banking.toggled.connect(self._sync_governance_controls)
        self._sync_governance_controls()

    # --- governance mode ---------------------------------------------------

    def is_banking(self) -> bool:
        return self._rb_banking.isChecked()

    def apply_jeffreys(self) -> bool:
        return self._chk_jeffreys.isChecked() if self.is_banking() else False

    def pd_floor(self) -> float | None:
        return float(self._spin_floor.value()) if self.is_banking() else None

    def max_depth(self) -> int:
        return int(self._spin_depth.value())

    def min_child_size(self) -> int:
        return int(self._spin_child.value())

    def min_child_weight(self) -> float | None:
        """Piso de MASA PONDERADA por rama (Fase 3.7.c). 0.0 = desactivado."""
        v = float(self._spin_min_child_weight.value())
        return None if v <= 0.0 else v

    def _sync_governance_controls(self) -> None:
        banking = self.is_banking()
        self._chk_jeffreys.setEnabled(banking)
        self._spin_floor.setEnabled(banking)
        if banking:  # restore regulatory defaults
            self._chk_jeffreys.setChecked(True)
            self._spin_floor.setValue(0.0005)

    # --- Qt overrides ------------------------------------------------------

    def initializePage(self) -> None:
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        wiz = self.wizard()
        if wiz is None:
            return
        cfg = wiz.current_config()
        gov_key = (
            "step4_govmode_banking_short"
            if cfg["governance_mode"] == "BANKING"
            else "step4_govmode_research_short"
        )
        lines = [
            f"{tr('step4_summary_engine')}: {cfg['engine']}",
            f"{tr('step2_target_label')} {cfg['target']}",
            f"{tr('step2_selected')}: {len(cfg['predictors'])}",
            (f"{tr('step3_train_label')}: {int(cfg['train_frac'] * 100)}% · "
             f"{tr('step3_seed_label')}: {cfg['seed']}"),
            (f"{tr('step4_max_depth')}: {cfg['max_depth']} · "
             f"{tr('step4_min_child')}: {cfg['min_child_size']}"),
            f"{tr('step4_govmode_title')}: {tr(gov_key)}",
        ]
        self._lbl_summary.setText("\n".join(lines))

    def isComplete(self) -> bool:
        return True  # spinbox ranges are valid by construction

    def retranslate_ui(self) -> None:
        self.setTitle(tr("step4_title"))
        self.setSubTitle(tr("step4_subtitle"))
        self._group_mode.setTitle(tr("step4_govmode_title"))
        self._rb_banking.setText(tr("step4_govmode_banking"))
        self._rb_research.setText(tr("step4_govmode_research"))
        self._lbl_banking_desc.setText(tr("step4_govmode_banking_desc"))
        self._lbl_research_desc.setText(tr("step4_govmode_research_desc"))
        self._lbl_jeffreys.setText(tr("step4_apply_jeffreys"))
        self._lbl_floor.setText(tr("step4_pd_floor"))
        self._lbl_depth.setText(tr("step4_max_depth"))
        self._lbl_child.setText(tr("step4_min_child"))
        self._lbl_min_child_weight.setText(tr("step4_min_child_weight"))
        self._lbl_min_child_weight_hint.setText(
            tr("step4_min_child_weight_hint")
        )
        self._lbl_summary_title.setText(tr("step4_summary_label"))
        self._refresh_summary()


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------


class ModelWizard(QWizard):
    """4-step transactional wizard; emits a plain config dict on Finish.

    NON-modal by design: the main-menu language switch must stay reachable
    while the wizard is open (live retranslation via language_bus).
    """

    finished_with_config = Signal(dict)

    def __init__(
        self,
        columns: tuple[str, ...],
        types: dict[str, str],
        *,
        target_provider: Callable[[str], dict] | None = None,
        weight_validator: Callable[[str], bool] | None = None,
        population_provider: Callable[[str], dict] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # Micro-ajuste 2 (diseno 2.1): el boton Help se oculta por DEFECTO en
        # Qt 6 (la opcion es HaveHelpButton; no existe "NoHelpButton" - ver
        # docs Qt6). Sin contenido de ayuda, basta no activarla.
        self.setModal(False)

        self.page_engine = EnginePage(self)
        self.page_predictors = PredictorsPage(
            columns, types, target_provider=target_provider,
            weight_validator=weight_validator,
            population_provider=population_provider, parent=self
        )
        self.page_validation = ValidationPage(self)
        self.page_governance = GovernancePage(self)
        for page in (self.page_engine, self.page_predictors,
                     self.page_validation, self.page_governance):
            self.addPage(page)

        language_bus.language_changed.connect(self._on_language_changed)
        self.retranslate_ui()

    # --- public API --------------------------------------------------------

    def selected_engine(self) -> str:
        return self.page_engine.selected_engine()

    def current_config(self) -> dict:
        """Plain-Python snapshot of the 4 steps (the contract to MainWindow)."""
        banking = self.page_governance.is_banking()
        return {
            "engine": self.page_engine.selected_engine(),
            "target": self.page_predictors.target(),
            "predictors": self.page_predictors.selected_predictors(),
            "target_class": self.page_predictors.target_class(),
            "class_labels": self.page_predictors.class_labels(),
            "weight_col": self.page_predictors.weight_col(),
            "population_col": self.page_predictors.population_col(),
            "population_ok_values": self.page_predictors.population_ok_values(),
            "train_frac": self.page_validation.train_frac(),
            "seed": self.page_validation.seed(),
            "max_depth": self.page_governance.max_depth(),
            "min_child_size": self.page_governance.min_child_size(),
            "min_child_weight": self.page_governance.min_child_weight(),
            "governance_mode": "BANKING" if banking else "RESEARCH",
            "apply_jeffreys": self.page_governance.apply_jeffreys(),
            "pd_floor": self.page_governance.pd_floor(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("wizard_title"))
        self.setButtonText(QWizard.WizardButton.NextButton, tr("wizard_next"))
        self.setButtonText(QWizard.WizardButton.BackButton, tr("wizard_back"))
        self.setButtonText(
            QWizard.WizardButton.FinishButton, tr("wizard_finish")
        )
        self.setButtonText(
            QWizard.WizardButton.CancelButton, tr("wizard_cancel")
        )
        for page in (self.page_engine, self.page_predictors,
                     self.page_validation, self.page_governance):
            page.retranslate_ui()

    # --- Qt overrides ------------------------------------------------------

    def accept(self) -> None:
        self.finished_with_config.emit(self.current_config())
        super().accept()

    def closeEvent(self, event: QCloseEvent) -> None:
        # disconnect the bus: without this, the bound method keeps the
        # wizard alive (and retranslating) until Qt deletes the object
        try:
            language_bus.language_changed.disconnect(self._on_language_changed)
        except (RuntimeError, TypeError):
            pass  # already disconnected
        super().closeEvent(event)

    # --- internals -----------------------------------------------------------

    def _on_language_changed(self, _lang: str) -> None:
        self.retranslate_ui()
