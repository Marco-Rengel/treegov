"""Tests de la infraestructura de iconos SVG temáticos."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_v3.icons import ICONS_DIR, load_icon  # noqa: E402


ICON_NAMES = (
    "open-dataset",
    "new-model",
    "train",
    "evaluate-oos",
    "load-oot",
    "prune",
    "zoom-in",
    "zoom-out",
    "zoom-fit",
    "type-nominal",
    "type-ordinal",
    "type-continuous",
    "engine-crt",
    "engine-chaid",
    "engine-chaid-exhaustive",
    "engine-quest",
    "gov-banking",
    "gov-research",
    "move-one-right",
    "move-one-left",
    "move-all-right",
    "move-all-left",
)


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_all_icons_present():
    missing = [name for name in ICON_NAMES if not (ICONS_DIR / f"{name}.svg").is_file()]
    assert len(ICON_NAMES) == 22
    assert not missing, f"Iconos ausentes: {missing}"


def test_load_icon_returns_non_null():
    _get_app()
    null_icons = [name for name in ICON_NAMES if load_icon(name).isNull()]
    assert not null_icons, f"Iconos nulos: {null_icons}"


def test_load_icon_light_vs_dark():
    _get_app()
    light = load_icon("engine-crt", theme="light").pixmap(32, 32).toImage()
    dark = load_icon("engine-crt", theme="dark").pixmap(32, 32).toImage()
    assert light.size() == dark.size()
    assert any(
        light.pixelColor(x, y) != dark.pixelColor(x, y)
        for x in range(light.width())
        for y in range(light.height())
    )


def test_svg_contains_current_color():
    svg_paths = sorted(ICONS_DIR.glob("*.svg"))
    assert len(svg_paths) == 22
    without_current_color = [
        path.name
        for path in svg_paths
        if "currentColor" not in path.read_text(encoding="utf-8")
    ]
    assert not without_current_color, (
        f"SVG con color horneado o sin currentColor: {without_current_color}"
    )


def test_load_icon_missing_returns_null():
    _get_app()
    assert load_icon("nonexistent").isNull() is True
