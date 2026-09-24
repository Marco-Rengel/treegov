"""Main window of the TreeGov GUI (Phase 2.0 - application skeleton).

Clean room: no analytical logic here. The window may hold a reference to
backend_v3.session_state.Session (injected via the constructor), but the
import is TYPE_CHECKING-only; the frontend never computes.

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
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent
from PySide6.QtWidgets import (
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

from frontend_v3 import __version__
from frontend_v3.i18n import (
    SUPPORTED,
    detect_system_language,
    get_language,
    set_language,
    tr,
)
from frontend_v3.theme import apply_theme

if TYPE_CHECKING:  # clean room: typing only, no runtime backend import
    from backend_v3.session_state import Session

_TT_PHASE21 = "Available in Phase 2.1"
_TT_PHASE23 = "Available in Phase 2.3"


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

        self._lbl_session.setText(f"{tr('status_session')}: —")
        self._lbl_theme.setText(
            f"{tr('status_theme')}: {tr(f'menu_view_theme_{self._theme_name}')}"
        )

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
        self._act_new_wizard = self._new_action(
            "act_new_wizard", "Ctrl+N", enabled=False, tooltip=_TT_PHASE21
        )
        self._act_open = self._new_action(
            "act_open", "Ctrl+O", enabled=False, tooltip=_TT_PHASE21
        )
        self._act_exit = self._new_action("act_exit", "Ctrl+Q")
        self._act_exit.triggered.connect(self.close)
        self._menu_file.addAction(self._act_new_wizard)
        self._menu_file.addAction(self._act_open)
        self._menu_file.addSeparator()
        self._menu_file.addAction(self._act_exit)
        bar.addMenu(self._menu_file)

        # --- Model (all placeholder until its phase lands) ---
        self._menu_model = QMenu(self)
        self._menu_model.setObjectName("menu_model")
        self._act_train = self._new_action(
            "act_train", enabled=False, tooltip=_TT_PHASE21
        )
        self._act_evaluate_oos = self._new_action(
            "act_evaluate_oos", enabled=False, tooltip=_TT_PHASE23
        )
        self._act_load_oot = self._new_action(
            "act_load_oot", enabled=False, tooltip=_TT_PHASE23
        )
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
        self._lbl_theme = QLabel()
        self._lbl_theme.setObjectName("statusThemeLabel")
        sb.addPermanentWidget(self._lbl_session)
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
        if self._logger is not None:
            self._logger.info("Theme switched to %s", name)

    def _switch_language(self, lang: str) -> None:
        set_language(lang)
        QSettings().setValue("language", lang)
        self.retranslate_ui()
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
