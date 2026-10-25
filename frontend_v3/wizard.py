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
from PySide6.QtGui import QCloseEvent, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStyle,
    QStyleFactory,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from frontend_v3.i18n import language_bus, tr

# Data-type icons for the predictor lists (Phase 3.11.a.1 UX polish):
# the visible item text is the bare column name; the type is carried by
# the icon and the tooltip.
_TYPE_ICONS = {
    "NOMINAL": QStyle.StandardPixmap.SP_DialogYesButton,
    "ORDINAL": QStyle.StandardPixmap.SP_ArrowUp,
    "CONTINUOUS": QStyle.StandardPixmap.SP_FileDialogInfoView,
}

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
# TODO(zona_gris): el brief pedia iconos SP_* en los radios de motor sin
# fijar cuáles; mapeo semántico conservador (C&RT = split binario,
# CHAID = rejilla multivía, Exhaustive = recorrido iterativo, QUEST =
# interrogante). El estratega puede cambiar los pixmaps.
_ENGINE_ICONS = {
    "CRT": QStyle.StandardPixmap.SP_ArrowForward,
    "CHAID": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "CHAID_EXHAUSTIVE": QStyle.StandardPixmap.SP_BrowserReload,
    "QUEST": QStyle.StandardPixmap.SP_MessageBoxQuestion,
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
        # Application title banner (legible over dark backgrounds via the
        # QSS rule QLabel#wizardTitle, color $ACCENT). Built ONCE here;
        # retranslate_ui only assigns the text, so a language switch
        # never duplicates the widget (single-source-of-truth pattern).
        self._lbl_wizard_title = QLabel()
        self._lbl_wizard_title.setObjectName("wizardTitle")
        layout.addWidget(self._lbl_wizard_title)
        for engine, desc_key in _ENGINES:
            radio = QRadioButton(_ENGINE_LABELS[engine])  # proper noun, fixed
            radio.setIcon(self.style().standardIcon(_ENGINE_ICONS[engine]))
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
        self._lbl_wizard_title.setText(tr("wizard_title"))
        self.setTitle(tr("step1_title"))
        self.setSubTitle(tr("step1_subtitle"))
        for engine, desc_key in _ENGINES:
            self._descs[engine].setText(tr(desc_key))


# ---------------------------------------------------------------------------
# Step 2 - predictors and target
# ---------------------------------------------------------------------------


class PredictorsPage(QWizardPage):
    """Target combo + dual predictor lists (available / selected).

    Phase 3.10.b (H14) removed the CHAID mirror rule: the backend now
    bins CONTINUOUS predictors automatically (SplitConfig.bin_edges), so
    [CONT] items are enabled for EVERY engine, including CHAID and
    CHAID_EXHAUSTIVE (Phase 3.11: legacy mirror rule deleted).

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

        # Phase 3.11.a.1: grid layout, three bands (combos / core lists /
        # class table). The old vertical stack crowded the lists; the
        # weight/population help texts moved to combo tooltips.
        layout = QGridLayout(self)

        # --- Row 0 (top): compact combo strip — target + weight +
        # population in a single horizontal band ---
        row_combos = QHBoxLayout()
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
        row_combos.addWidget(self._lbl_target)
        row_combos.addWidget(self._combo_target, 1)

        # --- Phase 3.2.h: weight column combo ---
        self._lbl_weight = QLabel()
        self._combo_weight = QComboBox()
        self._combo_weight.setObjectName("comboWeight")
        self._combo_weight.addItem("", userData=None)  # retraducido
        for col in columns:
            self._combo_weight.addItem(col, userData=col)
        row_combos.addWidget(self._lbl_weight)
        row_combos.addWidget(self._combo_weight, 1)

        # --- Phase 3.3.d: population column combo ---
        self._lbl_population = QLabel()
        self._combo_population = QComboBox()
        self._combo_population.setObjectName("comboPopulation")
        self._combo_population.addItem("", userData=None)  # retraducido
        for col in columns:
            self._combo_population.addItem(col, userData=col)
        row_combos.addWidget(self._lbl_population)
        row_combos.addWidget(self._combo_population, 1)
        layout.addLayout(row_combos, 0, 0)

        # --- Rows 1-2: non-blocking amber warnings (hidden by default) ---
        self._lbl_weight_warning = QLabel()
        self._lbl_weight_warning.setObjectName("lblWeightWarning")
        self._lbl_weight_warning.setWordWrap(True)
        self._lbl_weight_warning.setVisible(False)
        layout.addWidget(self._lbl_weight_warning, 1, 0)

        self._lbl_population_warning = QLabel()
        self._lbl_population_warning.setObjectName("lblPopulationWarning")
        self._lbl_population_warning.setWordWrap(True)
        self._lbl_population_warning.setVisible(False)
        layout.addWidget(self._lbl_population_warning, 2, 0)

        # --- Row 3: population OK-values group (visible only when a
        # population column is declared) ---
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
        self._tbl_population.setMaximumHeight(150)  # no aplastar las listas
        gpop_layout.addWidget(self._tbl_population)
        layout.addWidget(self._group_population, 3, 0)

        # --- Row 4 (centre, the core): available / selected predictor
        # lists with the arrow buttons in between ---
        lists_row = QHBoxLayout()
        left_box = QVBoxLayout()
        self._lbl_available = QLabel()
        self._lst_available = QListWidget()
        self._lst_available.setObjectName("lstAvailable")
        left_box.addWidget(self._lbl_available)
        left_box.addWidget(self._lst_available)
        lists_row.addLayout(left_box, 1)

        btns = QVBoxLayout()
        # Hotfix 3.11.a.1: tooltips via tr() (live retranslation in
        # retranslate_ui); initial text set there like every other string.
        self._btn_add = QPushButton("→")
        self._btn_remove = QPushButton("←")
        self._btn_add_all = QPushButton("⇒")
        self._btn_remove_all = QPushButton("⇐")
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
        layout.addLayout(lists_row, 4, 0)
        layout.setRowStretch(4, 1)  # las listas absorben el alto sobrante

        # --- Row 5 (bottom): class-of-interest + labels table, full width
        # but capped in height so it never crushes the lists ---
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
        self._tbl_classes.setMaximumHeight(150)
        gclass_layout.addWidget(self._tbl_classes)

        self._lbl_warning = QLabel()
        self._lbl_warning.setObjectName("lblClassWarning")
        self._lbl_warning.setWordWrap(True)
        self._lbl_warning.setVisible(False)  # se muestra si aplica
        gclass_layout.addWidget(self._lbl_warning)

        layout.addWidget(self._group_class, 5, 0)

        self._lbl_hint = QLabel()
        layout.addWidget(self._lbl_hint, 6, 0)

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
        ptype = self._types[col]
        item = QListWidgetItem(col)  # bare name; the type rides on the icon
        item.setIcon(self.style().standardIcon(_TYPE_ICONS[ptype]))
        # TODO(zona_gris): tooltip = backend PredictorType name (fixed
        # domain proper noun, like the engine names in _ENGINE_LABELS).
        # i18n keys ("Variable Continua" / "Continuous variable") were out
        # of scope for this task; add step2_type_* keys if wanted.
        item.setToolTip(ptype)
        item.setData(Qt.ItemDataRole.UserRole, col)
        if not enabled:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled
                          & ~Qt.ItemFlag.ItemIsSelectable)
        return item

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
            # Phase 3.11: no engine-specific disabling; CHAID bins [CONT]
            # automatically in the backend (Phase 3.10.b, H14).
            self._lst_available.addItem(self._make_item(col))
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
        la etiqueta humana, el valor original y el count. Default de
        etiqueta: str(valor). Se RESPETA el texto que el analista ya
        hubiera escrito para un valor (un repoblado no pisa
        ediciones). La última fila queda
        seleccionada por default (default neutral; el analista debe
        elegir explícitamente en cualquier caso).
        Warning amber si la clase seleccionada es la mayoritaria y
        NO hay empate entre clases.
        """
        # Capturar las etiquetas previas ANTES de vaciar la tabla: los
        # QLineEdit mueren con setRowCount(0).
        prev_labels = {
            r["value"]: r["label_edit"].text()
            for r in getattr(self, "_class_rows", [])
        }
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
            # Columna 0: etiqueta humana (editable). Prioridad: texto
            # previo del analista > str(valor).
            if valor in prev_labels:
                default_label = prev_labels[valor]
            else:
                default_label = str(valor)
            edit = QLineEdit(default_label)
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
        """Refresh the available list when entering the step.

        Phase 3.11: the CHAID mirror rule (evict selected [CONT] items)
        is gone — the backend bins continuous predictors automatically.
        """
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
        # Phase 3.11.a.1: the help texts live as combo tooltips (saves
        # vertical space in the grid layout).
        self._combo_weight.setToolTip(tr("wizard_weight_hint"))
        self._lbl_population.setText(tr("wizard_population_label"))
        self._combo_population.setItemText(0, tr("wizard_population_none"))
        self._combo_population.setToolTip(tr("wizard_population_hint"))
        self._lbl_population_warning.setText(tr("wizard_population_warning"))
        self._group_population.setTitle(tr("wizard_population_ok_title"))
        self._lbl_population_ok_hint.setText(tr("wizard_population_ok_hint"))
        self._tbl_population.setHorizontalHeaderLabels([
            tr("wizard_population_ok_col_value"),
            tr("wizard_population_ok_col_count"),
            tr("wizard_population_ok_col_ok"),
        ])
        self._btn_add.setToolTip(tr("step2_btn_move_one"))
        self._btn_remove.setToolTip(tr("step2_btn_move_back_one"))
        self._btn_add_all.setToolTip(tr("step2_btn_move_all"))
        self._btn_remove_all.setToolTip(tr("step2_btn_move_back_all"))


# ---------------------------------------------------------------------------
# Step 3 - validation scheme
# ---------------------------------------------------------------------------


class ValidationPage(QWizardPage):
    """Scheme radios (classic structure) + holdout slider + seed.

    Phase 3.11.a.1: three vertical radio buttons — Do not validate /
    Partition (Holdout, default) / Cross-validation. The progress bar and
    the slider are enabled ONLY under Holdout. CV shows a Phase 2.1.b
    notice.

    TODO(zona_gris): the scheme radios are presentational for now — the
    backend pipeline (Session.partition -> train) ALWAYS applies the
    stratified holdout; there is no no-validation or CV flow yet. To
    avoid a silent UI/backend mismatch, NONE and CV show an explicit
    notice and current_config() keeps emitting the holdout fraction.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Scheme radios (classic vertical stack; Holdout default)
        self._scheme_group = QButtonGroup(self)
        self._scheme_group.setExclusive(True)
        self._rb_none = QRadioButton()
        self._rb_none.setObjectName("rbSchemeNone")
        self._rb_holdout = QRadioButton()
        self._rb_holdout.setObjectName("rbSchemeHoldout")
        self._rb_cv = QRadioButton()
        self._rb_cv.setObjectName("rbSchemeCV")
        for rb in (self._rb_none, self._rb_holdout, self._rb_cv):
            self._scheme_group.addButton(rb)
            layout.addWidget(rb)
        self._rb_holdout.setChecked(True)

        # Availability notices (shown only when the radio is selected)
        self._lbl_none_notice = QLabel()
        self._lbl_none_notice.setObjectName("lblNoneNotice")
        self._lbl_none_notice.setWordWrap(True)
        self._lbl_none_notice.setVisible(False)
        self._lbl_cv_notice = QLabel()
        self._lbl_cv_notice.setObjectName("lblCVNotice")
        self._lbl_cv_notice.setWordWrap(True)
        self._lbl_cv_notice.setVisible(False)
        layout.addWidget(self._lbl_none_notice)
        layout.addWidget(self._lbl_cv_notice)

        # Hotfix 3.11.a.1: modern split visualisation — section title,
        # proportional progress bar and large train/test percentage labels.
        self._lbl_split_title = QLabel()
        self._lbl_split_title.setObjectName("panelTitle")
        layout.addWidget(self._lbl_split_title)

        self._split_bar = QProgressBar()
        self._split_bar.setObjectName("splitBar")
        self._split_bar.setTextVisible(False)
        self._split_bar.setFixedHeight(24)
        self._split_bar.setRange(0, 100)
        layout.addWidget(self._split_bar)

        row_split_labels = QHBoxLayout()
        self._lbl_train = QLabel()
        self._lbl_train.setObjectName("splitTrainLabel")
        self._lbl_train.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._lbl_test = QLabel()
        self._lbl_test.setObjectName("splitTestLabel")
        self._lbl_test.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        for lbl in (self._lbl_train, self._lbl_test):
            font = lbl.font()
            font.setPointSize(12)
            font.setBold(True)
            lbl.setFont(font)
        row_split_labels.addWidget(self._lbl_train)
        row_split_labels.addStretch(1)
        row_split_labels.addWidget(self._lbl_test)
        layout.addLayout(row_split_labels)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setObjectName("sliderTrainFrac")
        self._slider.setRange(50, 90)
        self._slider.setSingleStep(1)
        self._slider.setValue(70)
        self._slider.valueChanged.connect(self._update_split_ui)
        layout.addWidget(self._slider)

        # Seed row (spinbox kept, below the split controls)
        self._spin_seed = QSpinBox()
        self._spin_seed.setObjectName("spinSeed")
        self._spin_seed.setRange(0, 999999)
        self._spin_seed.setValue(42)
        self._lbl_seed = QLabel()
        row_seed = QHBoxLayout()
        row_seed.addWidget(self._lbl_seed)
        row_seed.addWidget(self._spin_seed)
        row_seed.addStretch(1)
        layout.addLayout(row_seed)
        layout.addStretch(1)

        self._scheme_group.buttonToggled.connect(self._sync_scheme_controls)
        self._sync_scheme_controls()

    def train_frac(self) -> float:
        return self._slider.value() / 100.0

    def seed(self) -> int:
        return int(self._spin_seed.value())

    def validation_scheme(self) -> str:
        """Selected scheme: NONE / HOLDOUT / CV (presentational, see TODO)."""
        if self._rb_none.isChecked():
            return "NONE"
        if self._rb_cv.isChecked():
            return "CV"
        return "HOLDOUT"

    def _sync_scheme_controls(self, *_args) -> None:
        holdout = self._rb_holdout.isChecked()
        # Only the holdout split controls track the radio; the split
        # labels keep showing the last values (read-only display).
        self._slider.setEnabled(holdout)
        self._split_bar.setEnabled(holdout)
        self._lbl_none_notice.setVisible(self._rb_none.isChecked())
        self._lbl_cv_notice.setVisible(self._rb_cv.isChecked())

    def _update_split_ui(self, value: int) -> None:
        self._split_bar.setValue(value)
        self._lbl_train.setText(f"{tr('step3_train_label')}: {value}%")
        self._lbl_test.setText(f"{tr('step3_test_label')}: {100 - value}%")

    def isComplete(self) -> bool:
        return True  # slider/spinbox ranges are valid by construction

    def retranslate_ui(self) -> None:
        self.setTitle(tr("step3_title"))
        self.setSubTitle(tr("step3_subtitle"))
        self._rb_none.setText(tr("step3_scheme_none"))
        self._rb_holdout.setText(tr("step3_scheme_partition"))
        self._rb_cv.setText(tr("step3_scheme_cv"))
        self._lbl_none_notice.setText(tr("step3_none_notice"))
        self._lbl_cv_notice.setText(tr("step3_cv_notice"))
        self._lbl_seed.setText(tr("step3_seed_label"))
        self._lbl_split_title.setText(tr("step3_split_title"))
        self._update_split_ui(self._slider.value())


# ---------------------------------------------------------------------------
# Step 4 - MRM governance
# ---------------------------------------------------------------------------


class AdvancedOptionsDialog(QDialog):
    """Modal advanced-options editor (Phase 3.11.a.1, classic structure).

    Tabs:
      - "Stopping Rules": max_depth, min_child_size, min_child_weight
        (editable; they flow into ModelWizard.current_config() on Accept).
      - "CHAID": alpha_merge / alpha_split.

    TODO(zona_gris): the CHAID alpha controls are DISABLED on purpose.
    ChaidEngine accepts alpha_merge/alpha_split (default 0.05) but
    Session.train does not expose them and they are not part of
    SplitConfig/params_fingerprint: editable-but-inert controls would be
    a silent no-op (governance violation). They enable when the backend
    contract lands (Phase 3.11.c/d, TreeBuilder redesign).

    The dialog is modal and short-lived: texts are resolved via tr() at
    construction (no live retranslation while open).
    """

    def __init__(
        self,
        *,
        max_depth: int,
        min_child_size: int,
        min_child_weight: float,
        cost_matrix: tuple[tuple[float, ...], ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("advancedOptionsDialog")
        self.setModal(True)
        self.setWindowTitle(tr("adv_dialog_title"))
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("advancedTabs")

        # --- Tab 1: Stopping Rules (editable) ---
        tab_stop = QWidget()
        tab_stop.setObjectName("tabStoppingRules")
        form_stop = QFormLayout(tab_stop)
        self._spin_depth = QSpinBox()
        self._spin_depth.setObjectName("spinMaxDepth")
        self._spin_depth.setRange(2, 10)
        self._spin_depth.setValue(int(max_depth))
        self._spin_child = QSpinBox()
        self._spin_child.setObjectName("spinMinChild")
        self._spin_child.setRange(10, 50000)
        self._spin_child.setValue(int(min_child_size))
        self._spin_min_child_weight = QDoubleSpinBox()
        self._spin_min_child_weight.setObjectName("spinMinChildWeight")
        self._spin_min_child_weight.setDecimals(2)
        self._spin_min_child_weight.setRange(0.0, 100000.0)
        self._spin_min_child_weight.setSingleStep(1.0)
        self._spin_min_child_weight.setValue(float(min_child_weight))
        form_stop.addRow(tr("step4_max_depth"), self._spin_depth)
        form_stop.addRow(tr("step4_min_child"), self._spin_child)
        form_stop.addRow(
            tr("step4_min_child_weight"), self._spin_min_child_weight
        )
        lbl_hint = QLabel(tr("step4_min_child_weight_hint"))
        lbl_hint.setWordWrap(True)
        form_stop.addRow("", lbl_hint)
        self._tabs.addTab(tab_stop, tr("adv_tab_stopping"))

        # --- Tab 2: CHAID (disabled until the backend contract lands) ---
        tab_chaid = QWidget()
        tab_chaid.setObjectName("tabChaid")
        form_chaid = QFormLayout(tab_chaid)
        self._spin_alpha_merge = QDoubleSpinBox()
        self._spin_alpha_merge.setObjectName("spinAlphaMerge")
        self._spin_alpha_merge.setDecimals(3)
        self._spin_alpha_merge.setRange(0.001, 0.5)
        self._spin_alpha_merge.setSingleStep(0.005)
        self._spin_alpha_merge.setValue(0.05)  # ChaidEngine default
        self._spin_alpha_split = QDoubleSpinBox()
        self._spin_alpha_split.setObjectName("spinAlphaSplit")
        self._spin_alpha_split.setDecimals(3)
        self._spin_alpha_split.setRange(0.001, 0.5)
        self._spin_alpha_split.setSingleStep(0.005)
        self._spin_alpha_split.setValue(0.05)  # ChaidEngine default
        self._spin_alpha_merge.setEnabled(False)  # TODO(zona_gris), arriba
        self._spin_alpha_split.setEnabled(False)
        form_chaid.addRow(tr("adv_chaid_alpha_merge"), self._spin_alpha_merge)
        form_chaid.addRow(tr("adv_chaid_alpha_split"), self._spin_alpha_split)
        lbl_pending = QLabel(tr("adv_chaid_pending"))
        lbl_pending.setWordWrap(True)
        form_chaid.addRow("", lbl_pending)
        self._tabs.addTab(tab_chaid, tr("adv_tab_chaid"))

        # --- Tab 3: Costs (N x N misclassification cost matrix, 3.11.c.3) ---
        # TODO(zona_gris): N fijo a 2 (binario) en esta fase; deducir el
        # numero de clases del target cuando el wizard exponga esa info
        # de forma fiable en Step 4 (Fase 3.11.d o 4.0).
        tab_costs = QWidget()
        tab_costs.setObjectName("tabCosts")
        lay_costs = QVBoxLayout(tab_costs)
        n_costs = 2
        self._tbl_costs = QTableWidget(n_costs, n_costs)
        self._tbl_costs.setObjectName("tblCosts")
        diag_bg = self.palette().color(QPalette.ColorRole.AlternateBase)
        for i in range(n_costs):
            for j in range(n_costs):
                valor = 0.0
                if cost_matrix and len(cost_matrix) == n_costs:
                    try:
                        valor = float(cost_matrix[i][j])
                    except (IndexError, TypeError, ValueError):
                        valor = 0.0
                item = QTableWidgetItem(f"{valor:.6g}")
                if i == j:
                    # Diagonal fija a 0: solo lectura y fondo atenuado.
                    item = QTableWidgetItem("0")
                    item.setBackground(diag_bg)
                    item.setFlags(
                        item.flags() & ~Qt.ItemFlag.ItemIsEditable
                    )
                self._tbl_costs.setItem(i, j, item)
        lay_costs.addWidget(self._tbl_costs)
        lbl_costs_hint = QLabel(tr("adv_costs_hint"))
        lbl_costs_hint.setWordWrap(True)
        lay_costs.addWidget(lbl_costs_hint)
        self._tabs.addTab(tab_costs, tr("adv_tab_costs"))

        layout.addWidget(self._tabs)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[int, int, float]:
        """(max_depth, min_child_size, min_child_weight) as edited."""
        return (
            int(self._spin_depth.value()),
            int(self._spin_child.value()),
            float(self._spin_min_child_weight.value()),
        )

    def get_cost_matrix(self) -> tuple[tuple[float, ...], ...]:
        """Matriz N x N leida de la tabla (tupla de tuplas, inmutable).

        Diagonal forzada a 0.0 y valores no parseables/negativos clampeados
        a 0.0 (defensa; la validacion estricta vive en Session.fix_spec).
        """
        n = self._tbl_costs.rowCount()
        mat: list[tuple[float, ...]] = []
        for i in range(n):
            fila: list[float] = []
            for j in range(n):
                item = self._tbl_costs.item(i, j)
                try:
                    v = float(item.text()) if item is not None else 0.0
                except ValueError:
                    v = 0.0
                fila.append(0.0 if i == j else max(0.0, v))
            mat.append(tuple(fila))
        return tuple(mat)


class GovernancePage(QWizardPage):
    """Governance mode (BANKING default / RESEARCH) + summary + advanced.

    Phase 3.11.a.1 (classic structure): the hyper-parameter fields no
    longer live on the page; they moved into the modal "Advanced
    Options..." dialog (Stopping Rules / CHAID tabs). The page keeps the
    governance controls (Jeffreys / PD floor — bound to the mode), a
    model summary label and the big Advanced Options button.

    Banking -> Research: Jeffreys/PD-floor controls disabled and the config
    emits apply_jeffreys=False, pd_floor=None. Research -> Banking: the
    controls come back with their regulatory defaults.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Hyper-parameters edited via the Advanced Options dialog
        # (defaults identical to the pre-3.11.a.1 spinboxes).
        self._max_depth: int = 4
        self._min_child_size: int = 50
        self._min_child_weight: float = 0.0
        # Fase 3.11.c.3: matriz de costos N x N (() = sin costos; fluye a
        # current_config() y de ahi a Session.fix_spec).
        self._cost_matrix: tuple[tuple[float, ...], ...] = ()

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
        # Mode icons (standard pixmaps): Banking = computer (regulated
        # production), Research = contents view (exploratory work).
        style = self.style()
        self._rb_banking.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        )
        self._rb_research.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        )
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
        self._lbl_jeffreys = QLabel()
        self._lbl_floor = QLabel()
        form.addRow(self._lbl_jeffreys, self._chk_jeffreys)
        form.addRow(self._lbl_floor, self._spin_floor)
        layout.addLayout(form)

        # Big classic entry point to the modal advanced-options editor.
        self._btn_advanced = QPushButton()
        self._btn_advanced.setObjectName("btnAdvancedOptions")
        self._btn_advanced.setMinimumHeight(40)
        font = self._btn_advanced.font()
        font.setBold(True)
        self._btn_advanced.setFont(font)
        self._btn_advanced.clicked.connect(self._open_advanced_options)
        layout.addWidget(self._btn_advanced)

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
        return int(self._max_depth)

    def min_child_size(self) -> int:
        return int(self._min_child_size)

    def min_child_weight(self) -> float | None:
        """Piso de MASA PONDERADA por rama (Fase 3.7.c). 0.0 = desactivado."""
        return None if self._min_child_weight <= 0.0 else self._min_child_weight

    def _open_advanced_options(self) -> None:
        """Open the modal editor; on Accept the values flow into
        current_config() (via the page getters) and the summary refreshes."""
        dlg = AdvancedOptionsDialog(
            max_depth=self._max_depth,
            min_child_size=self._min_child_size,
            min_child_weight=self._min_child_weight,
            cost_matrix=self._cost_matrix,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._max_depth, self._min_child_size, self._min_child_weight = (
            dlg.values()
        )
        self._cost_matrix = dlg.get_cost_matrix()
        self._refresh_summary()

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
        # Dashboard-style rich text (QLabel auto-detects HTML). Accent
        # spans highlight the decision values; the list keeps the audit
        # order engine -> target -> predictors -> split -> stopping rules
        # -> governance.
        # NOTE (test contract): the stopping-rules line keeps the colon
        # OUTSIDE the <b> tags so the raw HTML still contains ": <value>"
        # (test_wizard.py asserts ": 8" after editing max_depth); the other
        # lines keep the colon inside the <b> ("Motor:" / "Engine:" are
        # asserted with the colon attached to the label word).
        accent = "#1A73E8"
        html = (
            "<ul style='margin:0px; padding-left:16px;'>"
            f"<li><b>{tr('step4_summary_engine')}:</b> "
            f"<span style='color: {accent};'>{cfg['engine']}</span></li>"
            f"<li><b>{tr('step2_target_label')}</b> "
            f"<span style='color: {accent};'>{cfg['target']}</span></li>"
            f"<li><b>{tr('step2_selected')}:</b> {len(cfg['predictors'])}</li>"
            f"<li><b>{tr('step3_train_label')}:</b> "
            f"{int(cfg['train_frac'] * 100)}% · "
            f"<b>{tr('step3_seed_label')}:</b> {cfg['seed']}</li>"
            f"<li><b>{tr('step4_max_depth')}</b>: {cfg['max_depth']} · "
            f"<b>{tr('step4_min_child')}</b>: {cfg['min_child_size']}</li>"
            f"<li><b>{tr('step4_govmode_title')}:</b> "
            f"<span style='color: {accent};'>{tr(gov_key)}</span></li>"
            "</ul>"
        )
        self._lbl_summary.setText(html)

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
        self._btn_advanced.setText(tr("step4_advanced_options"))
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

        # Phase 3.11.a.1: pin the wizard itself to Fusion so it never falls
        # back to the native Windows style (which ignores the app
        # palette/QSS). QWidget.setStyle() does NOT transfer ownership:
        # keep the reference alive for the wizard's lifetime.
        self._fusion_style = QStyleFactory.create("Fusion")
        if self._fusion_style is not None:
            self.setStyle(self._fusion_style)

        # Force ClassicStyle: AeroStyle (the Windows default) renders the
        # header and button bar through the OS theme, ignoring the app
        # palette and the QSS. ClassicStyle lets the QSS paint both.
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)

        # Inherit the global app palette (set by theme.apply_palette) so
        # native-rendered chrome (title bar, button frames) follows the
        # active theme instead of the Windows light/dark mode.
        app = QApplication.instance()
        if app is not None:
            self.setPalette(app.palette())
        self.setAutoFillBackground(True)

        # Reasonable opening size: wide enough for the dual predictor
        # lists and tall enough for the governance summary without
        # cramming (the user can still shrink down to 800x600).
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.resize(950, 700)

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
            "cost_matrix": self.page_governance._cost_matrix,
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
