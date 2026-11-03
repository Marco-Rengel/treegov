"""TreeGov GUI entry point (Phase 2.0 - application skeleton).

Normal launch:
    .venv\\Scripts\\python treegov_gui.py

Headless smoke run (CI): set QT_QPA_PLATFORM=offscreen and
TREEGOV_GUI_AUTOQUIT_MS=<milliseconds> so the event loop quits alone.
"""

# ORDEN CRITICO: la guardia se instala ANTES de importar frontend_v3/PySide6.
from backend_v3.import_guard import install_import_guard, is_installed

install_import_guard()

import sys

if __name__ == "__main__":
    from frontend_v3.app import run

    sys.exit(run())
