"""TreeGov GUI entry point (Phase 2.0 - application skeleton).

Normal launch:
    .venv\\Scripts\\python treegov_gui.py

Headless smoke run (CI): set QT_QPA_PLATFORM=offscreen and
TREEGOV_GUI_AUTOQUIT_MS=<milliseconds> so the event loop quits alone.
"""

import sys

if __name__ == "__main__":
    from frontend_v3.app import run

    sys.exit(run())
