"""Theme manager for the TreeGov GUI (light / dark).

Single QSS template (resources/styles.qss) with $TOKENS substituted via
string.Template: '$' never collides with Qt Style Sheet syntax (unlike
str.format's braces, which ARE QSS rule delimiters).

Fail-fast policy: an unknown theme or a palette/template token mismatch
raises ValueError. A silent visual fallback would defeat auditability.
"""

from __future__ import annotations

import re
from pathlib import Path
from string import Template

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

_TEMPLATE_PATH = Path(__file__).resolve().parent / "resources" / "styles.qss"
_TOKEN_RE = re.compile(r"\$[A-Z_]+")

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "BG": "#FFFFFF",
        "SURFACE": "#F8F9FA",
        "SURFACE_ELEVATED": "#FFFFFF",
        "NODE_BG": "#FFFFFF",
        "FG": "#202124",
        "BORDER": "#DADCE0",
        "ACCENT": "#1A73E8",
        "ACCENT_FG": "#FFFFFF",
        "DISABLED": "#80868B",
        "STATUS_OK": "#188038",
        "STATUS_WARN": "#F29900",
        "STATUS_CRIT": "#D93025",
        "STATUS_UNKNOWN": "#5F6368",
    },
    "dark": {
        "BG": "#1E1E1E",
        "SURFACE": "#252526",
        "SURFACE_ELEVATED": "#2D2D2D",
        "NODE_BG": "#000000",
        "FG": "#E0E0E0",
        "BORDER": "#3C3C3C",
        "ACCENT": "#4C9AFF",
        "ACCENT_FG": "#1E1E1E",
        "DISABLED": "#6E6E6E",
        "STATUS_OK": "#4CAF50",
        "STATUS_WARN": "#FF9800",
        "STATUS_CRIT": "#F44336",
        "STATUS_UNKNOWN": "#9E9E9E",
    },
}


def available_themes() -> tuple[str, ...]:
    """Return the supported theme names."""
    return tuple(PALETTES)


def render_stylesheet(name: str) -> str:
    """Render the QSS template for palette `name`; fail-fast on mismatch."""
    try:
        palette = PALETTES[name]
    except KeyError:
        raise ValueError(
            f"Unknown theme: {name!r} (available: {available_themes()})"
        ) from None
    template = Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    missing = set(template.get_identifiers()) - palette.keys()
    if missing:
        raise ValueError(f"Palette {name!r} missing tokens: {sorted(missing)}")
    qss = template.substitute(palette)
    residual = _TOKEN_RE.findall(qss)
    if residual:
        raise ValueError(f"Unresolved tokens in stylesheet: {residual}")
    return qss


def apply_theme(name: str, app: QApplication | None = None) -> None:
    """Apply theme `name` to `app` (or the running QApplication if None)."""
    target = app if app is not None else QApplication.instance()
    if target is None:
        raise RuntimeError("apply_theme requires a QApplication instance")
    target.setStyleSheet(render_stylesheet(name))


# Role mapping for apply_palette: the QSS cannot restyle native-rendered
# chrome (wizard title bar, native button frames, disabled text); the
# QPalette covers those parts. Roles not listed keep Qt defaults.
_PALETTE_ROLES: tuple[tuple[QPalette.ColorRole, str], ...] = (
    (QPalette.ColorRole.Window, "BG"),
    (QPalette.ColorRole.WindowText, "FG"),
    (QPalette.ColorRole.Base, "SURFACE_ELEVATED"),
    (QPalette.ColorRole.AlternateBase, "SURFACE"),
    (QPalette.ColorRole.Text, "FG"),
    (QPalette.ColorRole.Button, "SURFACE"),
    (QPalette.ColorRole.ButtonText, "FG"),
    (QPalette.ColorRole.Highlight, "ACCENT"),
    (QPalette.ColorRole.HighlightedText, "ACCENT_FG"),
)

_DISABLED_ROLES: tuple[QPalette.ColorRole, ...] = (
    QPalette.ColorRole.Text,
    QPalette.ColorRole.ButtonText,
    QPalette.ColorRole.WindowText,
)


def apply_palette(name: str, app: QApplication | None = None) -> None:
    """Force the TreeGov QPalette for theme `name` (Phase 3.11.a.1).

    Without an explicit palette, native-rendered surfaces (QWizard chrome,
    dialogs) inherit the WINDOWS light/dark mode instead of the app theme.
    Same fail-fast policy as apply_theme: unknown theme -> ValueError.
    """
    try:
        palette = PALETTES[name]
    except KeyError:
        raise ValueError(
            f"Unknown theme: {name!r} (available: {available_themes()})"
        ) from None
    target = app if app is not None else QApplication.instance()
    if target is None:
        raise RuntimeError("apply_palette requires a QApplication instance")
    qp = QPalette()
    for role, token in _PALETTE_ROLES:
        qp.setColor(role, QColor(palette[token]))
    disabled = QColor(palette["DISABLED"])
    for role in _DISABLED_ROLES:
        qp.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    target.setPalette(qp)
