"""Descarga los iconos SVG de Bootstrap usados por la GUI de TreeGov."""

from pathlib import Path
import urllib.request


BASE_URL = "https://raw.githubusercontent.com/twbs/icons/v1.11.3/icons"
ICONS_DIR = Path(__file__).resolve().parents[1] / "frontend_v3" / "resources" / "icons"

ICONS = {
    "open-dataset": "folder2-open",
    "new-model": "file-earmark-plus",
    "train": "play-fill",
    "evaluate-oos": "clipboard-data",
    "load-oot": "folder-symlink",
    "prune": "trash",
    "zoom-in": "zoom-in",
    "zoom-out": "zoom-out",
    "zoom-fit": "arrows-fullscreen",
    "type-nominal": "tags",
    "type-ordinal": "sort-numeric-down",
    "type-continuous": "graph-up",
    "engine-crt": "diagram-2",
    "engine-chaid": "diagram-3",
    "engine-chaid-exhaustive": "arrow-repeat",
    "engine-quest": "question-circle",
    "gov-banking": "bank",
    "gov-research": "search",
    "move-one-right": "arrow-right",
    "move-one-left": "arrow-left",
    "move-all-right": "chevron-double-right",
    "move-all-left": "chevron-double-left",
}


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    for semantic_name, bootstrap_name in ICONS.items():
        destination = ICONS_DIR / f"{semantic_name}.svg"
        if destination.exists():
            print(f"SKIP {destination.name} (ya existe)")
            continue
        url = f"{BASE_URL}/{bootstrap_name}.svg"
        with urllib.request.urlopen(url, timeout=30) as response:
            destination.write_bytes(response.read())
        print(f"OK   {destination.name} <- {bootstrap_name}.svg")


if __name__ == "__main__":
    main()


# Bootstrap Icons v1.11.3 (MIT License)
# https://github.com/twbs/icons
# Re-ejecutar solo si se decide actualizar a una nueva versión.
