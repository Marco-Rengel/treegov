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

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QTabWidget,
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
from frontend_v3.theme import apply_theme
from frontend_v3.tree_view import (
    TreePanel,
    model_summary_lines,
    node_detail_lines,
)
from frontend_v3.metrics_panel import MetricsPanel
from frontend_v3.reports_panel import ReportsPanel
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
        self._wizard: ModelWizard | None = None
        self._mode_name: str = "—"

        # Language before any widget text is built. QSettings without an
        # eager default: detect_system_language() runs only when unset,
        # and a corrupt stored value falls back to detection.
        lang = QSettings().value("language")
        set_language(lang if lang in SUPPORTED else detect_system_language())

        self._build_menus()
        self._build_central()
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
        self._menu_model.setTitle(tr("menu_model"))
        self._menu_view.setTitle(tr("menu_view"))
        self._menu_help.setTitle(tr("menu_help"))

        self._act_new_wizard.setText(tr("menu_file_new_wizard"))
        self._act_open.setText(tr("menu_file_open"))
        self._act_exit.setText(tr("menu_file_exit"))
        self._act_train.setText(tr("menu_model_train"))
        self._act_evaluate_oos.setText(tr("menu_model_evaluate_oos"))
        self._act_load_oot.setText(tr("menu_model_load_oot"))

        self._menu_theme.setTitle(tr("menu_view_theme"))
        self._act_theme_light.setText(tr("menu_view_theme_light"))
        self._act_theme_dark.setText(tr("menu_view_theme_dark"))
        self._menu_language.setTitle(tr("menu_view_language"))
        self._act_lang_en.setText(tr("menu_view_language_en"))
        self._act_lang_es.setText(tr("menu_view_language_es"))
        self._act_toggle_left.setText(tr("menu_view_toggle_left"))
        self._act_toggle_hud.setText(tr("menu_view_toggle_right"))

        self._act_about.setText(tr("menu_help_about"))

        self._left_title.setText(tr("panel_left_title"))
        self._center_title.setText(tr("panel_center_title"))
        self._hud_title.setText(tr("panel_right_title"))
        self._tabs.setTabText(0, tr("tab_welcome_title"))
        self._tabs.setTabText(1, tr("tab_tree_title"))
        self._tabs.setTabText(2, tr("tab_oos_oot_title"))
        self._tabs.setTabText(3, tr("tab_reports_title"))

        self._refresh_session_indicator()
        self._lbl_mode.setText(f"{tr('status_mode')}: {self._mode_name}")
        self._lbl_theme.setText(
            f"{tr('status_theme')}: {tr(f'menu_view_theme_{self._theme_name}')}"
        )
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

        # --- Model (train opens the wizard; OOS/OOT land in Phase 2.3) ---
        self._menu_model = QMenu(self)
        self._menu_model.setObjectName("menu_model")
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
        self._menu_model.addAction(self._act_train)
        self._menu_model.addAction(self._act_evaluate_oos)
        self._menu_model.addAction(self._act_load_oot)
        bar.addMenu(self._menu_model)

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

    def _build_central(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("centralSplitter")

        self._left_panel, self._left_title = self._make_panel("leftPanel")
        self._hud_panel, self._hud_title = self._make_panel("hudPanel")
        # Properties body (Phase 2.2): node details / model summary
        self._hud_body = QLabel()
        self._hud_body.setObjectName("hudBody")
        self._hud_body.setWordWrap(True)
        self._hud_body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._hud_panel.layout().insertWidget(1, self._hud_body)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("centralTabs")
        welcome = QWidget()
        welcome_layout = QVBoxLayout(welcome)
        self._center_title = QLabel()
        self._center_title.setObjectName("panelTitle")
        self._center_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addStretch(1)
        welcome_layout.addWidget(self._center_title)
        welcome_layout.addStretch(1)
        self._tabs.addTab(welcome, "")

        # Phase 2.2: interactive tree viewer tab (empty until TRAINED)
        self._tree_panel = TreePanel()
        self._tree_panel.setObjectName("treePanel")
        self._tabs.addTab(self._tree_panel, "")
        self._tree_panel.node_selected.connect(self._on_tree_node_selected)
        self._tree_panel.selection_cleared.connect(self._hud_reset)

        # Phase 2.3: OOS/OOT metrics panel
        self._metrics_panel = MetricsPanel()
        self._metrics_panel.setObjectName("metricsPanel")
        self._tabs.addTab(self._metrics_panel, "")

        self._reports_panel = ReportsPanel()
        self._reports_panel.setObjectName("reportsPanel")
        self._tabs.addTab(self._reports_panel, "")

        splitter.addWidget(self._left_panel)
        splitter.addWidget(self._tabs)
        splitter.addWidget(self._hud_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([240, 760, 280])
        self.setCentralWidget(splitter)

        self._act_toggle_left.toggled.connect(self._left_panel.setVisible)
        self._act_toggle_hud.toggled.connect(self._hud_panel.setVisible)
        return splitter

    def _make_panel(self, name: str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setObjectName(name)
        layout = QVBoxLayout(frame)
        title = QLabel()
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addStretch(1)
        return frame, title

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
        self._theme_name = name
        self._lbl_theme.setText(
            f"{tr('status_theme')}: {tr(f'menu_view_theme_{name}')}"
        )
        # QGraphicsItems ignore the app QSS: recolor the scene explicitly
        self._tree_panel.set_theme(name)
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
        columns, types = self._session.describe_dataset()
        self._dataset_info = (columns, types)
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
            self._metrics_panel.set_report(None)
            self._hud_reset()
        columns, types = self._dataset_info
        wiz = ModelWizard(columns, types, parent=self)
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
            self._hud_reset()
            return
        st = self._session.state
        self._mode_name = (
            "Banking" if cfg["governance_mode"] == "BANKING" else "Research"
        )
        self._refresh_session_indicator()
        self._lbl_mode.setText(f"{tr('status_mode')}: {self._mode_name}")
        tree = st.tree
        if tree is not None:
            self._tree_panel.set_model(tree, cfg["governance_mode"])
            self._tabs.setCurrentWidget(self._tree_panel)
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

    def _train_pipeline(self, cfg: dict) -> None:
        self._session.fix_spec(cfg["target"], predictors=cfg["predictors"])
        self._session.partition(cfg["train_frac"], cfg["seed"])
        self._session.train(
            cfg["engine"],
            max_depth=cfg["max_depth"],
            min_child_size=cfg["min_child_size"],
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

    # ------------------------------------------------------------------
    # Slots (Phase 2.2: tree viewer -> properties panel)
    # ------------------------------------------------------------------

    def _on_tree_node_selected(self, node_id: int) -> None:
        """Show the selected node card (read-only, from the frozen tree)."""
        model = (
            self._session.state.tree if self._session is not None else None
        )
        if model is None or not (0 <= node_id < len(model.nodes)):
            return
        node = model.nodes[node_id]
        self._hud_body.setText("\n".join(node_detail_lines(node)))
        self.statusBar().showMessage(f"{tr('tree_prop_node')} #{node_id}", 5000)
        if self._logger is not None:
            self._logger.debug("[gui] node selected: %d", node_id)

    def _hud_reset(self) -> None:
        """Properties panel default: node detail > model summary > empty."""
        model = (
            self._session.state.tree if self._session is not None else None
        )
        sel = self._tree_panel.selected_node_id()
        if model is not None and (
            sel is not None and 0 <= sel < len(model.nodes)
        ):
            self._hud_body.setText(
                "\n".join(node_detail_lines(model.nodes[sel]))
            )
        elif model is not None:
            self._hud_body.setText(
                "\n".join(model_summary_lines(model, self._mode_name))
            )
        else:
            self._hud_body.setText(tr("tree_prop_empty"))

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
        self._tabs.setCurrentWidget(self._metrics_panel)
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
        self._tabs.setCurrentWidget(self._metrics_panel)
        self._refresh_session_indicator()
        if self._logger is not None:
            self._logger.info("[gui] OOT loaded and evaluated: %s", path)

    def _load_oot_pipeline(self, path: str) -> None:
        self._session.load_oot(path)
        self._session.evaluate_oot()

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

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        # Nothing to release manually (Qt parentage owns the widgets and
        # log_config owns the log handlers); just leave an audit trail.
        if self._logger is not None:
            self._logger.info("GUI closed cleanly")
        super().closeEvent(event)
