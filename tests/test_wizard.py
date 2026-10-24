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


def _make_wizard_with_provider(counts: dict):
    _get_app()
    return ModelWizard(
        _COLS, _TYPES,
        target_provider=lambda _col: counts,
    )


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


def _csv_imbalanced(tmp: Path) -> Path:
    """120 filas; default con desbalance 20/100 para probar el
    warning de clase mayoritaria."""
    n = 120
    edad = np.tile(np.arange(20, 60), 3)
    seg = np.tile(["a", "b", "c"], 40)
    # 100 unos, 20 ceros.
    y = np.array([1] * 100 + [0] * 20)
    df = pd.DataFrame({"edad": edad, "seg": seg, "default": y})
    p = tmp / "mini_imbalanced.csv"
    df.to_csv(p, index=False)
    return p


def _select_first_predictor(wiz: ModelWizard) -> str:
    """Mueve el primer predictor disponible a 'selected'; devuelve su nombre."""
    page = wiz.page_predictors
    assert page._lst_available.count() >= 1
    page._lst_available.setCurrentRow(0)
    page._move(False, False)
    return page.selected_predictors()[0]


def _select_target(wiz: ModelWizard, col: str) -> None:
    """Elige la columna col como target (Phase 3.7.e: H2 fijo)."""
    idx = wiz.page_predictors._combo_target.findData(col)
    if idx <= 0:
        raise AssertionError(f"target {col} no encontrado en el combo")
    wiz.page_predictors._combo_target.setCurrentIndex(idx)


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
    # Step 2 sin target ni predictores: Next deshabilitado (gate real de la UI)
    app = _get_app()
    app.processEvents()
    assert btn_next.isEnabled() is False
    _select_target(wiz, "default")
    app.processEvents()
    assert btn_next.isEnabled() is False            # aun sin predictores
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
    assert page.isComplete() is False              # sin target + 0 predictores
    # sin target elegido (H2), TODAS las columnas estan disponibles
    cols_avail = [
        page._lst_available.item(i).data(_USER)
        for i in range(page._lst_available.count())
    ]
    assert set(cols_avail) == {"default", "edad", "seg", "ingreso"}

    _select_target(wiz, "default")
    # el target elegido ("default") NO esta disponible como predictor
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
# 4: contrato CHAID post-3.10.b (H14): [CONT] habilitados para TODO motor
#    (el backend hace binning automatico; la regla espejo se elimino en 3.11)
# ---------------------------------------------------------------------------


def test_wizard_chaid_allows_continuous():
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
    # con CHAID, los [CONT] tambien estan habilitados (binning automatico)
    assert all(flags), "todo predictor debe estar habilitado con CHAID"
    # paridad con C&RT: mismo comportamiento
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
    _select_target(wiz, "default")
    _select_first_predictor(wiz)                   # "edad" (1er disponible)
    captured: list[dict] = []
    wiz.finished_with_config.connect(captured.append)
    wiz.accept()
    assert len(captured) == 1
    cfg = captured[0]
    assert set(cfg) == {
        "engine", "target", "predictors", "target_class", "class_labels",
        "train_frac", "seed", "max_depth", "min_child_size",
        "min_child_weight",
        "governance_mode", "apply_jeffreys", "pd_floor", "weight_col",
        "population_col", "population_ok_values",
    }
    assert cfg["engine"] == "CRT"
    assert cfg["target"] == "default"
    assert cfg["predictors"] == ["edad"]
    # sin target_provider: contrato presente pero vacio
    assert cfg["target_class"] is None
    assert cfg["class_labels"] == {}
    assert cfg["train_frac"] == 0.7 and cfg["seed"] == 42
    assert cfg["max_depth"] == 4 and cfg["min_child_size"] == 50
    assert cfg["governance_mode"] == "BANKING"
    assert cfg["apply_jeffreys"] is True and cfg["pd_floor"] == 0.0005
    assert cfg["weight_col"] is None  # default del wizard: sin pesos
    assert cfg["population_col"] is None
    assert cfg["population_ok_values"] == ()


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
            "target_class": 1,
            "class_labels": {0: "Non-event", 1: "Event"},
            "weight_col": None,
            "population_col": None,
            "population_ok_values": (),
            "train_frac": 0.7, "seed": 42,
            "max_depth": 4, "min_child_size": 5,
            "min_child_weight": None,
            "governance_mode": "BANKING",
            "apply_jeffreys": True, "pd_floor": 0.0005,
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


def test_wizard_default_class_selected():
    """Fase 3.1.e.4: tras poblar la tabla, SIEMPRE hay una clase
    de interés seleccionada por default (última fila del orden
    ascendente)."""
    wiz = _make_wizard_with_provider({0: 60, 1: 60})
    page = wiz.page_predictors
    # Forzar el poblado de la tabla llamando al refresh.
    page._refresh_class_table()
    assert page._tbl_classes.rowCount() == 2
    tc = page.target_class()
    assert tc is not None
    # El default es la última fila en orden ascendente -> 1.
    assert tc == 1
    labels = page.class_labels()
    assert labels == {0: "0", 1: "1"}
    wiz.close()
    wiz.deleteLater()


def test_wizard_shows_counts_per_class():
    """Fase 3.1.e.4: la tabla muestra el count por clase."""
    wiz = _make_wizard_with_provider({0: 30, 1: 90})
    page = wiz.page_predictors
    page._refresh_class_table()
    assert page._tbl_classes.rowCount() == 2
    # Columna 2 tiene los counts, en orden ascendente por valor.
    item0 = page._tbl_classes.item(0, 2)
    item1 = page._tbl_classes.item(1, 2)
    assert item0 is not None and item0.text() == "30"
    assert item1 is not None and item1.text() == "90"
    wiz.close()
    wiz.deleteLater()


def test_wizard_minority_warning_shown():
    """Fase 3.1.e.4: warning amber si la clase elegida es la
    mayoritaria (sin empate)."""
    wiz = _make_wizard_with_provider({0: 20, 1: 100})
    page = wiz.page_predictors
    page._refresh_class_table()
    # Default: última fila -> valor 1 (mayoritaria, count 100).
    # El radio de la fila 1 se marcó por default y disparó
    # _on_interest_toggled -> warning visible.
    assert page.target_class() == 1
    # NOTA: isVisible() es False mientras el wizard toplevel no se
    # muestre (offscreen); el flag que controla el codigo es el de
    # "hidden", asi que se verifica con isHidden().
    assert page._lbl_warning.isHidden() is False
    # Cambiar a la clase minoritaria (fila 0) debe ocultar el
    # warning.
    page._class_rows[0]["radio"].setChecked(True)
    assert page._lbl_warning.isHidden() is True
    wiz.close()
    wiz.deleteLater()


# ---------------------------------------------------------------------------
# 3.2.h - Ponderación por muestra
# ---------------------------------------------------------------------------

_COLS_W = _COLS + ("peso",)
_TYPES_W = {**_TYPES, "peso": "CONTINUOUS"}


def _available_cols(page) -> list:
    return [
        page._lst_available.item(i).data(_USER)
        for i in range(page._lst_available.count())
    ]


def test_wizard_weight_combo_default_is_none():
    wiz = ModelWizard(_COLS_W, _TYPES_W)
    page = wiz.page_predictors
    assert page.weight_col() is None
    # La primera opción del combo es la de "sin pesos" (userData=None)
    assert page._combo_weight.itemData(0) is None
    assert page._combo_weight.currentIndex() == 0
    # El resto de opciones son las columnas del dataset
    assert page._combo_weight.count() == 1 + len(_COLS_W)
    wiz.close()
    wiz.deleteLater()


def test_wizard_weight_mirror_rule():
    wiz = ModelWizard(_COLS_W, _TYPES_W)
    page = wiz.page_predictors
    assert "ingreso" in _available_cols(page)
    idx = page._combo_weight.findData("ingreso")
    assert idx > 0
    page._combo_weight.setCurrentIndex(idx)
    assert page.weight_col() == "ingreso"
    # Regla espejo: la columna de pesos sale de predictores disponibles
    assert "ingreso" not in _available_cols(page)
    # Volver a "(sin pesos)": la columna reaparece
    page._combo_weight.setCurrentIndex(0)
    assert page.weight_col() is None
    assert "ingreso" in _available_cols(page)
    wiz.close()
    wiz.deleteLater()


def test_wizard_weight_in_current_config():
    wiz = ModelWizard(_COLS_W, _TYPES_W)
    page = wiz.page_predictors
    cfg0 = wiz.current_config()
    assert "weight_col" in cfg0
    assert cfg0["weight_col"] is None
    idx = page._combo_weight.findData("peso")
    page._combo_weight.setCurrentIndex(idx)
    cfg1 = wiz.current_config()
    assert cfg1["weight_col"] == "peso"
    wiz.close()
    wiz.deleteLater()


def test_wizard_weight_warning_when_validator_returns_false():
    wiz = ModelWizard(
        _COLS_W, _TYPES_W,
        weight_validator=lambda col: col != "peso",
    )
    page = wiz.page_predictors
    assert page._lbl_weight_warning.isHidden() is True
    idx = page._combo_weight.findData("peso")
    page._combo_weight.setCurrentIndex(idx)
    # El validador rechaza "peso": aviso ámbar visible (isHidden == False)
    assert page._lbl_weight_warning.isHidden() is False
    # Columna válida: el aviso se oculta
    idx_ok = page._combo_weight.findData("ingreso")
    page._combo_weight.setCurrentIndex(idx_ok)
    assert page._lbl_weight_warning.isHidden() is True
    wiz.close()
    wiz.deleteLater()


# ---------------------------------------------------------------------------
# ejecucion directa sin pytest
# ---------------------------------------------------------------------------

def test_wizard_population_combo_default_is_none():
    """Fase 3.3.d: el combo arranca en "sin filtro de población"."""
    wiz = _make_wizard()
    page = wiz.page_predictors
    assert page.population_col() is None
    assert page.population_ok_values() == ()
    assert page._combo_population.itemData(0) is None
    assert page._combo_population.currentIndex() == 0
    wiz.close()
    wiz.deleteLater()


def test_wizard_population_mirror_rule():
    """Fase 3.3.d: la columna de población sale de predictores disponibles."""
    wiz = _make_wizard()
    page = wiz.page_predictors
    assert "ingreso" in _available_cols(page)
    idx = page._combo_population.findData("ingreso")
    assert idx > 0
    page._combo_population.setCurrentIndex(idx)
    assert page.population_col() == "ingreso"
    assert "ingreso" not in _available_cols(page)
    # Volver a "(sin filtro)": reaparece
    page._combo_population.setCurrentIndex(0)
    assert page.population_col() is None
    assert "ingreso" in _available_cols(page)
    wiz.close()
    wiz.deleteLater()


def test_wizard_population_ok_table_populated_from_provider():
    """Fase 3.3.d: con population_provider, la tabla se puebla con valores
    y conteos. Todos los valores marcados OK por defecto."""
    wiz = ModelWizard(
        _COLS, _TYPES,
        population_provider=lambda _col: {
            "exists": True, "n": 120,
            "values": (("OK", 70), ("INDET", 30), ("INSUF", 20)),
        },
    )
    page = wiz.page_predictors
    idx = page._combo_population.findData("ingreso")
    page._combo_population.setCurrentIndex(idx)
    assert page._tbl_population.rowCount() == 3
    assert page._tbl_population.item(0, 0).text() == "OK"
    assert page._tbl_population.item(0, 1).text() == "70"
    # Todos marcados OK por defecto
    assert page.population_ok_values() == ("OK", "INDET", "INSUF")
    # Desmarcar los dos últimos
    page._population_rows[1]["checkbox"].setChecked(False)
    page._population_rows[2]["checkbox"].setChecked(False)
    assert page.population_ok_values() == ("OK",)
    wiz.close()
    wiz.deleteLater()


def test_wizard_population_requires_at_least_one_ok():
    """Fase 3.3.d: si el analista desmarca todo, population_ok_values()
    devuelve tupla vacía (el backend lo rechazará con error claro)."""
    wiz = ModelWizard(
        _COLS, _TYPES,
        population_provider=lambda _col: {
            "exists": True, "n": 10,
            "values": (("OK", 10),),
        },
    )
    page = wiz.page_predictors
    idx = page._combo_population.findData("ingreso")
    page._combo_population.setCurrentIndex(idx)
    page._population_rows[0]["checkbox"].setChecked(False)
    assert page.population_ok_values() == ()
    wiz.close()
    wiz.deleteLater()


def test_wizard_population_in_current_config():
    """Fase 3.3.d: current_config incluye population_col y
    population_ok_values."""
    wiz = ModelWizard(
        _COLS, _TYPES,
        population_provider=lambda _col: {
            "exists": True, "n": 10,
            "values": (("OK", 8), ("INDET", 2)),
        },
    )
    cfg0 = wiz.current_config()
    assert cfg0["population_col"] is None
    assert cfg0["population_ok_values"] == ()
    page = wiz.page_predictors
    idx = page._combo_population.findData("ingreso")
    page._combo_population.setCurrentIndex(idx)
    cfg1 = wiz.current_config()
    assert cfg1["population_col"] == "ingreso"
    assert cfg1["population_ok_values"] == ("OK", "INDET")
    wiz.close()
    wiz.deleteLater()


def test_wizard_default_pd_floor_spinbox():
    """Fase 3.8: el spin box del Step 4 arranca en 0.0005.

    Verifica (a) el valor inicial del widget (lo que el analista ve
    al abrir el wizard) y (b) que _sync_governance_controls restaura
    0.0005 al volver de RESEARCH a BANKING. Nota: math no se importa
    en este archivo, se usa la comparacion por diferencia absoluta.
    """
    wiz = _make_wizard()
    page = wiz.page_governance
    # (a) Valor inicial: 0.0005 (default rc2)
    assert abs(page._spin_floor.value() - 0.0005) < 1e-12
    # Cambiar a RESEARCH deshabilita los controles
    page._rb_research.setChecked(True)
    assert page._spin_floor.isEnabled() is False
    # Manipular el valor mientras esta deshabilitado (setValue funciona
    # sobre widgets deshabilitados; solo la interaccion de usuario esta
    # bloqueada), y volver a BANKING: debe restaurar 0.0005.
    page._spin_floor.setValue(0.0123)
    page._rb_banking.setChecked(True)
    assert abs(page._spin_floor.value() - 0.0005) < 1e-12
    wiz.close()
    wiz.deleteLater()


def test_wizard_size_and_title_banner():
    """El wizard abre con tamaño adecuado (mínimo 800x600, inicial
    950x700) y la EnginePage muestra el título de la app como banner
    (objectName wizardTitle -> regla QSS con $ACCENT, legible en oscuro).
    La etiqueta se construye UNA vez y solo se retraduce: un cambio de
    idioma no la duplica."""
    wiz = _make_wizard()
    assert wiz.minimumWidth() == 800
    assert wiz.minimumHeight() == 600
    assert wiz.size().width() >= 950 and wiz.size().height() >= 700
    lbl = wiz.page_engine._lbl_wizard_title
    assert lbl.objectName() == "wizardTitle"
    assert lbl.text() == tr("wizard_title")
    # primer widget del layout de EnginePage
    assert wiz.page_engine.layout().itemAt(0).widget() is lbl
    # retraducción en caliente: texto ES, sin duplicar el widget
    prev = "en"
    try:
        set_language("es")
        language_bus.language_changed.emit("es")
        assert lbl.text() == tr("wizard_title", "es")
        n_titles = sum(
            1 for i in range(wiz.page_engine.layout().count())
            if wiz.page_engine.layout().itemAt(i).widget() is not None
            and wiz.page_engine.layout().itemAt(i).widget().objectName()
            == "wizardTitle"
        )
        assert n_titles == 1
    finally:
        set_language(prev)
        language_bus.language_changed.emit(prev)
    assert lbl.text() == tr("wizard_title", "en")
    wiz.close()
    wiz.deleteLater()


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
