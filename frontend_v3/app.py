"""Application bootstrap for the TreeGov GUI (Phase 2.0).

run() sequence: transactional log (authorized channel) -> custom
excepthook -> QApplication (org/app names so QSettings is deterministic)
-> default theme -> MainWindow -> event loop.

CI smoke: set QT_QPA_PLATFORM=offscreen and TREEGOV_GUI_AUTOQUIT_MS=<ms>
so the event loop quits by itself and the process exits cleanly.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Sequence

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from backend_v3.log_config import get_logger, setup_logging
from frontend_v3.main_window import MainWindow
from frontend_v3.theme import apply_theme

APP_NAME: str = "TreeGov — Risk Segmentation Workbench"
_ORG_NAME: str = "TreeGov"
_APP_NAME: str = "TreeGovGUI"
_AUTOQUIT_ENV: str = "TREEGOV_GUI_AUTOQUIT_MS"


def create_app(argv: Sequence[str] | None = None) -> QApplication:
    """Build the QApplication and fix org/app names for QSettings."""
    app = QApplication(list(argv) if argv is not None else sys.argv)
    QCoreApplication.setOrganizationName(_ORG_NAME)
    QCoreApplication.setApplicationName(_APP_NAME)
    return app


def _install_excepthook(logger: logging.Logger) -> None:
    """Route uncaught exceptions to the 'treegov.gui' audit log.

    A critical dialog is shown only on a real display: under offscreen
    (CI) a modal QMessageBox would hang the process forever.
    """
    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_tb) -> None:  # type: ignore[no-untyped-def]
        logger.critical(
            "Uncaught GUI exception", exc_info=(exc_type, exc_value, exc_tb)
        )
        app = QApplication.instance()
        if app is not None and app.platformName() != "offscreen":
            QMessageBox.critical(None, APP_NAME, f"Unexpected error:\n{exc_value}")
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


def run(argv: Sequence[str] | None = None) -> int:
    """Start the GUI; return the event-loop exit code."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join("logs", f"gui_{stamp}.log")
    setup_logging(log_path)
    logger = get_logger("gui")
    logger.info("GUI startup (pid=%d)", os.getpid())

    _install_excepthook(logger)
    app = create_app(argv)
    apply_theme("light", app)  # fixed default in 2.0; persistence deferred

    window = MainWindow(logger=logger)
    window.show()

    autoquit = os.environ.get(_AUTOQUIT_ENV)
    if autoquit:
        QTimer.singleShot(int(autoquit), app.quit)

    code = app.exec()
    logger.info("GUI event loop finished (exit=%d)", code)
    return code
