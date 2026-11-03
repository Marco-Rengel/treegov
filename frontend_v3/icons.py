from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap
from frontend_v3.theme import PALETTES

ICONS_DIR: Path = Path(__file__).parent / "resources" / "icons"


def load_icon(name: str, theme: str = "light") -> QIcon:
    """Carga un SVG temático sustituyendo currentColor por $FG."""
    svg_path = ICONS_DIR / f"{name}.svg"
    if not svg_path.exists():
        return QIcon()  # null icon; los tests detectan el fallo
    color = PALETTES[theme]["FG"]
    text = svg_path.read_text(encoding="utf-8")
    text = text.replace("currentColor", color)
    pixmap = QPixmap()
    pixmap.loadFromData(text.encode("utf-8"), "SVG")
    return QIcon(pixmap)


__all__ = ["ICONS_DIR", "load_icon"]
