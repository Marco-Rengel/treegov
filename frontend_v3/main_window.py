"""Main window of the TreeGov GUI (Phase 2.0 skeleton + 2.1 wizard flow).

Clean room: no analytical logic here. The window orchestrates the backend
EXCLUSIVELY via backend_v3.session_state.Session (the authorized contract);
heavy data (DataFrames) never crosses into the frontend, only plain
metadata (column names, PredictorType.name strings) via describe_dataset().

Internationalization: every user-visible string goes through
frontend_v3.i18n.tr (bilingual EN/ES). Qt's self.tr()/lrelease workflow is
intentionally out of scope. Keyboard mnemonics ("&") deferred: to be
evaluated in Phase 2.3.

Single source of truth for texts: widgets are built empty and
retranslate_ui() assigns every visible string. __init__ ends by calling
retranslate_ui(), so language switch and first paint share one code path.
"""

from __future__ import annotations

import logging
import os
from typing import Callable

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyle,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from backend_v3.session_state import FlowState, Session
from frontend_v3 import __version__
from frontend_v3.i18n import (
    SUPPORTED,
    detect_system_language,
    get_language,
    language_bus,
    set_language,
    tr,
)
from frontend_v3.theme import apply_palette, apply_theme
from frontend_v3.tree_view import (
    TreePanel,
    model_summary_lines,
    node_detail_lines,
)
from frontend_v3.metrics_panel import MetricsPanel
from frontend_v3.data_viewer import DataViewer
from frontend_v3.tree_map import TreeMap
from frontend_v3.prune_dialog import PruneDialog
from frontend_v3.reports_panel import ReportsPanel
from frontend_v3.univariate_dialog import UnivariateDialog
from frontend_v3.wizard import ModelWizard


class MainWindow(QMainWindow):
    """TreeGov main window: menu bar, 3-panel splitter, status bar."""

    def __init__(
        self,
        session: Session | None = None,
        parent: QWidget | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._logger = logger
        self._theme_name: str = "light"
        # Phase 2.1: dataset profile (columns, types) and live wizard handle
        self._dataset_info: tuple[tuple[str, ...], dict[str, str]] | None = None
        self._current_dataset_path: str | None = None
        self._wizard: ModelWizard | None = None
        # Phase 3.1.f: last successful wizard cfg (needed to retrain after
        # a class-of-interest inversion without reopening the wizard)
        self._last_train_cfg: dict | None = None
        self._mode_name: str = "—"
        self._security_warning_shown: bool = False

        # Language before any widget text is built. QSettings without an
        # eager default: detect_system_language() runs only when unset,
        # and a corrupt stored value falls back to detection.
        lang = QSettings().value("language")
        set_language(lang if lang in SUPPORTED else detect_system_language())

        self._build_menus()
        self._build_central()
        self._build_toolbar()
        self._build_statusbar()
        self.retranslate_ui()

        self.resize(1280, 800)
        self.statusBar().showMessage(tr("status_ready"))

    # ------------------------------------------------------------------
    # Public contract (used from Phase 2.1 onward)
    # ------------------------------------------------------------------

    def set_session(self, session: Session) -> None:
        """Inject/refresh the backend session handle."""
        self._session = session

    def retranslate_ui(self) -> None:
        """Re-apply tr() to every visible string (called on language
        switch and once at startup, so both share the same path)."""
        self.setWindowTitle(tr("window_title"))

        self._menu_file.setTitle(tr("menu_file"))
        self._menu_edit.setTitle(tr("menu_edit"))
        self._menu_view.setTitle(tr("menu_view"))
        self._menu_format.setTitle(tr("menu_format"))
        self._menu_analysis.setTitle(tr("menu_analysis"))
        self._menu_tree.setTitle(tr("menu_tree"))
        self._menu_window.setTitle(tr("menu_window"))
        self._menu_help.setTitle(tr("menu_help"))

        self._act_new_wizard.setText(tr("menu_file_new_wizard"))
        self._act_open.setText(tr("menu_file_open"))
        self._act_exit.setText(tr("menu_file_exit"))
        self._act_edit_undo.setText(tr("menu_edit_undo"))
        self._act_format_node_display.setText(tr("menu_format_node_display"))
        self._act_analysis_var_types.setText(tr("menu_analysis_var_types"))
        self._act_univariate.setText(tr("menu_analysis_univariate"))
        self._act_window_tile.setText(tr("menu_window_tile"))
        self._act_train.setText(tr("menu_model_train"))
        self._act_evaluate_oos.setText(tr("menu_model_evaluate_oos"))
        self._act_load_oot.setText(tr("menu_model_load_oot"))
        self._act_prune.setText(tr("menu_model_prune"))
        self._act_zoom_in.setText(tr("tree_zoom_in"))
        self._act_zoom_out.setText(tr("tree_zoom_out"))
        self._act_zoom_fit.setText(tr("tree_zoom_fit"))

        # Toolbar IconOnly: el texto de la acción no es visible, así que
        # el tooltip (y el status tip) son la única etiqueta. Se fijan
        # aquí con el mismo tr() para re-traducirse al cambiar de
        # idioma.
        # TODO(zona_gris): el brief asumía que las acciones ya tenían
        # tooltip; no lo tenían (ni menús ni zoom). Se añaden aquí.
        for act, key in (
            (self._act_open, "menu_file_open"),
            (self._act_new_wizard, "menu_file_new_wizard"),
            (self._act_train, "menu_model_train"),
            (self._act_evaluate_oos, "menu_model_evaluate_oos"),
            (self._act_load_oot, "menu_model_load_oot"),
            (self._act_prune, "menu_model_prune"),
            (self._act_zoom_in, "tree_zoom_in"),
            (self._act_zoom_out, "tree_zoom_out"),
            (self._act_zoom_fit, "tree_zoom_fit"),
        ):
            act.setToolTip(tr(key))
            act.setStatusTip(tr(key))

        self._menu_theme.setTitle(tr("menu_view_theme"))
        self._act_theme_light.setText(tr("menu_view_theme_light"))
        self._act_theme_dark.setText(tr("menu_view_theme_dark"))
        self._menu_language.setTitle(tr("menu_view_language"))
        self._act_lang_en.setText(tr("menu_view_language_en"))
        self._act_lang_es.setText(tr("menu_view_language_es"))
        self._act_toggle_left.setText(tr("menu_view_toggle_left"))
        self._act_toggle_hud.setText(tr("menu_view_toggle_right"))

        self._act_about.setText(tr("menu_help_about"))

        self._left_gb_explorer.setTitle(tr("panel_left_title"))
        self._left_gb_treemap.setTitle(tr("panel_tree_map"))
        self._left_gb_dataviewer.setTitle(tr("panel_data_viewer"))
        self._hud_title.setText(tr("panel_right_title"))
        # Main tabs (Excel-style sheets): Tree / Gains / Risks / Rules /
        # Summary — each tab fills the whole central area.
        self._main_tabs.setTabText(0, tr("tab_tree"))
        self._main_tabs.setTabText(1, tr("tab_gains"))
        self._main_tabs.setTabText(2, tr("tab_risks"))
        self._main_tabs.setTabText(3, tr("tab_rules"))
        self._main_tabs.setTabText(4, tr("tab_summary"))

        self._refresh_session_indicator()
        self._lbl_mode.setText(f"{tr('status_mode')}: {self._mode_name}")
        self._lbl_theme.setText(
            f"{tr('status_theme')}: {tr(f'menu_view_theme_{self._theme_name}')}"
        )
        self._hud_gb_governance.setTitle(tr("panel_governance"))
        self._hud_lbl_gov_fp_cap.setText(f"{tr('governance_fingerprint')}:")
        self._hud_lbl_gov_mode_cap.setText(f"{tr('governance_mode')}:")
        self._hud_btn_view_audit.setText(tr("governance_view_audit"))
        self._hud_gb_dataset.setTitle(tr("hud_group_dataset"))
        self._hud_gb_node.setTitle(tr("hud_group_node"))
        self._hud_gb_rule.setTitle(tr("hud_group_rule"))
        self._hud_placeholder.setText(tr("tree_prop_empty"))
        self._hud_reset()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _new_action(
        self,
        name: str,
        shortcut: str | None = None,
        *,
        enabled: bool = True,
        tooltip: str | None = None,
        checkable: bool = False,
        checked: bool = False,
    ) -> QAction:
        act = QAction("", self)
        act.setObjectName(name)
        if shortcut is not None:
            act.setShortcut(shortcut)
        act.setEnabled(enabled)
        if tooltip is not None:
            act.setToolTip(tooltip)
            act.setStatusTip(tooltip)
        act.setCheckable(checkable)
        act.setChecked(checked)
        return act

    def _build_menus(self) -> None:
        bar = self.menuBar()

        # --- File ---
        self._menu_file = QMenu(self)
        self._menu_file.setObjectName("menu_file")
        # gated: the wizard needs a loaded dataset (Phase 2.1)
        self._act_new_wizard = self._new_action(
            "act_new_wizard", "Ctrl+N", enabled=False
        )
        self._act_new_wizard.triggered.connect(self._on_new_wizard)
        self._act_open = self._new_action("act_open", "Ctrl+O")
        self._act_open.triggered.connect(self._on_open_dataset)
        self._act_exit = self._new_action("act_exit", "Ctrl+Q")
        self._act_exit.triggered.connect(self.close)
        self._menu_file.addAction(self._act_new_wizard)
        self._menu_file.addAction(self._act_open)
        self._menu_file.addSeparator()
        self._menu_file.addAction(self._act_exit)
        bar.addMenu(self._menu_file)

        # --- Edit (Phase 3.11.a.1: classic menu structure; undo/redo of
        # interactive interventions lands in Phase 3.11.d) ---
        self._menu_edit = QMenu(self)
        self._menu_edit.setObjectName("menu_edit")
        self._act_edit_undo = self._new_action("act_edit_undo", enabled=False)
        self._menu_edit.addAction(self._act_edit_undo)
        bar.addMenu(self._menu_edit)

        # --- View ---
        self._menu_view = QMenu(self)
        self._menu_view.setObjectName("menu_view")

        self._menu_theme = QMenu(self)
        self._menu_theme.setObjectName("menu_theme")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        self._act_theme_light = self._new_action(
            "act_theme_light", checkable=True, checked=True
        )
        self._act_theme_dark = self._new_action("act_theme_dark", checkable=True)
        for act, name in (
            (self._act_theme_light, "light"),
            (self._act_theme_dark, "dark"),
        ):
            act.setData(name)
            theme_group.addAction(act)
            self._menu_theme.addAction(act)
        theme_group.triggered.connect(
            lambda act: self._switch_theme(act.data())
        )
        self._menu_view.addMenu(self._menu_theme)

        self._menu_language = QMenu(self)
        self._menu_language.setObjectName("menu_language")
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)
        self._act_lang_en = self._new_action(
            "act_lang_en", checkable=True, checked=True
        )
        self._act_lang_es = self._new_action("act_lang_es", checkable=True)
        for act, code in (
            (self._act_lang_en, "en"),
            (self._act_lang_es, "es"),
        ):
            act.setData(code)
            lang_group.addAction(act)
            self._menu_language.addAction(act)
        lang_group.triggered.connect(
            lambda act: self._switch_language(act.data())
        )
        self._menu_view.addMenu(self._menu_language)

        self._menu_view.addSeparator()
        self._act_toggle_left = self._new_action(
            "act_toggle_left", checkable=True, checked=True
        )
        self._act_toggle_hud = self._new_action(
            "act_toggle_hud", checkable=True, checked=True
        )
        self._menu_view.addAction(self._act_toggle_left)
        self._menu_view.addAction(self._act_toggle_hud)
        bar.addMenu(self._menu_view)

        # --- Format (placeholder: node/line presentation options) ---
        self._menu_format = QMenu(self)
        self._menu_format.setObjectName("menu_format")
        self._act_format_node_display = self._new_action(
            "act_format_node_display", enabled=False
        )
        self._menu_format.addAction(self._act_format_node_display)
        bar.addMenu(self._menu_format)

        # --- Analysis (placeholder: manual variable types and cost matrix
        # land in Phase 3.11.c) ---
        self._menu_analysis = QMenu(self)
        self._menu_analysis.setObjectName("menu_analysis")
        self._act_analysis_var_types = self._new_action(
            "act_analysis_var_types", enabled=False
        )
        self._menu_analysis.addAction(self._act_analysis_var_types)
        # Phase 3.11.c.2: batch univariate trees (design
        # docs/3.11.c_design_univariate_cost_matrix.md §2.2).
        self._act_univariate = self._new_action("act_univariate", enabled=False)
        self._act_univariate.triggered.connect(self._on_univariate)
        self._menu_analysis.addAction(self._act_univariate)
        bar.addMenu(self._menu_analysis)

        # --- Tree (former Model menu: train opens the wizard; OOS/OOT
        # from Phase 2.3; interactive grow/select land in Phase 3.11.d) ---
        self._menu_tree = QMenu(self)
        self._menu_tree.setObjectName("menu_tree")
        self._act_train = self._new_action("act_train", enabled=False)
        self._act_train.triggered.connect(self._on_new_wizard)
        self._act_evaluate_oos = self._new_action(
            "act_evaluate_oos", enabled=False
        )
        self._act_evaluate_oos.triggered.connect(self._on_evaluate_oos)
        self._act_load_oot = self._new_action(
            "act_load_oot", enabled=False
        )
        self._act_load_oot.triggered.connect(self._on_load_oot)
        self._act_prune = self._new_action("act_prune", enabled=False)
        self._act_prune.triggered.connect(self._on_prune)
        self._menu_tree.addAction(self._act_train)
        self._menu_tree.addAction(self._act_evaluate_oos)
        self._menu_tree.addAction(self._act_load_oot)
        self._menu_tree.addAction(self._act_prune)
        bar.addMenu(self._menu_tree)

        # --- Window (placeholder: management of open model views) ---
        self._menu_window = QMenu(self)
        self._menu_window.setObjectName("menu_window")
        self._act_window_tile = self._new_action(
            "act_window_tile", enabled=False
        )
        self._menu_window.addAction(self._act_window_tile)
        bar.addMenu(self._menu_window)

        # --- Help ---
        self._menu_help = QMenu(self)
        self._menu_help.setObjectName("menu_help")
        self._act_about = self._new_action("act_about")
        self._act_about.triggered.connect(self._show_about)
        self._menu_help.addAction(self._act_about)
        bar.addMenu(self._menu_help)

        # Reflect the active language in the exclusive language group
        # (set_language() runs before _build_menus in __init__).
        current = get_language()
        self._act_lang_en.setChecked(current == "en")
        self._act_lang_es.setChecked(current == "es")

    def _build_toolbar(self) -> None:
        self._toolbar = QToolBar("Main Toolbar", self)
        self._toolbar.setObjectName("mainToolbar")
        self.addToolBar(self._toolbar)

        style = self.style()
        self._act_open.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self._act_new_wizard.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self._act_train.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self._act_evaluate_oos.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self._act_load_oot.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self._act_prune.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        self._toolbar.addAction(self._act_open)
        self._toolbar.addAction(self._act_new_wizard)
        self._toolbar.addAction(self._act_train)
        self._toolbar.addAction(self._act_evaluate_oos)
        self._toolbar.addAction(self._act_load_oot)
        self._toolbar.addAction(self._act_prune)
        self._toolbar.addSeparator()

        self._act_zoom_in = self._new_action("act_zoom_in")
        self._act_zoom_in.triggered.connect(self._tree_panel.zoom_in)
        self._act_zoom_out = self._new_action("act_zoom_out")
        self._act_zoom_out.triggered.connect(self._tree_panel.zoom_out)
        self._act_zoom_fit = self._new_action("act_zoom_fit")
        self._act_zoom_fit.triggered.connect(self._tree_panel.zoom_fit)

        self._act_zoom_in.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self._act_zoom_out.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self._act_zoom_fit.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))

        self._toolbar.addAction(self._act_zoom_in)
        self._toolbar.addAction(self._act_zoom_out)
        self._toolbar.addAction(self._act_zoom_fit)

        # Phase 3.11.a.1: classic compact toolbar (icon only). Applied
        # AFTER all actions are added so every button honors the style.
        # With IconOnly the QAction text is not visible: the tooltips
        # set in retranslate_ui() carry the labels.
        self._toolbar.setIconSize(QSize(16, 16))
        self._toolbar.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )

    def _build_central(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("centralSplitter")

        # Phase 3.11.a.1 (Estándar Clásico de Estaciones de Árboles,
        # circa 2001): left panel is a
        # vertical splitter with three stacked group boxes — Project
        # Explorer, Tree Map (minimap, lands in 3.11.b) and Data Viewer
        # (lands in 3.11.b).
        self._left_panel = QSplitter(Qt.Orientation.Vertical)
        self._left_panel.setObjectName("leftPanel")
        self._left_gb_explorer = self._make_left_groupbox("gbProjectExplorer")
        # Phase 3.11.b.4: Project Explorer — identidad del modelo activo
        self._lbl_explorer_model = QLabel("—")
        self._lbl_explorer_model.setWordWrap(True)
        self._left_gb_explorer.layout().addWidget(self._lbl_explorer_model)
        self._left_gb_treemap = self._make_left_groupbox("gbTreeMap")
        self._left_gb_dataviewer = self._make_left_groupbox("gbDataViewer")
        self._left_panel.addWidget(self._left_gb_explorer)
        self._left_panel.addWidget(self._left_gb_treemap)
        self._left_panel.addWidget(self._left_gb_dataviewer)
        # Phase 3.11.b.2: contenido del bloque Data Viewer (preview crudo
        # del CSV via Session.get_data_preview; Explorer llega en b.4).
        self._data_viewer = DataViewer(self._left_gb_dataviewer)
        self._left_gb_dataviewer.layout().addWidget(self._data_viewer)
        # Phase 3.11.b.3: contenido del bloque Tree Map (minimapa pasivo,
        # decisión D2: escena propia e independiente; clic -> panning del
        # canvas principal sin tocar su zoom ni su selección).
        self._tree_map = TreeMap(self._left_gb_treemap)
        self._left_gb_treemap.layout().addWidget(self._tree_map)
        self._tree_map.node_clicked.connect(self._on_tree_map_node_clicked)

        self._hud_panel, self._hud_title = self._make_panel("hudPanel")
        # Phase 3.10.a: structured properties panel (Dataset / Node / Rule)
        self._build_hud_panel_content(self._hud_panel.layout())
        # Bounded properties panel: collapsible via the View menu, and
        # never oversized (the splitter cannot stretch it past 400 px).
        self._hud_panel.setMinimumWidth(200)
        self._hud_panel.setMaximumWidth(400)

        # Phase 2.2: interactive tree canvas (empty until TRAINED).
        # Phase 3.11.a.1 (classic layout): the canvas is the FIXED upper
        # pane of the central vertical splitter, above the main tabs.
        self._tree_panel = TreePanel()
        self._tree_panel.setObjectName("treePanel")
        self._tree_panel.node_selected.connect(self._on_tree_node_selected)
        self._tree_panel.selection_cleared.connect(self._hud_reset)
        # Phase 3.11.d.2: menú contextual del analista (clic derecho
        # sobre un NodeItem del canvas principal).
        self._tree_panel._scene.node_context_menu.connect(
            self._on_tree_context_menu
        )
        # Phase 3.11.b.3 (D2): resaltado pasivo del minimapa — refleja la
        # selección del canvas principal y nunca la propaga.
        self._tree_panel.node_selected.connect(self._tree_map.set_selected_node)
        self._tree_panel.selection_cleared.connect(
            lambda: self._tree_map.set_selected_node(None)
        )

        # Phase 2.3: OOS/OOT metrics panel (main "Risks" tab)
        self._metrics_panel = MetricsPanel()
        self._metrics_panel.setObjectName("metricsPanel")
        self._metrics_panel.inversion_requested.connect(
            self._on_inversion_requested
        )

        self._reports_panel = ReportsPanel()
        self._reports_panel.setObjectName("reportsPanel")
        self._reports_panel.partition_changed.connect(
            self._on_reports_partition_changed
        )
        self._reports_panel.view_changed.connect(
            self._on_reports_view_changed
        )
        self._reports_panel.threshold_changed.connect(
            self._on_reports_threshold_changed
        )
        self._reports_panel.refresh_requested.connect(
            self._refresh_reports_panel
        )

        # Main tab widget fills the WHOLE central area (Phase 3.11.a.1
        # correction): the tab bar is anchored at the BOTTOM of the
        # window (TabPosition.South), Excel-sheet style. Sheets: Tree
        # (the canvas) / Gains / Risks / Rules / Summary. Rules and
        # Summary are placeholders until sub-phases 3.11.b-d fill them.
        self._main_tabs = QTabWidget()
        self._main_tabs.setObjectName("centralTabs")
        self._main_tabs.setTabPosition(QTabWidget.TabPosition.South)
        self._main_tabs.addTab(self._tree_panel, "")
        self._main_tabs.addTab(self._reports_panel, "")
        self._main_tabs.addTab(self._metrics_panel, "")
        self._tab_rules = self._make_placeholder_tab("tabRules")
        self._main_tabs.addTab(self._tab_rules, "")
        self._tab_summary = self._make_placeholder_tab("tabSummary")
        self._main_tabs.addTab(self._tab_summary, "")

        splitter.addWidget(self._left_panel)
        splitter.addWidget(self._main_tabs)
        splitter.addWidget(self._hud_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)
        # Priority to the center sheet; the HUD starts within its bounds.
        splitter.setSizes([250, 800, 300])
        self.setCentralWidget(splitter)

        self._act_toggle_left.toggled.connect(self._left_panel.setVisible)
        self._act_toggle_hud.toggled.connect(self._hud_panel.setVisible)
        return splitter

    def _make_left_groupbox(self, name: str) -> QGroupBox:
        """Empty stacked block of the left panel (Phase 3.11.a.1). Content
        (Explorer list, minimap, data grid) lands in sub-phase 3.11.b."""
        gb = QGroupBox()
        gb.setObjectName(name)
        QVBoxLayout(gb)
        return gb

    def _make_panel(self, name: str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setObjectName(name)
        layout = QVBoxLayout(frame)
        title = QLabel()
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addStretch(1)
        return frame, title

    def _make_placeholder_tab(self, name: str) -> QWidget:
        """Empty placeholder tab (Phase 3.11.a). Real content lands in
        sub-phases 3.11.b-d."""
        widget = QWidget()
        widget.setObjectName(name)
        lay = QVBoxLayout(widget)
        lbl = QLabel("—")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)
        return widget

    def _build_hud_panel_content(self, layout: QVBoxLayout) -> None:
        # 0. Gobernanza MRM (Phase 3.11.a): fingerprint, mode, audit access
        self._hud_gb_governance = QGroupBox()
        form_gov = QFormLayout(self._hud_gb_governance)
        self._hud_lbl_gov_fp_cap = QLabel()
        self._hud_lbl_gov_fp = QLabel("—")
        self._hud_lbl_gov_fp.setWordWrap(True)
        # copiable: the fingerprint is auditor-facing data
        self._hud_lbl_gov_fp.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._hud_lbl_gov_mode_cap = QLabel()
        self._hud_lbl_gov_mode = QLabel("—")
        self._hud_btn_view_audit = QPushButton()
        # placeholder: the audit viewer lands in Phase 3.11.d
        self._hud_btn_view_audit.setEnabled(False)
        form_gov.addRow(self._hud_lbl_gov_fp_cap, self._hud_lbl_gov_fp)
        form_gov.addRow(self._hud_lbl_gov_mode_cap, self._hud_lbl_gov_mode)
        form_gov.addRow(self._hud_btn_view_audit)
        layout.insertWidget(1, self._hud_gb_governance)

        # 1. Dataset
        self._hud_gb_dataset = QGroupBox()
        form_ds = QFormLayout(self._hud_gb_dataset)
        self._hud_lbl_file = QLabel("—")
        self._hud_lbl_rows = QLabel("—")
        self._hud_lbl_cols = QLabel("—")
        form_ds.addRow("File:", self._hud_lbl_file)
        form_ds.addRow("Rows:", self._hud_lbl_rows)
        form_ds.addRow("Cols:", self._hud_lbl_cols)
        layout.insertWidget(2, self._hud_gb_dataset)

        # 2. Nodo
        self._hud_gb_node = QGroupBox()
        form_node = QFormLayout(self._hud_gb_node)
        self._hud_lbl_pop = QLabel("—")
        self._hud_lbl_events = QLabel("—")
        self._hud_lbl_bad_rate = QLabel("—")
        self._hud_bar = QProgressBar()
        self._hud_bar.setTextVisible(False)
        self._hud_bar.setFixedHeight(12)
        form_node.addRow("Pop:", self._hud_lbl_pop)
        form_node.addRow("Events:", self._hud_lbl_events)
        form_node.addRow("Bad Rate:", self._hud_lbl_bad_rate)
        form_node.addRow(self._hud_bar)
        layout.insertWidget(3, self._hud_gb_node)

        # 3. Regla
        self._hud_gb_rule = QGroupBox()
        form_rule = QFormLayout(self._hud_gb_rule)
        self._hud_lbl_rule_var = QLabel("—")
        self._hud_lbl_rule_cond = QLabel("—")
        self._hud_lbl_rule_stat = QLabel("—")
        self._hud_lbl_rule_p = QLabel("—")
        form_rule.addRow("Var:", self._hud_lbl_rule_var)
        form_rule.addRow("Cond:", self._hud_lbl_rule_cond)
        form_rule.addRow("Stat:", self._hud_lbl_rule_stat)
        form_rule.addRow("p-val:", self._hud_lbl_rule_p)
        layout.insertWidget(4, self._hud_gb_rule)

        self._hud_placeholder = QLabel()
        self._hud_placeholder.setWordWrap(True)
        layout.insertWidget(5, self._hud_placeholder)
        layout.addStretch(1)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        self._lbl_session = QLabel()
        self._lbl_session.setObjectName("statusSessionLabel")
        self._lbl_mode = QLabel()
        self._lbl_mode.setObjectName("statusModeLabel")
        self._lbl_theme = QLabel()
        self._lbl_theme.setObjectName("statusThemeLabel")
        sb.addPermanentWidget(self._lbl_session)
        sb.addPermanentWidget(self._lbl_mode)
        sb.addPermanentWidget(self._lbl_theme)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _switch_theme(self, name: str) -> None:
        apply_theme(name)  # operates on the running QApplication
        # Phase 3.11.a.1: re-pin the QPalette too, so native-rendered
        # chrome (wizard/dialogs) follows the new theme, not Windows'.
        apply_palette(name, QApplication.instance())
        self._theme_name = name
        self._lbl_theme.setText(
            f"{tr('status_theme')}: {tr(f'menu_view_theme_{name}')}"
        )
        # QGraphicsItems ignore the app QSS: recolor the scene explicitly
        self._tree_panel.set_theme(name)
        self._tree_map.set_theme(name)
        if self._logger is not None:
            self._logger.info("Theme switched to %s", name)

    # ------------------------------------------------------------------
    # Slots (Phase 2.1: dataset load + transactional wizard orchestration)
    # ------------------------------------------------------------------

    def _on_open_dataset(self) -> None:
        path, _filt = QFileDialog.getOpenFileName(
            self, tr("dlg_open_dataset_title"), "",
            tr("dlg_open_dataset_filter"),
        )
        if path:
            self._load_dataset_path(path)

    def _load_dataset_path(self, path: str) -> bool:
        """Load a CSV into a fresh Session and cache its profile (columns,
        inferred types). Returns True on success. Dialog-free so tests can
        drive it headless."""
        if self._session is None:
            self._session = Session()
        if not self._run_guarded(self._session.load_dataset, path):
            return False

        if not self._security_warning_shown:
            app = QApplication.instance()
            if app is not None and app.platformName() != "offscreen":
                QMessageBox.warning(
                    self,
                    tr("security_warning_title"),
                    tr("security_warning_body"),
                )
            self._security_warning_shown = True
            if self._logger is not None:
                self._logger.info("[gui] security warning shown on first dataset load")
        columns, types = self._session.describe_dataset()
        self._dataset_info = (columns, types)
        # Phase 3.11.b.2: preview crudo del CSV en el Data Viewer
        # (contrato D3; dict de tipos puros, nunca lanza sin dataset).
        self._data_viewer.set_preview(self._session.get_data_preview())
        self._current_dataset_path = path
        self._act_new_wizard.setEnabled(True)
        self._act_train.setEnabled(True)
        self._refresh_session_indicator()
        st = self._session.state
        self.statusBar().showMessage(
            f"{os.path.basename(path)} — {st.n_rows} × {st.n_cols}"
        )
        if self._logger is not None:
            self._logger.info("Dataset loaded via GUI: %s", path)
        return True

    def _on_new_wizard(self) -> None:
        if self._dataset_info is None or self._session is None:
            return
        # reconfigure over the SAME loaded dataset (no CSV re-IO) when the
        # session already advanced past DATA_LOADED
        if self._session.state.state is not FlowState.DATA_LOADED:
            self._session.reset_to_data_loaded()
            # transactional consistency: the session no longer holds a
            # tree, so the viewer must not keep displaying the old one
            self._tree_panel.clear_model()
            self._tree_map.set_model(None)
            self._metrics_panel.set_report(None)
            self._reports_panel.set_gains_table(None)
            self._reports_panel.set_classification_matrix(None)
            self._data_viewer.set_preview(None)
            # Phase 3.11.b.4: Project Explorer vuelve al estado vacío
            self._lbl_explorer_model.setText("—")
            self._hud_lbl_gov_fp.setText("—")
            self._hud_lbl_gov_mode.setText("—")
            self._hud_reset()
        columns, types = self._dataset_info
        wiz = ModelWizard(
            columns, types,
            target_provider=lambda col: self._session.describe_target(col),
            weight_validator=self._weight_validator,
            population_provider=lambda col: (
                self._session.describe_population_column(col)
                if self._session is not None else {"exists": False, "n": 0, "values": ()}
            ),
            parent=self,
        )
        wiz.finished_with_config.connect(self._on_wizard_finished)
        wiz.finished.connect(self._on_wizard_closed)
        self._wizard = wiz
        # one configuration at a time; View (theme/language) stays active
        self._act_open.setEnabled(False)
        self._act_new_wizard.setEnabled(False)
        self._act_train.setEnabled(False)
        wiz.show()

    def _on_wizard_closed(self, _result: int) -> None:
        if self._wizard is not None:
            self._wizard.deleteLater()
            self._wizard = None
        self._act_open.setEnabled(True)
        has_ds = self._dataset_info is not None
        self._act_new_wizard.setEnabled(has_ds)
        self._act_train.setEnabled(has_ds)

    def _on_wizard_finished(self, cfg: dict) -> None:
        """Consume the wizard config: fix_spec -> partition -> train."""
        if self._session is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok = self._run_guarded(self._train_pipeline, cfg,
                                   reset_on_error=True)
        finally:
            QApplication.restoreOverrideCursor()
        if not ok:
            # rollback already applied (reset_on_error); the viewer must
            # not keep a tree the session state no longer holds
            self._tree_panel.clear_model()
            self._tree_map.set_model(None)
            self._hud_reset()
            return
        st = self._session.state
        self._last_train_cfg = dict(cfg)  # defensive copy (no aliasing)
        self._mode_name = (
            "Banking" if cfg["governance_mode"] == "BANKING" else "Research"
        )
        self._refresh_session_indicator()
        self._lbl_mode.setText(f"{tr('status_mode')}: {self._mode_name}")
        tree = st.tree
        if tree is not None:
            self._tree_panel.set_model(tree, cfg["governance_mode"])
            # Phase 3.11.b.4: Project Explorer refleja el modelo entrenado
            if tree is not None:
                self._lbl_explorer_model.setText(f"{tree.method} · {tree.params_fingerprint[:8]}")
            # Phase 3.11.b.3 (D2): el minimapa se reconstruye completo
            # ante cualquier cambio del modelo (fit/poda/nuevo CSV).
            self._tree_map.set_model(tree)
            # Phase 3.11.a: governance panel shows the model identity
            self._hud_lbl_gov_fp.setText(tree.params_fingerprint)
            self._hud_lbl_gov_mode.setText(cfg["governance_mode"])
            self._hud_reset()
            if self._logger is not None:
                self._logger.info(
                    "[gui] tree rendered: %s | nodos=%d | fp=%s",
                    tree.method, len(tree.nodes), tree.params_fingerprint,
                )
            self.statusBar().showMessage(
                tr("msg_model_trained").format(
                    method=tree.method, n=len(tree.nodes)
                ),
                8000,
            )
        # Phase 2.3.e.5: refresh OOS/OOT panel with current report
        self._metrics_panel.set_report(self._session.get_oos_oot_report())
        self._refresh_reports_panel()

    def _on_inversion_requested(self) -> None:
        """Invert the class of interest and retrain with the same cfg (3.1.f).

        Triggered by MetricsPanel.inversion_requested (negative OOS Gini).
        Reuses the stored wizard cfg; only the binary case (K=2) applies.
        """
        if self._session is None or self._last_train_cfg is None:
            if self._logger is not None:
                self._logger.warning(
                    "[gui] inversion_requested ignored: no trained cfg stored"
                )
            return
        tree = self._session.state.tree
        if tree is None or len(tree.class_labels) != 2:
            if self._logger is not None:
                self._logger.warning(
                    "[gui] inversion_requested ignored: model is not binary"
                )
            return
        old_class = self._last_train_cfg["target_class"]
        if old_class not in (0, 1):
            if self._logger is not None:
                self._logger.warning(
                    "[gui] inversion_requested ignored: unexpected "
                    "target_class=%r", old_class,
                )
            return
        new_class = 1 - int(old_class)
        # confirmation dialog (skipped under offscreen so CI never hangs)
        app = QApplication.instance()
        if app is not None and app.platformName() != "offscreen":
            answer = QMessageBox.question(
                self,
                tr("inversion_confirm_title"),
                tr("inversion_confirm_message"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        cfg_inv = dict(self._last_train_cfg)
        cfg_inv["target_class"] = new_class
        # class_labels stay as-is: they describe the target VALUES, not
        # the class of interest
        self._session.reset_to_data_loaded()
        ok = self._run_guarded(self._train_pipeline, cfg_inv,
                               reset_on_error=True)
        if not ok:
            # _run_guarded already reset to DATA_LOADED and showed the error
            return
        self._last_train_cfg = cfg_inv
        tree = self._session.state.tree
        if tree is not None:
            # transactional consistency: the viewer must not keep showing
            # the pre-inversion tree (same rule as _on_wizard_finished)
            self._tree_panel.set_model(tree, cfg_inv["governance_mode"])
            self._tree_map.set_model(tree)
        self._metrics_panel.set_report(self._session.get_oos_oot_report())
        self._refresh_reports_panel()
        self._refresh_session_indicator()
        if self._logger is not None:
            self._logger.info(
                tr("inversion_log_narrative").format(
                    from_class=old_class, to_class=new_class
                )
            )

    def _weight_validator(self, col: str) -> bool:
        """True si la columna de pesos es utilizable (existe, todos sus
        valores son finitos, estrictamente positivos y sin NaN).
        False en cualquier otro caso."""
        if self._session is None:
            return False
        info = self._session.describe_weight_column(col)
        return bool(
            info["exists"] is True
            and info["n_nonpositive"] == 0
            and info["n_nan"] == 0
        )

    def _train_pipeline(self, cfg: dict) -> None:
        self._session.fix_spec(
            cfg["target"],
            predictors=cfg["predictors"],
            target_class=cfg["target_class"],
            class_labels=cfg["class_labels"],
            weight_col=cfg["weight_col"],
            population_col=cfg["population_col"],
            population_ok_values=cfg["population_ok_values"],
            cost_matrix=cfg.get("cost_matrix", ()),
        )
        self._session.partition(cfg["train_frac"], cfg["seed"])
        self._session.train(
            cfg["engine"],
            max_depth=cfg["max_depth"],
            min_child_size=cfg["min_child_size"],
            min_child_weight=cfg["min_child_weight"],
            pd_floor=cfg["pd_floor"],
            apply_jeffreys=cfg["apply_jeffreys"],
        )

    def _run_guarded(
        self,
        fn: Callable,
        *args,
        reset_on_error: bool = False,
        **kwargs,
    ) -> bool:
        """Run a backend call; on exception: full trace to the log, state
        rollback via reset_to_data_loaded (if requested), and a user dialog
        (suppressed under offscreen so CI never hangs on a modal)."""
        try:
            fn(*args, **kwargs)
            return True
        except Exception as exc:  # noqa: BLE001 - last UI line of defense
            if self._logger is not None:
                self._logger.exception("Backend operation failed")
            if reset_on_error and self._session is not None:
                try:
                    self._session.reset_to_data_loaded()
                except ValueError:
                    pass  # nothing loaded to reset
            app = QApplication.instance()
            if app is not None and app.platformName() != "offscreen":
                QMessageBox.warning(self, tr("msg_error_title"), str(exc))
            self._refresh_session_indicator()
            return False

    def _refresh_session_indicator(self) -> None:
        name = (
            self._session.state.state.name
            if self._session is not None
            else "—"
        )
        self._lbl_session.setText(f"{tr('status_session')}: {name}")
        # Phase 2.3.e.5: OOS/OOT actions depend on Session state.
        trained = (
            self._session is not None
            and self._session.state.state is FlowState.TRAINED
        )
        self._act_evaluate_oos.setEnabled(trained)
        self._act_load_oot.setEnabled(trained)
        self._act_prune.setEnabled(trained)
        self._act_univariate.setEnabled(trained)
        has_tree = self._session is not None and self._session.state.tree is not None
        if hasattr(self, "_act_zoom_in"):
            self._act_zoom_in.setEnabled(has_tree)
            self._act_zoom_out.setEnabled(has_tree)
            self._act_zoom_fit.setEnabled(has_tree)
        state = (
            self._session.state.state
            if self._session is not None
            else FlowState.EMPTY
        )
        train_ok = state in (
            FlowState.TRAINED, FlowState.OOT_LOADED, FlowState.OOT_EVALUATED
        )
        oos_ok = train_ok
        oot_ok = state in (
            FlowState.OOT_LOADED, FlowState.OOT_EVALUATED
        )
        self._reports_panel.set_session_available(
            train=train_ok, oos=oos_ok, oot=oot_ok
        )

    # ------------------------------------------------------------------
    # Slots (Phase 2.2: tree viewer -> properties panel)
    # ------------------------------------------------------------------

    def _on_tree_map_node_clicked(self, node_id: int) -> None:
        """Clic en el minimapa -> panning del canvas principal al nodo
        (centerOn sobre su centro), SIN tocar su zoom ni su selección
        (D2; invariante 4 del diseño 3.11.b: el mapa es pasivo)."""
        center = self._tree_map.node_pos(node_id)
        if center is not None:
            self._tree_panel._view.centerOn(*center)

    def _on_tree_node_selected(self, node_id: int) -> None:
        """Show the selected node card (read-only, from the frozen tree)."""
        model = self._session.state.tree if self._session is not None else None
        if model is None or not (0 <= node_id < len(model.nodes)):
            return
        node = model.nodes[node_id]
        self._update_hud_node(node)
        self.statusBar().showMessage(f"{tr('tree_prop_node')} #{node_id}", 5000)

    def _on_tree_context_menu(self, node_id: int) -> None:
        """Clic derecho sobre un nodo del canvas (Fase 3.11.d.2).

        Menú contextual del analista (Grow Tree / Prune Branch), solo
        con modelo entrenado. Grow se habilita en hojas; Prune en nodos
        internos. En modo BANKING la poda manual exige confirmación
        explícita (QMessageBox); en RESEARCH se aplica directamente.
        Toda intervención queda registrada en el Manual Override Log del
        backend (SessionState.manual_overrides) y sufija el fingerprint.
        """
        if self._session is None or self._session.state.tree is None:
            return
        tree = self._session.state.tree
        if not (0 <= node_id < len(tree.nodes)):
            return
        node = tree.nodes[node_id]
        mode = (
            self._last_train_cfg.get("governance_mode", "BANKING")
            if self._last_train_cfg is not None
            else "BANKING"
        )
        # TODO(zona_gris): textos del menú literales, sin claves i18n;
        # resolver con claves tree_ctx_* al cerrar la fase 3.11.d.
        menu = QMenu(self)
        act_grow = menu.addAction("Grow Tree")
        act_grow.setEnabled(node.is_leaf)
        act_prune = menu.addAction("Prune Branch")
        act_prune.setEnabled(not node.is_leaf)
        chosen = menu.exec(QCursor.pos())
        if chosen is act_prune:
            if mode == "BANKING":
                answer = QMessageBox.question(
                    self,
                    "Prune Branch",
                    f"Podar la rama del nodo {node_id}: la intervención "
                    "manual quedará registrada en el Manual Override Log "
                    "y alterará el fingerprint del modelo. ¿Continuar?",
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            ok = self._run_guarded(
                self._session.intervene_node, node_id, "prune_branch"
            )
            if not ok:
                return
            new_tree = self._session.state.tree
            self._tree_panel.set_model(new_tree, mode)
            self._tree_map.set_model(new_tree)
            self._refresh_session_indicator()
            if self._logger is not None:
                self._logger.info(
                    "[gui] intervene prune_branch: node=%d | nodos=%d",
                    node_id, len(new_tree.nodes),
                )
            self.statusBar().showMessage(
                f"Prune Branch #{node_id} | "
                f"fp={new_tree.params_fingerprint}",
                8000,
            )
        elif chosen is act_grow:
            # TODO(3.11.d.3): Grow Tree (y Select Predictor / Define
            # Split) llegan cuando el backend implemente esas acciones
            # en Session.intervene_node.
            pass

    def _hud_reset(self) -> None:
        """Properties panel default: node detail if selected, else clear."""
        model = self._session.state.tree if self._session is not None else None
        sel = self._tree_panel.selected_node_id()
        if model is not None and (sel is not None and 0 <= sel < len(model.nodes)):
            self._update_hud_node(model.nodes[sel])
        else:
            self._clear_hud()

    def _on_evaluate_oos(self) -> None:
        """Model > Evaluate OOS: runs evaluate_oos() on the trained model."""
        if self._session is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok = self._run_guarded(self._session.evaluate_oos)
        finally:
            QApplication.restoreOverrideCursor()
        if not ok:
            return
        self._metrics_panel.set_report(self._session.get_oos_oot_report())
        self._refresh_reports_panel()
        self._main_tabs.setCurrentWidget(self._metrics_panel)
        self._refresh_session_indicator()
        if self._logger is not None:
            self._logger.info("[gui] OOS evaluation done")

    def _on_load_oot(self) -> None:
        """Model > Load OOT Cohort: pick a CSV, load, then evaluate."""
        if self._session is None:
            return
        path, _filt = QFileDialog.getOpenFileName(
            self, tr("dlg_open_dataset_title"), "",
            tr("dlg_open_dataset_filter"),
        )
        if not path:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok = self._run_guarded(self._load_oot_pipeline, path)
        finally:
            QApplication.restoreOverrideCursor()
        if not ok:
            return
        self._metrics_panel.set_report(self._session.get_oos_oot_report())
        self._refresh_reports_panel()
        self._main_tabs.setCurrentWidget(self._metrics_panel)
        self._refresh_session_indicator()
        if self._logger is not None:
            self._logger.info("[gui] OOT loaded and evaluated: %s", path)

    def _load_oot_pipeline(self, path: str) -> None:
        self._session.load_oot(path)
        self._session.evaluate_oot()

    def _on_prune(self) -> None:
        """Model > Prune Tree: interactive cost-complexity pruning (3.9).

        The dialog applies Session.prune(alpha) itself; on Accepted the
        viewer is RE-BOUND to the pruned tree (TreePanel.refresh() alone
        would keep rendering the original model bound by set_model).
        """
        if self._session is None or self._session.state.tree is None:
            return
        dlg = PruneDialog(self._session, language_bus, self,
                          logger=self._logger)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        st = self._session.state
        tree = st.pruned_tree if st.pruned_tree is not None else st.tree
        mode = (
            self._last_train_cfg.get("governance_mode", "BANKING")
            if self._last_train_cfg is not None
            else "BANKING"
        )
        self._tree_panel.set_model(tree, mode)
        self._tree_map.set_model(tree)
        self._metrics_panel.refresh()
        self._refresh_reports_panel()
        self._refresh_session_indicator()
        if self._logger is not None:
            self._logger.info(
                "[gui] pruning applied: alpha=%s | nodos=%d",
                st.prune_alpha, len(tree.nodes),
            )
        self.statusBar().showMessage(
            tr("msg_model_pruned").format(
                alpha=st.prune_alpha, n=len(tree.nodes)
            ),
            8000,
        )

    def _on_univariate(self) -> None:
        """Analysis > Generate Univariate Trees (Phase 3.11.c.2).

        Reads the flat DTO from Session.get_univariate_trees() and shows
        it in a modal dialog. Read-only: the session state is untouched.
        """
        if self._session is None or self._session.state.tree is None:
            return
        try:
            data = self._session.get_univariate_trees(max_depth=3)
        except Exception as exc:
            QMessageBox.warning(self, tr("msg_error_title"), str(exc))
            return
        dlg = UnivariateDialog(self, logger=self._logger)
        dlg.set_data(data)
        dlg.exec()

    def _on_reports_partition_changed(self, _partition: str) -> None:
        """Partition combo changed: recompute gains table and matrix."""
        self._refresh_reports_panel()

    def _on_reports_view_changed(self, _view: str, _n_buckets: int) -> None:
        """View (terminal-node/bucket) or bucket count changed: recompute gains table."""
        self._refresh_reports_panel()

    def _on_reports_threshold_changed(self, _threshold: float) -> None:
        """Threshold changed: recompute classification matrix."""
        self._refresh_reports_panel()

    def _refresh_reports_panel(self) -> None:
        """Fetch gains table and classification matrix from Session and push
        them into ReportsPanel. Silent on unavailable partitions (shows
        empty state instead of failing)."""
        if self._session is None:
            self._reports_panel.set_gains_table(None)
            self._reports_panel.set_classification_matrix(None)
            return
        state = self._session.state.state
        if state not in (
            FlowState.TRAINED, FlowState.OOT_LOADED, FlowState.OOT_EVALUATED
        ):
            self._reports_panel.set_gains_table(None)
            self._reports_panel.set_classification_matrix(None)
            return
        partition = self._reports_panel.current_partition()
        view = self._reports_panel.current_view()
        n_buckets = self._reports_panel.current_n_buckets()
        threshold = self._reports_panel.current_threshold()
        try:
            gains = self._session.get_gains_table(
                partition=partition, by=view, n_buckets=n_buckets
            )
            matrix = self._session.get_classification_matrix(
                partition=partition, threshold=threshold
            )
        except (RuntimeError, ValueError) as exc:
            if self._logger is not None:
                self._logger.warning(
                    "[gui] reports panel refresh failed: %s", exc
                )
            self._reports_panel.set_gains_table(None)
            self._reports_panel.set_classification_matrix(None)
            return
        self._reports_panel.set_gains_table(gains)
        self._reports_panel.set_classification_matrix(matrix)

    def _switch_language(self, lang: str) -> None:
        set_language(lang)
        QSettings().setValue("language", lang)
        self.retranslate_ui()
        language_bus.language_changed.emit(lang)  # wizard & future dialogs
        if self._logger is not None:
            self._logger.info("Language switched to %s", lang)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            tr("about_title"),
            tr("about_body").format(version=__version__),
        )

    def _clear_hud(self) -> None:
        self._hud_placeholder.setVisible(True)
        self._hud_gb_node.setVisible(False)
        self._hud_gb_rule.setVisible(False)
        if self._session is not None and self._session.state.state is not None:
            self._hud_gb_dataset.setVisible(True)
            st = self._session.state
            self._hud_lbl_file.setText(self._current_dataset_path.split("\\")[-1] if self._current_dataset_path else "—")
            self._hud_lbl_rows.setText(str(st.n_rows))
            self._hud_lbl_cols.setText(str(st.n_cols))
        else:
            self._hud_gb_dataset.setVisible(False)

    def _update_hud_node(self, node) -> None:
        self._hud_placeholder.setVisible(False)
        self._hud_gb_node.setVisible(True)
        self._hud_gb_rule.setVisible(True)
        self._clear_hud_dataset_info()

        # Populate Node
        self._hud_lbl_pop.setText(str(node.n))
        events = node.n_events[0] if node.n_events else 0
        self._hud_lbl_events.setText(str(events))
        pd_val = node.pd_final[0] if node.pd_final else 0.0
        self._hud_lbl_bad_rate.setText(f"{pd_val * 100:.2f}%")

        self._hud_bar.setMinimum(0)
        self._hud_bar.setMaximum(100)
        self._hud_bar.setValue(int(pd_val * 100))

        # Style the bar (red for high PD, green for low)
        color = "#2E7D32" if pd_val < 0.05 else ("#ED6C02" if pd_val < 0.15 else "#D32F2F")
        self._hud_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")

        # Populate Rule
        if node.is_leaf:
            self._hud_lbl_rule_var.setText(tr("tree_node_terminal"))
            self._hud_lbl_rule_cond.setText(tr(f"tree_terminal_reason_{node.leaf_reason}"))
            self._hud_lbl_rule_stat.setText("—")
            self._hud_lbl_rule_p.setText("—")
        else:
            split = node.split
            self._hud_lbl_rule_var.setText(str(split.predictor))
            if split.threshold is not None:
                cond = f"≤ {split.threshold:.4g}"
            else:
                cond = f"{len(split.branches or ())} groups"
            self._hud_lbl_rule_cond.setText(cond)
            self._hud_lbl_rule_stat.setText(f"{split.statistic_name} = {split.statistic:.4g}")
            if split.p_value is not None:
                p_str = f"{split.p_value:.4g}"
                if split.p_value_adjusted is not None:
                    p_str += f" (adj: {split.p_value_adjusted:.4g})"
                self._hud_lbl_rule_p.setText(p_str)
            else:
                self._hud_lbl_rule_p.setText("—")

    def _clear_hud_dataset_info(self) -> None:
        self._hud_gb_dataset.setVisible(True)
        st = self._session.state if self._session else None
        if st:
            fname = self._current_dataset_path.split("\\")[-1] if self._current_dataset_path else "—"
            self._hud_lbl_file.setText(fname)
            self._hud_lbl_rows.setText(str(st.n_rows))
            self._hud_lbl_cols.setText(str(st.n_cols))

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        # Nothing to release manually (Qt parentage owns the widgets and
        # log_config owns the log handlers); just leave an audit trail.
        if self._logger is not None:
            self._logger.info("GUI closed cleanly")
        super().closeEvent(event)
