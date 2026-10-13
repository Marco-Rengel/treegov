"""frontend_v3 - Presentation layer (TreeGov, Phase 2).

Clean-room rules (.treegovrules):
  - No analytical logic here: numpy/pandas/scipy imports are forbidden
    (enforced by tests/test_gui_smoke.py::test_frontend_clean_room).
  - Backend communication exclusively via backend_v3.session_state.Session.
  - Log writes only via backend_v3.log_config (authorized channel).
"""

__version__ = "1.0.0a4"
