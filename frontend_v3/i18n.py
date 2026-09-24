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

from PySide6.QtCore import QLocale

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
        "about_title": "About TreeGov",
        "about_body": (
            "Risk segmentation workbench with native MRM/IFRS 9 governance.\n"
            "Version {version} · Apache 2.0 License"
        ),
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
        "about_title": "Acerca de TreeGov",
        "about_body": (
            "Herramienta de segmentación de riesgo con gobernanza MRM/IFRS 9 "
            "nativa.\nVersión {version} · Licencia Apache 2.0"
        ),
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
