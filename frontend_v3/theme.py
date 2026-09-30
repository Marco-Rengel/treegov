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

from PySide6.QtWidgets import QApplication

_TEMPLATE_PATH = Path(__file__).resolve().parent / "resources" / "styles.qss"
_TOKEN_RE = re.compile(r"\$[A-Z_]+")

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "BG": "#FFFFFF",
        "SURFACE": "#F5F5F5",
        "FG": "#1B1B1B",
        "BORDER": "#C8C8C8",
        "ACCENT": "#1F6FEB",
        "ACCENT_FG": "#FFFFFF",
        "DISABLED": "#9A9A9A",
        "STATUS_OK": "#2E7D32",
        "STATUS_WARN": "#ED6C02",
        "STATUS_CRIT": "#D32F2F",
        "STATUS_UNKNOWN": "#757575",
    },
    "dark": {
        "BG": "#1E1E1E",
        "SURFACE": "#2A2A2A",
        "FG": "#E6E6E6",
        "BORDER": "#454545",
        "ACCENT": "#4C9AFF",
        "ACCENT_FG": "#101010",
        "DISABLED": "#6E6E6E",
        "STATUS_OK": "#66BB6A",
        "STATUS_WARN": "#FFA726",
        "STATUS_CRIT": "#EF5350",
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
