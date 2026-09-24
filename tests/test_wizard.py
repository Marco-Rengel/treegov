"""Tests del wizard transaccional de Fase 2.1 (frontend_v3/wizard.py +
orquestacion en frontend_v3/main_window.py). Dual: pytest o python directo.

    .venv\\Scripts\\python -m pytest tests/test_wizard.py -v
    .venv\\Scripts\\python tests\\test_wizard.py

Headless: QT_QPA_PLATFORM=offscreen por defecto (setdefault). Los tests
de integracion (7-8) usan un CSV sintetico en tempfile; NADA se escribe
en data/ (zona protegida).
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402  (tests/ SI puede importar: fuera del frontend)
import pandas as pd  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QRadioButton, QWizard  # noqa: E402

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import language_bus, set_language, tr  # noqa: E402
from frontend_v3.main_window import MainWindow  # noqa: E402
from frontend_v3.wizard import ModelWizard  # noqa: E402

_COLS = ("default", "edad", "seg", "ingreso")
_TYPES = {
    "default": "ORDINAL",
    "edad": "CONTINUOUS",
    "seg": "NOMINAL",
    "ingreso": "CONTINUOUS",
}
_USER = Qt.ItemDataRole.UserRole
_ENABLED = Qt.ItemFlag.ItemIsEnabled


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _make_wizard() -> ModelWizard:
    _get_app()
    return ModelWizard(_COLS, _TYPES)


def _csv_tiny(tmp: Path) -> Path:
    """120 filas; y = 1_{edad >= 40} (mismo fixture que test_session_state)."""
    n = 120
    edad = np.tile(np.arange(20, 60), 3)
    seg = np.tile(["a", "b", "c"], 40)
    df = pd.DataFrame({"edad": edad, "seg": seg,
                       "default": (edad >= 40).astype(int)})
    p = tmp / "mini_gui.csv"
    df.to_csv(p, index=False)
    return p


def _select_first_predictor(wiz: ModelWizard) -> str:
    """Mueve el primer predictor disponible a 'selected'; devuelve su nombre."""
    page = wiz.page_predictors
    assert page._lst_available.count() >= 1
    page._lst_available.setCurrentRow(0)
    page._move(False, False)
    return page.selected_predictors()[0]


# ---------------------------------------------------------------------------
# 1-3: construccion, navegacion, validacion de Step 2
# ---------------------------------------------------------------------------


def test_wizard_constructs():
    wiz = _make_wizard()
    assert wiz.windowTitle()
    assert wiz.selected_engine() == "CRT"          # default propuesto
    assert [wiz.pageIds()[i] for i in range(4)] == [0, 1, 2, 3]
    assert wiz.isModal() is False                  # requisito: retraduccion en caliente
    wiz.close()
    wiz.deleteLater()


def test_wizard_navigation():
    wiz = _make_wizard()
    wiz.show()
    btn_next = wiz.button(QWizard.WizardButton.NextButton)
    assert wiz.currentId() == 0
    wiz.next()
    assert wiz.currentId() == 1
    # Step 2 sin predictores: el boton Next (gate real de la UI) deshabilitado
    app = _get_app()
    app.processEvents()
    assert btn_next.isEnabled() is False
    _select_first_predictor(wiz)
    app.processEvents()
    assert btn_next.isEnabled() is True
    wiz.next()
    assert wiz.currentId() == 2
    wiz.next()
    assert wiz.currentId() == 3                    # governance (resumen)
    summary = wiz.page_governance._lbl_summary.text()
    assert "CRT" in summary and "default" in summary
    wiz.back()
    assert wiz.currentId() == 2
    wiz.close()
    wiz.deleteLater()


def test_wizard_predictors_validation():
    wiz = _make_wizard()
    page = wiz.page_predictors
    assert page.isComplete() is False              # 0 predictores
    # el target inicial ("default") NO esta disponible como predictor
    cols_avail = [
        page._lst_available.item(i).data(_USER)
        for i in range(page._lst_available.count())
    ]
    assert "default" not in cols_avail
    assert set(cols_avail) == {"edad", "seg", "ingreso"}

    _select_first_predictor(wiz)                   # "edad" -> selected
    assert page.isComplete() is True
    assert page.selected_predictors() == ["edad"]

    # target -> "seg": los predictores seleccionados ajenos se preservan
    idx_seg = page._combo_target.findData("seg")
    page._combo_target.setCurrentIndex(idx_seg)
    assert page.target() == "seg"
    assert page.selected_predictors() == ["edad"]
    avail_cols = [
        page._lst_available.item(i).data(_USER)
        for i in range(page._lst_available.count())
    ]
    assert "seg" not in page.selected_predictors()
    assert "seg" not in avail_cols                 # ahora es el target
    assert "default" in avail_cols                 # el target anterior vuelve

    # si el nuevo target ESTABA seleccionado, sale de selected
    page._combo_target.setCurrentIndex(page._combo_target.findData("edad"))
    assert page.target() == "edad"
    assert "edad" not in page.selected_predictors()
    wiz.close()
    wiz.deleteLater()


# ---------------------------------------------------------------------------
# 4: regla espejo CHAID (<-> contrato chaid_engine: sin CONTINUOUS)
# ---------------------------------------------------------------------------


def test_wizard_chaid_disables_continuous():
    wiz = _make_wizard()
    wiz.show()
    page0 = wiz.page_engine
    radio_chaid = next(
        rb for rb in page0.findChildren(QRadioButton) if rb.text() == "CHAID"
    )
    radio_chaid.setChecked(True)
    wiz.next()                                     # entra a Step 2
    page = wiz.page_predictors
    flags = [
        bool(page._lst_available.item(i).flags() & _ENABLED)
        for i in range(page._lst_available.count())
    ]
    cols = [
        page._lst_available.item(i).data(_USER)
        for i in range(page._lst_available.count())
    ]
    for col, enabled in zip(cols, flags):
        if _TYPES[col] == "CONTINUOUS":
            assert not enabled, f"{col} deberia estar deshabilitado con CHAID"
        else:
            assert enabled
    # volver a C&RT: los [CONT] se rehabilitan
    radio_crt = next(
        rb for rb in page0.findChildren(QRadioButton) if rb.text() == "C&RT"
    )
    wiz.back()
    radio_crt.setChecked(True)
    wiz.next()
    flags2 = [
        bool(page._lst_available.item(i).flags() & _ENABLED)
        for i in range(page._lst_available.count())
    ]
    assert all(flags2)
    wiz.close()
    wiz.deleteLater()


# ---------------------------------------------------------------------------
# 5: Finish emite el dict de configuracion completo
# ---------------------------------------------------------------------------


def test_wizard_finish_emits_config():
    wiz = _make_wizard()
    wiz.show()
    _select_first_predictor(wiz)                   # "edad" (1er disponible)
    captured: list[dict] = []
    wiz.finished_with_config.connect(captured.append)
    wiz.accept()
    assert len(captured) == 1
    cfg = captured[0]
    assert set(cfg) == {
        "engine", "target", "predictors", "train_frac", "seed",
        "max_depth", "min_child_size", "governance_mode",
        "apply_jeffreys", "pd_floor",
    }
    assert cfg["engine"] == "CRT"
    assert cfg["target"] == "default"
    assert cfg["predictors"] == ["edad"]
    assert cfg["train_frac"] == 0.7 and cfg["seed"] == 42
    assert cfg["max_depth"] == 4 and cfg["min_child_size"] == 50
    assert cfg["governance_mode"] == "BANKING"
    assert cfg["apply_jeffreys"] is True and cfg["pd_floor"] == 0.0003


def test_wizard_research_mode_disables_governance():
    wiz = _make_wizard()
    wiz.show()
    _select_first_predictor(wiz)
    wiz.next()
    wiz.next()                                     # Step 4
    page = wiz.page_governance
    page._rb_research.setChecked(True)
    assert page._chk_jeffreys.isEnabled() is False
    assert page._spin_floor.isEnabled() is False
    captured: list[dict] = []
    wiz.finished_with_config.connect(captured.append)
    wiz.accept()
    cfg = captured[0]
    assert cfg["governance_mode"] == "RESEARCH"
    assert cfg["apply_jeffreys"] is False
    assert cfg["pd_floor"] is None


# ---------------------------------------------------------------------------
# 6: retraduccion en caliente + persistencia del combo (micro-ajustes 3)
# ---------------------------------------------------------------------------


def test_wizard_retranslate_via_bus():
    wiz = _make_wizard()
    wiz.show()
    page = wiz.page_predictors
    idx_seg = page._combo_target.findData("seg")
    page._combo_target.setCurrentIndex(idx_seg)    # target = "seg"

    prev = "en"
    try:
        set_language("es")
        language_bus.language_changed.emit("es")
        assert wiz.windowTitle() == tr("wizard_title", "es")
        assert wiz.button(QWizard.WizardButton.NextButton).text() == "Siguiente"
        assert wiz.page_engine.title() == tr("step1_title", "es")
        # el combo target sobrevive intacto al cambio de idioma
        assert page._combo_target.currentData() == "seg"
        assert page._combo_target.currentText() == "seg"
        # el resumen del Step 4 tambien se retraduce (Motor / Bancario)
        summary_es = wiz.page_governance._lbl_summary.text()
        assert "Motor:" in summary_es
        assert "Bancario" in summary_es
    finally:
        set_language(prev)
        language_bus.language_changed.emit(prev)
    assert wiz.windowTitle() == tr("wizard_title", "en")
    assert "Engine:" in wiz.page_governance._lbl_summary.text()
    wiz.close()
    wiz.deleteLater()


# ---------------------------------------------------------------------------
# 7-8: integracion MainWindow <-> Session (backend real, CSV tiny)
# ---------------------------------------------------------------------------


def test_mainwindow_dataset_flow_enables_wizard():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_tiny(Path(td))
        _get_app()
        w = MainWindow()
        assert w._act_open.isEnabled() is True
        assert w._act_new_wizard.isEnabled() is False  # gated hasta DATA_LOADED
        assert w._act_train.isEnabled() is False
        assert w._load_dataset_path(str(csv_path)) is True
        assert w._act_new_wizard.isEnabled() is True
        assert w._act_train.isEnabled() is True
        cols, types = w._dataset_info
        assert cols == ("edad", "seg", "default")
        assert types["edad"] == "CONTINUOUS" and types["seg"] == "NOMINAL"
        assert w._lbl_session.text().endswith("DATA_LOADED")
        w.close()
        w.deleteLater()


def test_mainwindow_wizard_config_trains():
    with tempfile.TemporaryDirectory() as td:
        csv_path = _csv_tiny(Path(td))
        _get_app()
        w = MainWindow()
        assert w._load_dataset_path(str(csv_path)) is True
        cfg = {
            "engine": "CRT", "target": "default",
            "predictors": ["edad", "seg"],
            "train_frac": 0.7, "seed": 42,
            "max_depth": 4, "min_child_size": 5,
            "governance_mode": "BANKING",
            "apply_jeffreys": True, "pd_floor": 0.0003,
        }
        w._on_wizard_finished(cfg)
        st = w._session.state
        assert st.state.name == "TRAINED"
        assert st.tree is not None
        assert st.tree.method == "CRT"
        assert w._lbl_session.text().endswith("TRAINED")
        assert w._lbl_mode.text().endswith("Banking")
        fp_banking = st.tree.params_fingerprint

        # segunda corrida en modo RESEARCH sobre el mismo dataset (sin re-IO)
        w._session.reset_to_data_loaded()
        cfg2 = dict(cfg, governance_mode="RESEARCH",
                    apply_jeffreys=False, pd_floor=None)
        w._on_wizard_finished(cfg2)
        st2 = w._session.state
        assert st2.tree is not None
        assert st2.tree.params_fingerprint != fp_banking
        hojas = [nd for nd in st2.tree.nodes if nd.is_leaf]
        assert all(nd.pd_final == nd.pd_jeffreys for nd in hojas)  # sin floor
        w.close()
        w.deleteLater()


# ---------------------------------------------------------------------------
# ejecucion directa sin pytest
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        obj
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
