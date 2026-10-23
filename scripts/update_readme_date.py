"""Utility to update the Mermaid diagram date in READMEs (TreeGov)."""
import re
from datetime import datetime
from pathlib import Path

MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def update_readme(path: Path, is_spanish: bool) -> None:
    now = datetime.now()
    if is_spanish:
        date_str = f"{now.day:02d} {MESES_ES[now.month - 1]} {now.year}"
        pattern = r'📅 [0-9]{2} [a-z]{3} [0-9]{4}'
    else:
        date_str = f"{MESES_EN[now.month - 1]} {now.day:02d}, {now.year}"
        pattern = r'📅 [a-zA-Z]{3} [0-9]{2}, [0-9]{4}'
    
    content = path.read_text(encoding="utf-8")
    new_content = re.sub(pattern, f"📅 {date_str}", content)
    
    if content != new_content:
        path.write_text(new_content, encoding="utf-8")
        print(f"Updated {path.name} with date: {date_str}")
    else:
        print(f"No changes needed for {path.name} (date: {date_str})")

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    update_readme(root / "README.md", is_spanish=False)
    update_readme(root / "README.es.md", is_spanish=True)