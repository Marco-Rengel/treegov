import os
import sys
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from frontend_v3.app import create_app
from frontend_v3.i18n import set_language
from frontend_v3.main_window import MainWindow

def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app

def _make_csv_non_banking(path: Path, n: int = 100, seed: int = 42) -> Path:
    """Dataset sintético no-bancario: predecir si un paciente está enfermo."""
    rng = np.random.default_rng(seed)
    edad = rng.integers(20, 80, size=n)
    presion = rng.integers(90, 180, size=n)
    # Señal real: enfermo si edad > 50 o presion > 140
    enfermo = ((edad > 50) | (presion > 140)).astype(int)
    df = pd.DataFrame({"edad": edad, "presion": presion, "enfermo": enfermo})
    df.to_csv(path, index=False)
    return path

def test_e2e_non_banking_research_mode():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv_non_banking(Path(td) / "pacientes.csv")
        _get_app()
        w = MainWindow()
        set_language("en")  # Forzar inglés para aserciones predecibles
        w.retranslate_ui()
        assert w._load_dataset_path(str(csv))

        # Configuración explícita en modo RESEARCH
        cfg = {
            "engine": "CRT", "target": "enfermo",
            "predictors": ["edad", "presion"],
            "target_class": 1,
            "class_labels": {0: "Sano", 1: "Enfermo"},
            "weight_col": None, "population_col": None, "population_ok_values": (),
            "train_frac": 0.7, "seed": 42,
            "max_depth": 3, "min_child_size": 10, "min_child_weight": None,
            "governance_mode": "RESEARCH",
            "apply_jeffreys": False, "pd_floor": None,
        }

        w._on_wizard_finished(cfg)
        # state = SessionState (dataclass); el FlowState vive en .state
        assert w._session.state.state.name == "TRAINED"

        # Verificar terminología neutra en el panel de reportes
        # La columna de PD debe decir "Probability", no "PD"
        header_pd = w._reports_panel._table.horizontalHeaderItem(1).text()
        assert "Probability" in header_pd
        assert "PD" not in header_pd

        # Verificar terminología neutra en el HTML
        html = w._reports_panel._build_report_html()
        assert "Probability" in html
        assert "Bad rate" not in html

        w.close()
        w.deleteLater()
