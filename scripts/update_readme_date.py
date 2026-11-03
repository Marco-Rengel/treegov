"""scripts/update_readme_date.py — fechas 📅 de estado en los READMEs.

Sub-fase 1.c.1 de la Fase 1 (diseño: docs/scripts_design.md §2, contratos
U1–U6). Uso:

    python scripts/update_readme_date.py                 # muta con hoy
    python scripts/update_readme_date.py --check         # no escribe; exit 0/1
    python scripts/update_readme_date.py --date 2026-11-02

Contratos as-built (por ID del backlog):

- U1 (fallo ruidoso): si el regex del marcador 📅 no matchea contra un
  target, ``RuntimeError`` con la ruta del archivo y el patrón esperado;
  aborta con traceback antes de tocar disco. En modo ``--check``, el
  drift de formato se reporta como línea de error y termina exit 1.
- U2 (escritura atómica): los dos renders se producen en memoria y se
  verifican ANTES de tocar disco; después cada target se escribe a un
  temp del mismo directorio y se aplica ``os.replace`` (atómico). Si un
  rename falla tras haber aplicado el otro, se restaura el contenido
  previo y se aborta: la divergencia entre READMEs no es un estado
  posible.
- U3 (contrato 📅): el marcador 📅 es el opt-in canónico del workflow
  (protege las fechas históricas de changelogs). Regla: toda fecha de
  estado corriente de release va marcada con 📅 en ambos READMEs. Los
  targets se declaran por constantes (``TARGET_FILES``); el script no
  descubre archivos en runtime.
- U4 (--check): sin escrituras; para cada pendiente imprime el diff
  (``ruta: vigente -> candidata``) y termina exit 1; al día, imprime
  ``OK`` y termina exit 0.
- U5 (guarda de retroceso): la fecha vigente del README se parsea y se
  compara con la candidata (por defecto, hoy); si la candidata es
  anterior a la vigente (año del README mayor que el año actual del
  sistema, mismo año con mes mayor, o cualquier día posterior),
  ``RuntimeError`` "no se puede retroceder en el tiempo". En --check
  el retroceso se reporta como pendiente, sin escribir.
- U6 (anclaje): ``ROOT_DIR`` desde ``__file__`` (nunca desde el cwd) y
  targets a ``ROOT_DIR / "README.md"`` y ``ROOT_DIR / "README.es.md"``.
  Superficie de salida: ``print`` (esta salida es material de CLI
  humano; el logging estructurado aplica a los scripts de datos, no a
  la utilería de fechas).

Line endings: lectura y escritura con ``newline=''`` para preservar
los del repo (normalizados vía ``.gitattributes``); una pasada sin
cambio de fecha produce un diff vacío.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date as Date
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent  # U6: raíz del repo, no cwd

# U3: targets por constante (ruta relativa a ROOT_DIR, ¿es español?).
TARGET_FILES: list[tuple[str, bool]] = [
    ("README.md", False),
    ("README.es.md", True),
]

MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# U1/U5: los patrones capturan la fecha para poder parsear el vigente.
_PATTERN_EN = r"📅 ([A-Za-z]{3} [0-9]{2}, [0-9]{4})"
_PATTERN_ES = r"📅 ([0-9]{2} [a-z]{3} [0-9]{4})"


def _pattern_for(is_spanish: bool) -> str:
    """Regex canónico por idioma (captura la fecha)."""
    return _PATTERN_ES if is_spanish else _PATTERN_EN


def render_date(is_spanish: bool, candidate: Date) -> str:
    """Fecha candidata en el formato canónico del README."""
    if is_spanish:
        return f"{candidate.day:02d} {MESES_ES[candidate.month - 1]} {candidate.year}"
    return f"{MESES_EN[candidate.month - 1]} {candidate.day:02d}, {candidate.year}"


def _month_from_name(name: str, is_spanish: bool) -> int:
    """Índice de mes (1-based) desde la marca textual."""
    meses = MESES_ES if is_spanish else MESES_EN
    try:
        idx = meses.index(name)
    except ValueError as exc:
        raise RuntimeError(
            f"Mes desconocido '{name}' (is_spanish={is_spanish})"
        ) from exc
    return idx + 1


def parse_marca(raw_date: str, is_spanish: bool) -> Date:
    """Parsea ``02 nov 2026`` (ES) o ``Nov 02, 2026`` (EN) a ``date``."""
    raw = raw_date.strip()
    if is_spanish:
        day_s, month_s, year_s = raw.split(" ")
        return Date(int(year_s), _month_from_name(month_s, is_spanish), int(day_s))
    month_s, day_s, year_s = raw.replace(",", "").split(" ")
    return Date(int(year_s), _month_from_name(month_s, is_spanish), int(day_s))


def _read(path: Path) -> str:
    """Lectura con ``newline=''``: conserva los line endings del archivo."""
    with path.open("r", encoding="utf-8", newline="") as f:
        return f.read()


def _analyse_target(
    path: Path, is_spanish: bool, candidate: Date
) -> tuple[str, str, Date, str]:
    """Análisis en memoria de un target (U1/U5; sin tocar disco).

    Devuelve ``(content, vigente_str, vigente_date, nuevo_str)``. Lanza
    ``RuntimeError`` (ruta + patrón) si el regex no matchea (U1).
    """
    pattern = _pattern_for(is_spanish)
    content = _read(path)
    matches = re.findall(pattern, content)
    if not matches:
        raise RuntimeError(
            f"patron no matchea en {path}: se esperaba '{pattern}' "
            "(marcador de calendario + fecha)"
        )
    vigente_str = matches[0]
    vigente_date = parse_marca(vigente_str, is_spanish)
    nuevo_str = render_date(is_spanish, candidate)
    return content, vigente_str, vigente_date, nuevo_str


def _temp_name(path: Path) -> Path:
    """Ruta del temp hermano (mismo directorio; U2)."""
    return path.with_name(path.name + ".tmp")


def _restore(path: Path, prev_content: str) -> None:
    """Restaura el contenido previo al fallo de rename (U2)."""
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(prev_content)


def _apply_atomic_pair(writes: list[tuple[Path, str, str]]) -> None:
    """Escritura atómica de la lista completa (U2).

    ``writes``: lista de ``(path, nuevo_contenido, prev_contenido)``.
    Todos los temps se escriben ANTES del primer ``os.replace``; si un
    rename falla, se restaura el contenido previo de los targets ya
    renombrados y se aborta. Line endings intactos (``newline=''``).
    """
    renamed: list[tuple[Path, str]] = []
    tmps: list[Path] = []
    cur_target: Path | None = None
    try:
        # Fase A: escribir todos los temps (ningún target tocado aún).
        for path, new_content, _prev in writes:
            cur_target = path
            tmp = _temp_name(path)
            with tmp.open("w", encoding="utf-8", newline="") as f:
                f.write(new_content)
            tmps.append(tmp)
        # Fase B: renames seguidos (os.replace es atómico por target).
        for (path, _new, _prev), tmp in zip(writes, tmps):
            cur_target = path
            os.replace(tmp, path)
            renamed.append((path, _prev))
    except OSError as exc:
        # Fase R: restaurar los targets ya renombrados (U2).
        for path, prev_content in reversed(renamed):
            try:
                _restore(path, prev_content)
                print(f"  {path}: restaurado al contenido previo tras el fallo")
            except OSError as restore_exc:
                print(
                    f"  {path}: restauracion fallida: {restore_exc!r}",
                    file=sys.stderr,
                )
        raise RuntimeError(
            f"escritura atomica fallida cerca de {cur_target}: {exc!r}"
        ) from exc
    finally:
        for tmp in tmps:
            if tmp.exists():
                tmp.unlink()  # limpieza de temps sobrevivientes


def _check_target(path: Path, is_spanish: bool, candidate: Date) -> str | None:
    """U4/U5 en modo check: línea de reporte, o None si está al día.

    Nunca escribe. El drift U1 y el retroceso U5 se reportan como
    líneas de error (exit 1 global), no como abort: la salida del
    check es material de CLI y conviene ver TODOS los problemas en
    una sola pasada.
    """
    try:
        _content, vigente_str, vigente_date, nuevo_str = _analyse_target(
            path, is_spanish, candidate
        )
    except RuntimeError as exc:
        return f"ERROR: {exc}"
    if vigente_date > candidate:
        return (
            f"{path}: vigente {vigente_str} -> candidata {nuevo_str} "
            "(retroceso temporal: requiere revision manual)"
        )
    if vigente_date == candidate:
        return None
    return f"{path}: {vigente_str} -> {nuevo_str}"


def _candidate_from_args(args: argparse.Namespace) -> Date:
    """Fecha candidata: ``--date`` (YYYY-MM-DD) o hoy (U5)."""
    if args.date is None:
        return Date.today()
    return datetime.strptime(args.date, "%Y-%m-%d").date()


def run_check(candidate: Date | None = None) -> int:
    """U4: verifica ambos targets; sin escribir. Devuelve 0/1."""
    candidate = candidate or Date.today()
    problems: list[str] = []
    for rel, is_spanish in TARGET_FILES:
        report = _check_target(ROOT_DIR / rel, is_spanish, candidate)
        if report is not None:
            problems.append(report)
    if problems:
        print("READMEs desactualizados (o conflicto de formato):")
        for line in problems:
            print(f"  {line}")
        return 1
    print("OK")
    return 0


def run_mutate(candidate: Date | None = None) -> int:
    """Modo default. Devuelve 0; aborta ante cualquier fallo imposible.

    Flujo U1 → U5 → U3 → U2: análisis de ambos targets (U1), guarda de
    retroceso (U5), renders en memoria (solo targets que cambian) y
    escritura atómica (U2).
    """
    candidate = candidate or Date.today()
    # S1/S2: análisis + guarda de retroceso de TODOS los targets antes
    # de tocar disco (sin estado intermedio; U2).
    plan: list[tuple[Path, bool, str, str, Date, str]] = []
    for rel, is_spanish in TARGET_FILES:
        path = ROOT_DIR / rel
        content, vigente_str, vigente_date, nuevo_str = _analyse_target(
            path, is_spanish, candidate
        )
        if vigente_date > candidate:  # U5: no se puede retroceder
            raise RuntimeError(
                f"no se puede retroceder en el tiempo: {path} tiene fecha "
                f"vigente '{vigente_str}' y la candidata es la anterior "
                f"('{nuevo_str}')"
            )
        plan.append((path, is_spanish, content, vigente_str, vigente_date, nuevo_str))

    # S3: renders en memoria; solo se escriben los que cambian.
    writes: list[tuple[Path, str, str]] = []
    diffs: list[str] = []
    for path, is_spanish, content, vigente_str, _vig, nuevo_str in plan:
        pattern = _pattern_for(is_spanish)
        new_content = re.sub(pattern, f"📅 {nuevo_str}", content)
        if new_content != content:
            writes.append((path, new_content, content))
            diffs.append(f"{path}: {vigente_str} -> {nuevo_str} (escrito)")
        else:
            print(f"{path}: al dia (sin cambios)")

    if not writes:
        print("OK: todos los READMEs al dia")
        return 0

    # S4: escritura atómica (temps → os.replace → abort+restore si falla).
    _apply_atomic_pair(writes)
    for line in diffs:
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entrypoint (U4/U6).

    Devuelve ``0`` si todo está al día o la mutación completa; ``1``
    cuando check encuentra pendientes o drift. Los aborts (U1/U5 en
    mutate, U2 en el fase de escritura) propagan la excepción:
    traceback y exit != 0.
    """
    parser = argparse.ArgumentParser(
        description="Actualiza (o verifica) las fechas 📅 de estado de los "
        "READMEs (docs/scripts_design.md §2)."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="verifica sin escribir: imprime los diffs pendientes y sale "
        "con exit 1, o OK con exit 0 (U4)",
    )
    parser.add_argument(
        "--date", type=str, default=None, metavar="YYYY-MM-DD",
        help="fecha candidata (default: hoy; U5)",
    )
    args = parser.parse_args(argv)

    # Consola cp1252 (PowerShell legacy): un print que contenga el emoji
    # 📅 o caracteres fuera de la codepage rompe la emisión con
    # UnicodeEncodeError; con errors='replace' se muestra sin romper.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")

    candidate = _candidate_from_args(args)
    if args.check:
        return run_check(candidate)
    return run_mutate(candidate)


if __name__ == "__main__":
    raise SystemExit(main())
