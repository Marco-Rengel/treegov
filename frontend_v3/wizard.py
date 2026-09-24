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
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
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
    """

    def __init__(
        self,
        columns: tuple[str, ...],
        types: dict[str, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not columns:
            raise ValueError("PredictorsPage requires at least one column")
        self._columns = columns
        self._types = types

        layout = QVBoxLayout(self)

        target_row = QHBoxLayout()
        self._lbl_target = QLabel()
        self._combo_target = QComboBox()
        self._combo_target.setObjectName("comboTarget")
        for col in columns:
            self._combo_target.addItem(col, userData=col)
        target_row.addWidget(self._lbl_target)
        target_row.addWidget(self._combo_target, 1)
        layout.addLayout(target_row)

        lists_row = QHBoxLayout()
        left_box = QVBoxLayout()
        self._lbl_available = QLabel()
        self._lst_available = QListWidget()
        self._lst_available.setObjectName("lstAvailable")
        left_box.addWidget(self._lbl_available)
        left_box.addWidget(self._lst_available)
        lists_row.addLayout(left_box, 1)

        btns = QVBoxLayout()
        self._btn_add = QPushButton(">")
        self._btn_remove = QPushButton("<")
        self._btn_add_all = QPushButton(">>")
        self._btn_remove_all = QPushButton("<<")
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

        self._on_target_change(0)  # initial fill of the available list

    # --- data access -----------------------------------------------------

    def target(self) -> str:
        return str(self._combo_target.currentData())

    def selected_predictors(self) -> list[str]:
        return [
            str(self._lst_selected.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self._lst_selected.count())
        ]

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
        # if the new target was selected as predictor, move it back first
        for i in range(self._lst_selected.count() - 1, -1, -1):
            item = self._lst_selected.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == target:
                self._lst_selected.takeItem(i)
                self._lst_available.addItem(item)
        # available = columns - target - selected (order of self._columns)
        in_selected = set(self.selected_predictors())
        self._lst_available.clear()
        for col in self._columns:
            if col == target or col in in_selected:
                continue
            disabled = self._is_chaid() and self._types[col] == "CONTINUOUS"
            self._lst_available.addItem(self._make_item(col, not disabled))
        self.completeChanged.emit()

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
        return self._lst_selected.count() >= 1

    def validateCurrentPage(self) -> bool:
        # defense in depth (Enter key / programmatic paths); the observable
        # gate for the user is the Next button, disabled via completeChanged
        return self.isComplete()

    def retranslate_ui(self) -> None:
        self.setTitle(tr("step2_title"))
        self.setSubTitle(tr("step2_subtitle"))
        self._lbl_target.setText(tr("step2_target_label"))
        self._lbl_available.setText(tr("step2_available"))
        self._lbl_selected.setText(tr("step2_selected"))
        self._lbl_hint.setText(tr("step2_hint_min_one"))
        self._lbl_chaid_note.setText(
            tr("step2_chaid_cont_note") if self._is_chaid() else ""
        )


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
        self._spin_floor.setValue(0.0003)  # Basel PD floor (BCBS CRE 20.39)
        self._spin_depth = QSpinBox()
        self._spin_depth.setObjectName("spinMaxDepth")
        self._spin_depth.setRange(2, 10)
        self._spin_depth.setValue(4)
        self._spin_child = QSpinBox()
        self._spin_child.setObjectName("spinMinChild")
        self._spin_child.setRange(10, 50000)
        self._spin_child.setValue(50)
        self._lbl_jeffreys = QLabel()
        self._lbl_floor = QLabel()
        self._lbl_depth = QLabel()
        self._lbl_child = QLabel()
        form.addRow(self._lbl_jeffreys, self._chk_jeffreys)
        form.addRow(self._lbl_floor, self._spin_floor)
        form.addRow(self._lbl_depth, self._spin_depth)
        form.addRow(self._lbl_child, self._spin_child)
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

    def _sync_governance_controls(self) -> None:
        banking = self.is_banking()
        self._chk_jeffreys.setEnabled(banking)
        self._spin_floor.setEnabled(banking)
        if banking:  # restore regulatory defaults
            self._chk_jeffreys.setChecked(True)
            self._spin_floor.setValue(0.0003)

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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # Micro-ajuste 2 (diseno 2.1): el boton Help se oculta por DEFECTO en
        # Qt 6 (la opcion es HaveHelpButton; no existe "NoHelpButton" - ver
        # docs Qt6). Sin contenido de ayuda, basta no activarla.
        self.setModal(False)

        self.page_engine = EnginePage(self)
        self.page_predictors = PredictorsPage(columns, types, self)
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
            "train_frac": self.page_validation.train_frac(),
            "seed": self.page_validation.seed(),
            "max_depth": self.page_governance.max_depth(),
            "min_child_size": self.page_governance.min_child_size(),
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
