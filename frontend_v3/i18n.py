"""Centralized bilingual strings for the TreeGov GUI (EN / ES).

Design notes (Phase 2.0, approved):
  - Plain-Python dictionaries (auditable white-box), NOT Qt Linguist
    (.ts / lrelease / .qm). That workflow is overkill for two locales.
  - A module-level singleton holds the active language.
  - Persistence across sessions is the caller's job (QSettings key
    "language"); this module stays free of settings side effects.
  - Fail-fast: unknown key -> KeyError, unsupported language -> ValueError.
    A silent fallback would hide gaps an auditor must see.

tr() performs no formatting; composed strings are assembled by the caller
(f"{tr('status_theme')}: {name}"). Sole exception: about_body carries a
{version} placeholder (the version sits mid-sentence, not composable).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QLocale, Signal

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "window_title": "TreeGov — Risk Segmentation Workbench",
        "menu_file": "File",
        "menu_model": "Model",
        "menu_view": "View",
        "menu_help": "Help",
        "menu_file_new_wizard": "New Model Wizard...",
        "menu_file_open": "Open Dataset...",
        "menu_file_exit": "Exit",
        "menu_model_train": "Train",
        "menu_model_evaluate_oos": "Evaluate OOS",
        "menu_model_load_oot": "Load OOT Cohort...",
        "menu_view_theme": "Theme",
        "menu_view_theme_light": "Light",
        "menu_view_theme_dark": "Dark",
        "menu_view_language": "Language",
        "menu_view_language_en": "English",
        "menu_view_language_es": "Español",
        "menu_view_toggle_left": "Left Panel",
        "menu_view_toggle_right": "Properties Panel",
        "menu_help_about": "About TreeGov",
        "panel_left_title": "Project Explorer",
        "panel_center_title": "Workspace",
        "panel_right_title": "Properties",
        "tab_welcome_title": "Welcome",
        "status_ready": "Ready",
        "status_session": "Session",
        "status_theme": "Theme",
        "status_mode": "Mode",
        "about_title": "About TreeGov",
        "about_body": (
            "Risk segmentation workbench with native MRM/IFRS 9 governance.\n"
            "Version {version} · Apache 2.0 License"
        ),
        # --- Phase 2.1: transactional wizard ---
        "wizard_title": "New Model Wizard",
        "wizard_next": "Next",
        "wizard_back": "Back",
        "wizard_finish": "Finish",
        "wizard_cancel": "Cancel",
        "step1_title": "Step 1 — Engine selection",
        "step1_subtitle": "Choose the splitting algorithm.",
        "step1_desc_chaid": (
            "CHAID — multiway category merging with Bonferroni correction "
            "(Kass, 1980)"
        ),
        "step1_desc_chaid_exhaustive": (
            "Exhaustive CHAID — merging until exhaustion "
            "(Biggs, de Ville & Suen, 1991)"
        ),
        "step1_desc_crt": (
            "C&RT — binary Gini/variance partitioning with surrogate splits "
            "(Breiman et al., 1984)"
        ),
        "step1_desc_quest": (
            "QUEST — unbiased variable selection with univariate QDA split "
            "(Loh & Shih, 1997)"
        ),
        "step2_title": "Step 2 — Predictors and target",
        "step2_subtitle": "Pick the binary target and at least one predictor.",
        "step2_target_label": "Target (binary 0/1):",
        "step2_available": "Available predictors",
        "step2_selected": "Selected predictors",
        "step2_hint_min_one": "Select at least one predictor to continue.",
        "step2_chaid_cont_note": (
            "Note: CHAID engines reject [CONT] predictors by contract."
        ),
        "step3_title": "Step 3 — Validation scheme",
        "step3_subtitle": "Stratified holdout partition (Hamilton-Hare).",
        "step3_scheme_label": "Scheme",
        "step3_scheme_holdout": "Holdout (stratified, Hamilton-Hare)",
        "step3_scheme_cv_todo": "Cross-validation (Phase 2.1.b)",
        "step3_seed_label": "Random seed",
        "step3_train_label": "Train",
        "step3_test_label": "Test",
        "step4_title": "Step 4 — MRM governance",
        "step4_subtitle": "Regularisation and regulatory controls.",
        "step4_govmode_title": "Governance mode",
        "step4_govmode_banking": "Banking (MRM / IFRS 9)",
        "step4_govmode_banking_desc": (
            "Jeffreys estimator ON · PD Floor 0.0003 (Basel 3 bps)"
        ),
        "step4_govmode_research": "Research (raw)",
        "step4_govmode_research_desc": "Jeffreys estimator OFF · no PD Floor",
        "step4_apply_jeffreys": "Apply Jeffreys correction",
        "step4_max_depth": "Max depth",
        "step4_min_child": "Min child size",
        "step4_pd_floor": "PD floor",
        "step4_summary_label": "Summary",
        "step4_summary_engine": "Engine",
        "step4_govmode_banking_short": "Banking",
        "step4_govmode_research_short": "Research",
        "dlg_open_dataset_title": "Open dataset",
        "dlg_open_dataset_filter": "CSV files (*.csv)",
        "msg_model_trained": "Model trained: {method} ({n} nodes)",
        "msg_error_title": "TreeGov — Error",
        # --- Phase 2.2: interactive tree viewer ---
        "tab_tree_title": "Model tree",
        "tree_empty": "Train a model to display the tree (Ctrl+N).",
        "tree_hdr_nodes": "nodes",
        "tree_hdr_leaves": "leaves",
        "tree_hdr_fp": "Fingerprint",
        "tree_large_warning": (
            "Large tree ({n} nodes). Consider reducing max_depth or "
            "pruning (Phase 2.4)."
        ),
        "tree_zoom_in": "Zoom in (Ctrl++)",
        "tree_zoom_out": "Zoom out (Ctrl+-)",
        "tree_zoom_fit": "Fit (Ctrl+0)",
        "tree_leaf_badge": "LEAF",
        "tree_leaf_reason_max_depth": "max depth reached",
        "tree_leaf_reason_min_child": "min child size",
        "tree_leaf_reason_sin_split": "no valid split",
        "tree_leaf_reason_rama_insuficiente": "child branch too small",
        "tree_groups": "groups",
        "tree_node_events": "events",
        "tree_node_pd": "PD",
        "tree_prop_node": "Node",
        "tree_prop_depth": "Depth",
        "tree_prop_pd_jeffreys": "PD (Jeffreys)",
        "tree_prop_pd_final": "PD (final, operational on leaves)",
        "tree_prop_floor_note": "PD floor binding (BCBS CRE 20.39)",
        "tree_prop_leaf": "Leaf reason",
        "tree_prop_predictor": "Predictor",
        "tree_prop_statistic": "Statistic",
        "tree_prop_gain": "Impurity gain",
        "tree_prop_branch": "Branch",
        "tree_prop_method": "Method",
        "tree_prop_empty": (
            "Train a model and select a node to see its properties."
        ),
        "tab_oos_oot_title": "OOS / OOT",
        "oos_section_title": "Out-of-Sample validation",
        "oos_label_sample": "Sample",
        "oos_label_auc": "AUC",
        "oos_label_ks": "KS",
        "oos_label_gini": "Gini (2·AUC-1)",
        "oos_label_pr_auc": "PR-AUC",
        "oos_label_brier": "Brier",
        "oos_label_brier_skill": "Brier skill",
        "oos_label_hl": "Hosmer-Lemeshow",
        "oos_label_pd_mean": "Mean PD",
        "oos_roc_title": "ROC curve points",
        "oot_section_title": "Out-of-Time monitoring",
        "oot_label_psi": "PSI",
        "oot_label_csi": "CSI",
        "oot_label_gini_drop": "Gini drop",
        "oot_gini_alert_msg": "Critical degradation",
        "status_stable": "STABLE",
        "status_moderate": "MODERATE",
        "status_unstable": "UNSTABLE",
        "status_undetermined": "UNDETERMINED",
        "status_critical": "CRITICAL",
        "status_warning": "WARNING",
        "status_none": "NONE",
        "oos_oot_no_model": "Train a model to compute OOS/OOT metrics.",
        "oos_oot_no_oos": "No OOS sample (partition is not enabled).",
        "oos_oot_no_oot": "No OOT cohort loaded.",
    },
    "es": {
        "window_title": "TreeGov — Risk Segmentation Workbench",
        "menu_file": "Archivo",
        "menu_model": "Modelo",
        "menu_view": "Ver",
        "menu_help": "Ayuda",
        "menu_file_new_wizard": "Asistente de nuevo modelo...",
        "menu_file_open": "Abrir dataset...",
        "menu_file_exit": "Salir",
        "menu_model_train": "Entrenar",
        "menu_model_evaluate_oos": "Evaluar OOS",
        "menu_model_load_oot": "Cargar cohorte OOT...",
        "menu_view_theme": "Tema",
        "menu_view_theme_light": "Claro",
        "menu_view_theme_dark": "Oscuro",
        "menu_view_language": "Idioma",
        "menu_view_language_en": "English",
        "menu_view_language_es": "Español",
        "menu_view_toggle_left": "Panel izquierdo",
        "menu_view_toggle_right": "Panel de propiedades",
        "menu_help_about": "Acerca de TreeGov",
        "panel_left_title": "Explorador de proyecto",
        "panel_center_title": "Espacio de trabajo",
        "panel_right_title": "Propiedades",
        "tab_welcome_title": "Bienvenido",
        "status_ready": "Listo",
        "status_session": "Sesión",
        "status_theme": "Tema",
        "status_mode": "Modo",
        "about_title": "Acerca de TreeGov",
        "about_body": (
            "Herramienta de segmentación de riesgo con gobernanza MRM/IFRS 9 "
            "nativa.\nVersión {version} · Licencia Apache 2.0"
        ),
        # --- Fase 2.1: wizard transaccional ---
        "wizard_title": "Asistente de nuevo modelo",
        "wizard_next": "Siguiente",
        "wizard_back": "Atrás",
        "wizard_finish": "Finalizar",
        "wizard_cancel": "Cancelar",
        "step1_title": "Paso 1 — Selección del motor",
        "step1_subtitle": "Elija el algoritmo de partición.",
        "step1_desc_chaid": (
            "CHAID — fusión multirrama de categorías con corrección de "
            "Bonferroni (Kass, 1980)"
        ),
        "step1_desc_chaid_exhaustive": (
            "CHAID exhaustivo — fusión hasta el agotamiento "
            "(Biggs, de Ville y Suen, 1991)"
        ),
        "step1_desc_crt": (
            "C&RT — partición binaria por Gini/varianza con splits surrogate "
            "(Breiman et al., 1984)"
        ),
        "step1_desc_quest": (
            "QUEST — selección insesgada de variable con corte QDA "
            "univariante (Loh y Shih, 1997)"
        ),
        "step2_title": "Paso 2 — Predictores y objetivo",
        "step2_subtitle": "Elija el objetivo binario y al menos un predictor.",
        "step2_target_label": "Objetivo (binario 0/1):",
        "step2_available": "Predictores disponibles",
        "step2_selected": "Predictores seleccionados",
        "step2_hint_min_one": "Seleccione al menos un predictor para continuar.",
        "step2_chaid_cont_note": (
            "Nota: los motores CHAID rechazan predictores [CONT] por contrato."
        ),
        "step3_title": "Paso 3 — Esquema de validación",
        "step3_subtitle": "Partición holdout estratificada (Hamilton-Hare).",
        "step3_scheme_label": "Esquema",
        "step3_scheme_holdout": "Holdout (estratificado, Hamilton-Hare)",
        "step3_scheme_cv_todo": "Validación cruzada (Fase 2.1.b)",
        "step3_seed_label": "Semilla aleatoria",
        "step3_train_label": "Entrenamiento",
        "step3_test_label": "Prueba",
        "step4_title": "Paso 4 — Gobernanza MRM",
        "step4_subtitle": "Regularización y controles regulatorios.",
        "step4_govmode_title": "Modo de gobernanza",
        "step4_govmode_banking": "Banca (MRM / IFRS 9)",
        "step4_govmode_banking_desc": (
            "Estimador de Jeffreys ON · PD Floor 0.0003 (Basilea 3 bps)"
        ),
        "step4_govmode_research": "Investigación (crudo)",
        "step4_govmode_research_desc": (
            "Estimador de Jeffreys OFF · sin PD Floor"
        ),
        "step4_apply_jeffreys": "Aplicar corrección de Jeffreys",
        "step4_max_depth": "Profundidad máxima",
        "step4_min_child": "Tamaño mínimo de hijo",
        "step4_pd_floor": "PD floor",
        "step4_summary_label": "Resumen",
        "step4_summary_engine": "Motor",
        "step4_govmode_banking_short": "Bancario",
        "step4_govmode_research_short": "Investigación",
        "dlg_open_dataset_title": "Abrir dataset",
        "dlg_open_dataset_filter": "Archivos CSV (*.csv)",
        "msg_model_trained": "Modelo entrenado: {method} ({n} nodos)",
        "msg_error_title": "TreeGov — Error",
        # --- Fase 2.2: visor interactivo de árbol ---
        "tab_tree_title": "Árbol del modelo",
        "tree_empty": "Entrene un modelo para visualizar el árbol (Ctrl+N).",
        "tree_hdr_nodes": "nodos",
        "tree_hdr_leaves": "hojas",
        "tree_hdr_fp": "Huella",
        "tree_large_warning": (
            "Árbol grande ({n} nodos). Considere reducir max_depth o "
            "podar (Fase 2.4)."
        ),
        "tree_zoom_in": "Acercar (Ctrl++)",
        "tree_zoom_out": "Alejar (Ctrl+-)",
        "tree_zoom_fit": "Ajustar (Ctrl+0)",
        "tree_leaf_badge": "HOJA",
        "tree_leaf_reason_max_depth": "profundidad máxima alcanzada",
        "tree_leaf_reason_min_child": "tamaño mínimo de hijo",
        "tree_leaf_reason_sin_split": "sin split válido",
        "tree_leaf_reason_rama_insuficiente": "rama hija insuficiente",
        "tree_groups": "grupos",
        "tree_node_events": "eventos",
        "tree_node_pd": "PD",
        "tree_prop_node": "Nodo",
        "tree_prop_depth": "Profundidad",
        "tree_prop_pd_jeffreys": "PD (Jeffreys)",
        "tree_prop_pd_final": "PD (final, operativa en hojas)",
        "tree_prop_floor_note": "PD floor activo (BCBS CRE 20.39)",
        "tree_prop_leaf": "Motivo de hoja",
        "tree_prop_predictor": "Predictor",
        "tree_prop_statistic": "Estadístico",
        "tree_prop_gain": "Ganancia de impureza",
        "tree_prop_branch": "Rama",
        "tree_prop_method": "Método",
        "tree_prop_empty": (
            "Entrene un modelo y seleccione un nodo para ver sus propiedades."
        ),
        "tab_oos_oot_title": "OOS / OOT",
        "oos_section_title": "Validación fuera de muestra",
        "oos_label_sample": "Muestra",
        "oos_label_auc": "AUC",
        "oos_label_ks": "KS",
        "oos_label_gini": "Gini (2·AUC-1)",
        "oos_label_pr_auc": "PR-AUC",
        "oos_label_brier": "Brier",
        "oos_label_brier_skill": "Habilidad de Brier",
        "oos_label_hl": "Hosmer-Lemeshow",
        "oos_label_pd_mean": "PD media",
        "oos_roc_title": "Puntos de la curva ROC",
        "oot_section_title": "Monitoreo fuera de tiempo",
        "oot_label_psi": "PSI",
        "oot_label_csi": "CSI",
        "oot_label_gini_drop": "Caída de Gini",
        "oot_gini_alert_msg": "Degradación crítica",
        "status_stable": "ESTABLE",
        "status_moderate": "MODERADO",
        "status_unstable": "INESTABLE",
        "status_undetermined": "INDETERMINADO",
        "status_critical": "CRÍTICO",
        "status_warning": "PREVENTIVO",
        "status_none": "SIN ALERTA",
        "oos_oot_no_model": "Entrene un modelo para calcular las métricas OOS/OOT.",
        "oos_oot_no_oos": "Sin muestra OOS (partición no habilitada).",
        "oos_oot_no_oot": "Sin cohorte OOT cargada.",
    },
}

SUPPORTED: tuple[str, ...] = tuple(_STRINGS)
_DEFAULT: str = "en"
_current: str = _DEFAULT


def tr(key: str, lang: str | None = None) -> str:
    """Return the string for `key` in `lang` (active language if None)."""
    lang = _current if lang is None else lang
    try:
        table = _STRINGS[lang]
    except KeyError:
        raise ValueError(
            f"Unsupported language: {lang!r} (supported: {SUPPORTED})"
        ) from None
    try:
        return table[key]
    except KeyError:
        raise KeyError(f"Unknown i18n key: '{key}'") from None


def set_language(lang: str) -> None:
    """Activate `lang` as the module-level current language."""
    global _current
    if lang not in _STRINGS:
        raise ValueError(
            f"Unsupported language: {lang!r} (supported: {SUPPORTED})"
        )
    _current = lang


def get_language() -> str:
    """Return the active language code ("en" or "es")."""
    return _current


def detect_system_language() -> str:
    """Best locale guess: QLocale.system().name() 'es_EC' -> 'es'; else 'en'.

    QLocale.system() is static-safe: no QApplication instance required.
    """
    code = QLocale.system().name().split("_")[0].lower()
    return code if code in _STRINGS else _DEFAULT


class LanguageBus(QObject):
    """Notification channel for live language switches (Phase 2.1).

    Design invariant: every language change enters through
    MainWindow._switch_language(), which (1) calls set_language(), then
    (2) emits this bus. Dialogs/wizards connect to the bus to retranslate
    themselves while open. The bus never mutates the active language.
    """

    language_changed = Signal(str)


language_bus = LanguageBus()  # process-wide singleton
