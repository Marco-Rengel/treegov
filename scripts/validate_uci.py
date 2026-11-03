"""scripts/validate_uci.py — validación E2E de los 6 datasets UCI (Fase 3.6).

Sub-fase 1.d.1 de la Fase 1 (diseño: docs/scripts_design.md §3, contratos
V1–V12). Uso:

    python scripts/validate_uci.py            # regenera el informe
    python scripts/validate_uci.py --check    # no escribe; exit 0/1

Contratos as-built (por ID del backlog):

- V1 (n_groups adaptativo): `n_test = len(sess.state.test_idx)` y
  `n_groups = min(10, max(3, n_test // 5))`, la misma fórmula de
  `Session.evaluate_oot` (Hosmer–Lemeshow exige al menos 3 grupos y
  `n_groups * 5 <= N`).
- V2 (target_type explícito): BINARY para german_credit,
  breast_cancer_wdbc y blood_transfusion; CATEGORICAL para
  car_evaluation, balance_scale e iris. Se pasa a `Session.train`.
- V3/V4 (narrativa dinámica): se eliminan `_QUALITATIVE_NOTES` y
  `_REVISION_NOTES`. `_get_revision_notes()` deriva la fecha del último
  commit que tocó `backend_v3/tree_builder.py` con
  `git log -1 --format=%ad --date=short -- <archivo>`; sin fallback
  silencioso: si git no responde, `RuntimeError`.
  Consecuencia esperada: la primera regeneración cambia el informe
  (desaparece la sección cualitativa y las notas congeladas de rc2).
- V5 (--check + árbol limpio): `--check` no escribe; compara el informe
  vigente con una regeneración y termina 0 si coincide, 1 (con diff
  unificado) si difiere. Sin `--check`, `git status --porcelain` debe
  estar vacío antes de entrenar; en caso contrario `RuntimeError`.
- V6 (métricas None): si `gini`, `ks` o `auc` son None se imprime
  `ERROR: métrica no computable`, la fila se marca como error y el
  proceso termina con exit 2 (distinguible del 1 de --check y del 0 de
  éxito). Nunca se escribe un informe con huecos.
- V9 (target_class justificada): cada CONFIG documenta por qué elige su
  clase de interés (evento de negocio o baseline histórica 3.6).
- V10 (PD_FLOOR): el suelo de PD es una constante nombrada con cita
  (BCBS CRE 32.4; docs/methodology.md), no un literal por dataset.
- V11/V12 (anclaje): `ROOT_DIR` desde `__file__`; `FIXTURES` y
  `TARGET_MD` cuelgan de la raíz; `sys.path` usa la raíz, nunca el cwd
  ni `scripts/`.

Fuera de alcance en esta sub-fase (el prompt de 1.d.1 fija los motores y
la tabla vigentes): V7 (CHAID 6/6) y V8 (separar semántica de accuracy
por target_type). Ambas quedan marcadas con TODO(zona_gris) y exigen su
propia sub-fase con regeneración del informe y recaptura de fingerprints.
"""

from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent  # V11/V12: raíz, no cwd
sys.path.insert(0, str(ROOT_DIR))                  # V12: backend_v3 desde la raíz

from backend_v3.session_state import Session      # noqa: E402
from backend_v3.types import TargetType           # noqa: E402

FIXTURES = ROOT_DIR / "tests" / "fixtures" / "uci"          # V11
TARGET_MD = ROOT_DIR / "docs" / "validation_results_3.6.md"  # V5

# V10: suelo de PD de Banking mode (BCBS CRE 32.4; docs/methodology.md).
PD_FLOOR = 0.0005

# 14 pares (dataset, motor) que verifica tests/test_uci_integration.py.
# Decision as-built (31/10/2026, B8): CHAID se omite en 4 datasets
# (german_credit, breast_cancer_wdbc, iris, blood_transfusion) por
# ALCANCE de la Fase 3.6 original, no por contrato del motor. CHAID
# acepta CONTINUOUS desde H14 (3.10.b). Si se quiere incluir, es una
# Fase 3.6.x separada que regenere el informe con 18 filas y recapture
# 4 fingerprints nuevos en tests/test_uci_integration.py.
#
# TODO(zona_gris): V7 (CHAID 6/6) no se aplica en 1.d.1 porque el prompt
# de la sub-fase no lo ordena y su ejecución cambia el informe y exige
# recaptura de fingerprints; resolver en una sub-fase propia.
VALID_ENGINES: dict[str, list[str]] = {
    "german_credit": ["CRT", "QUEST"],
    "car_evaluation": ["CRT", "CHAID", "QUEST"],
    "balance_scale": ["CRT", "CHAID", "QUEST"],
    "breast_cancer_wdbc": ["CRT", "QUEST"],
    "iris": ["CRT", "QUEST"],
    "blood_transfusion": ["CRT", "QUEST"],
}

CONFIGS = {
    "german_credit": {
        "csv": "german_credit/german_credit.csv",
        "target": "target",
        "target_class": 1,  # V9: evento de negocio = impago (Bad)
        "class_labels": {0: "Good", 1: "Bad"},
        "target_type": TargetType.BINARY,
        "max_depth": 4,
        "min_child_size": 50,
        "pd_floor": PD_FLOOR,
        "seed": 42,
    },
    "car_evaluation": {
        "csv": "car_evaluation/car_evaluation.csv",
        "target": "target",
        # V9: clase mayoritaria (unacc) = baseline histórica de la 3.6.
        "target_class": 0,
        "class_labels": {0: "unacc", 1: "acc", 2: "good", 3: "vgood"},
        "target_type": TargetType.CATEGORICAL,
        "max_depth": 3,
        "min_child_size": 50,
        "pd_floor": PD_FLOOR,
        "seed": 42,
    },
    "balance_scale": {
        "csv": "balance_scale/balance_scale.csv",
        "target": "target",
        # V9: L (0) es la clase de referencia histórica; L y R empatan a
        # 288 casos, así que no hay mayoría estricta.
        "target_class": 0,
        "class_labels": {0: "L", 1: "B", 2: "R"},
        "target_type": TargetType.CATEGORICAL,
        "max_depth": 3,
        "min_child_size": 20,
        "pd_floor": PD_FLOOR,
        "seed": 42,
    },
    "breast_cancer_wdbc": {
        "csv": "breast_cancer_wdbc/breast_cancer_wdbc.csv",
        "target": "target",
        "target_class": 1,  # V9: evento de negocio = maligno (Malignant)
        "class_labels": {0: "Benign", 1: "Malignant"},
        "target_type": TargetType.BINARY,
        "max_depth": 4,
        "min_child_size": 20,
        "pd_floor": PD_FLOOR,
        "seed": 42,
    },
    "iris": {
        "csv": "iris/iris.csv",
        "target": "target",
        # V9: Setosa (0) como clase de referencia; el dataset está
        # balanceado 50/50/50 y no tiene clase mayoritaria.
        "target_class": 0,
        "class_labels": {0: "Setosa", 1: "Versicolor", 2: "Virginica"},
        "target_type": TargetType.CATEGORICAL,
        "max_depth": 3,
        "min_child_size": 10,
        "pd_floor": PD_FLOOR,
        "seed": 42,
    },
    "blood_transfusion": {
        "csv": "blood_transfusion/blood_transfusion.csv",
        "target": "target",
        "target_class": 1,  # V9: evento de negocio = donante (Donor)
        "class_labels": {0: "Non-donor", 1: "Donor"},
        "target_type": TargetType.BINARY,
        "max_depth": 4,
        "min_child_size": 20,
        "pd_floor": PD_FLOOR,
        "seed": 42,
    },
}


def _run_one(name: str, cfg: dict, engine_name: str) -> dict:
    """Ejecuta el pipeline y devuelve un dict con los campos del informe.

    En error devuelve `{'error': <mensaje>, 'error_kind': ...}`. Una
    métrica None (V6) se reporta como error duro, no como hueco.
    """
    row: dict = {"dataset": name, "engine": engine_name}
    try:
        sess = Session()
        sess.load_dataset(str(FIXTURES / cfg["csv"]))
        cols, _ = sess.describe_dataset()
        predictors = [c for c in cols if c != cfg["target"]]
        sess.fix_spec(
            target=cfg["target"],
            predictors=predictors,
            target_class=cfg["target_class"],
            class_labels=cfg["class_labels"],
        )
        sess.partition(train_frac=0.7, seed=cfg["seed"])
        sess.train(
            engine=engine_name,
            target_type=cfg["target_type"],  # V2: explícito por dataset
            max_depth=cfg["max_depth"],
            min_child_size=cfg["min_child_size"],
            pd_floor=cfg["pd_floor"],        # V10: constante nombrada
        )

        # V1: n_groups adaptativo al tamaño real del test.
        test_idx = sess.state.test_idx
        if not test_idx:
            raise RuntimeError(
                f"[validate] test_idx vacío para {name} / {engine_name}"
            )
        n_test = len(test_idx)
        n_groups = min(10, max(3, n_test // 5))
        sess.evaluate_oos(n_groups=n_groups)

        st = sess.state
        tree = st.tree
        metrics = st.oos_metrics
        mat = sess.get_classification_matrix()
        acc = mat.get("accuracy") if mat else None
        row.update(
            {
                "fingerprint": tree.params_fingerprint,
                "nodes": len(tree.nodes),
                "leaves": sum(1 for n in tree.nodes if n.is_leaf),
                "gini": metrics.gini,
                "ks": metrics.ks,
                "auc": metrics.auc,
                "accuracy": acc,
                "n_groups": n_groups,
                "error": None,
            }
        )

        # V6: métrica None = error duro (nunca un informe con huecos).
        missing = [k for k in ("gini", "ks", "auc") if row[k] is None]
        if missing:
            print("ERROR: métrica no computable", file=sys.stderr)
            detalle = ", ".join(f"{k} = None" for k in missing)
            print(f"  detalle: {name} / {engine_name}: {detalle}",
                  file=sys.stderr)
            row["error"] = f"métrica no computable: {detalle}"
            row["error_kind"] = "metric_none"
        return row
    except Exception as exc:
        row["error"] = str(exc).replace("\n", " ")
        row["error_kind"] = "exception"
        return row


def _get_revision_notes() -> str:
    """V3/V4: revision notes derivadas del último commit del tree builder.

    Ejecuta exactamente `git log -1 --format=%ad --date=short --
    backend_v3/tree_builder.py`. Sin fallback: un árbol sin git o sin
    historial del archivo aborta con `RuntimeError` (la fecha del informe
    no puede ser inventada).
    """
    proc = subprocess.run(
        [
            "git", "log", "-1", "--format=%ad", "--date=short",
            "--", "backend_v3/tree_builder.py",
        ],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    fecha = proc.stdout.strip()
    if proc.returncode != 0 or not fecha:
        raise RuntimeError(
            "no se pudo obtener la fecha de backend_v3/tree_builder.py con "
            f"'git log -1 --format=%ad --date=short' (exit {proc.returncode}): "
            f"{proc.stderr.strip() or 'sin salida'}"
        )
    return (
        "## Revision notes\n\n"
        f"### {fecha} — Fingerprints recapturados\n\n"
        "Los fingerprints actuales fueron generados con el código de "
        f"tree_builder.py del commit del {fecha}."
    )


def _assert_clean_tree() -> None:
    """V5: aborta si `git status --porcelain` reporta cambios sin commitear."""
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git status --porcelain falló en {ROOT_DIR} "
            f"(exit {proc.returncode}): {proc.stderr.strip() or 'sin salida'}"
        )
    dirty = proc.stdout.strip()
    if dirty:
        raise RuntimeError(
            "árbol de trabajo sucio: la regeneración del informe exige un "
            "árbol limpio (V5). Haga commit o descarte estos cambios:\n"
            f"{dirty}"
        )


def _fmt(value: float | None) -> str:
    """Formatea una métrica del informe (None -> 'None')."""
    return f"{value:.4f}" if value is not None else "None"


def _table_lines(results: list[dict]) -> list[str]:
    """Filas de la tabla cuantitativa (misma forma que el informe v3.6)."""
    lines = [
        "| Dataset | Engine | Fingerprint | Nodes | Leaves | Gini | KS | AUC | Accuracy |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.get("error"):
            lines.append(
                f"| {r['dataset']} | {r['engine']} | **ERROR** | - | - | - | - | - | - |"
            )
            continue
        lines.append(
            f"| {r['dataset']} | {r['engine']} | {r['fingerprint']} | "
            f"{r['nodes']} | {r['leaves']} | {_fmt(r['gini'])} | "
            f"{_fmt(r['ks'])} | {_fmt(r['auc'])} | {_fmt(r['accuracy'])} |"
        )
    return lines


def _render_markdown(results: list[dict]) -> str:
    """Genera el contenido del informe (determinista; no escribe).

    TODO(zona_gris): V8 (separar la semántica de accuracy por target_type)
    no se aplica en 1.d.1: el prompt mantiene la tabla única vigente.
    """
    for r in results:
        if r.get("error"):
            raise RuntimeError(
                "[validate] no se puede renderizar una fila con error: "
                f"{r['dataset']} / {r['engine']}"
            )
    lines: list[str] = []
    lines.append("# TreeGov — Validation Results (Phase 3.6)")
    lines.append("")
    lines.append("This document is GENERATED by `scripts/validate_uci.py`.")
    lines.append("Tables and sections are fully deterministic given the")
    lines.append("repository code. The generation date and the commit")
    lines.append("that produced these results are available via")
    lines.append("`git log -- docs/validation_results_3.6.md`.")
    lines.append("")
    lines.append(
        "**Configuration:** train_frac=0.7, seed=42; engines "
        "and depths per dataset; pd_floor=0.0005 (default, "
        "Banking mode)."
    )
    lines.append("")
    lines.append("## Quantitative Baseline")
    lines.append("")
    lines.extend(_table_lines(results))
    lines.append("")
    lines.append(_get_revision_notes())
    lines.append("")
    return "\n".join(lines)


def _write_target(generated: str) -> None:
    """Escribe el informe con LF (`.gitattributes`: eol=lf)."""
    TARGET_MD.parent.mkdir(parents=True, exist_ok=True)
    with TARGET_MD.open("w", encoding="utf-8", newline="") as f:
        f.write(generated)


def _check_against_target(generated: str) -> int:
    """V5: compara sin escribir. 0 = idéntico; 1 = drift (imprime diff)."""
    if not TARGET_MD.exists():
        print(f"ERROR: no existe el informe vigente {TARGET_MD}", file=sys.stderr)
        return 1
    existing = TARGET_MD.read_text(encoding="utf-8")  # universal newlines
    if existing == generated:
        print("OK")
        return 0
    diff = difflib.unified_diff(
        existing.splitlines(keepends=True),
        generated.splitlines(keepends=True),
        fromfile=f"{TARGET_MD.name} (vigente)",
        tofile=f"{TARGET_MD.name} (regenerado)",
        lineterm="\n",
    )
    text = "".join(diff)
    if text and not text.endswith("\n"):
        text += "\n"
    sys.stdout.write(text)
    return 1


def _collect_results() -> list[dict]:
    """Ejecuta los 14 pares (dataset, motor) del manifiesto."""
    results: list[dict] = []
    for name, cfg in CONFIGS.items():
        for engine_name in VALID_ENGINES[name]:
            results.append(_run_one(name, cfg, engine_name))
    return results


def run(check: bool = False) -> int:
    """Entrypoint operativo. 0 = OK; 1 = drift/error; 2 = métrica None."""
    if not check:
        _assert_clean_tree()  # V5: antes de entrenar nada

    results = _collect_results()
    errors = [r for r in results if r.get("error")]

    if not check:
        for line in _table_lines(results):
            print(line)
    if errors:
        for r in errors:
            print(f"\nERROR {r['dataset']} / {r['engine']}: {r['error']}",
                  file=sys.stderr)
        print(f"\n{len(errors)} errores; el informe NO se escribe.",
              file=sys.stderr)
        if any(r.get("error_kind") == "metric_none" for r in errors):
            return 2  # V6
        return 1

    generated = _render_markdown(results)
    if check:
        return _check_against_target(generated)

    _write_target(generated)
    print(f"\nInforme escrito en {TARGET_MD} ({len(results)} filas)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entrypoint CLI. `--check` verifica; sin flag regenera."""
    parser = argparse.ArgumentParser(
        description="Valida los 6 datasets UCI y regenera (o verifica con "
        "--check) docs/validation_results_3.6.md (docs/scripts_design.md §3)."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="no escribe: compara la regeneración contra el informe vigente "
        "y sale con 1 si difiere, 0 si es idéntico (V5)",
    )
    args = parser.parse_args(argv)

    # Consola cp1252 (PowerShell legacy): el informe y los diffs pueden
    # contener '—' o acentos; con errors='replace' nunca rompe la emisión.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")

    return run(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
