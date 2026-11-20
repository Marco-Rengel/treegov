"""MCP server implementation for TreeGov (Phase 5.0.b).

Glue code that binds the headless backend_v3.Session to the official
Model Context Protocol SDK. The server uses stdio transport, keeping
all data on the local machine.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from mcp.server.fastmcp import FastMCP

from backend_v3.session_state import Session
from backend_v3.tree_builder import BASEL_PD_FLOOR_MIN
from backend_v3.types import TargetType
from mcp_v3.dto import _jsonable

logger = logging.getLogger(__name__)

# El proceso MCP tiene una única sesión en memoria protegida por un RLock.
_session: Session | None = None
_session_lock = threading.RLock()


def _get_session() -> Session:
    global _session
    with _session_lock:
        if _session is None:
            _session = Session()
        return _session


def _get_allowed_root() -> Path:
    """Resolve the authorized directory for CSV access (TREEGOV_MCP_ROOT or CWD)."""
    env_val = os.environ.get("TREEGOV_MCP_ROOT", "").strip()
    if env_val:
        root = Path(env_val).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(
                "[mcp] TREEGOV_MCP_ROOT no es un directorio válido"
            )
        return root
    return Path.cwd().resolve()


def _resolve_csv_path(
    raw_path: str,
    *,
    must_exist: bool,
    forbid_existing: bool = False,
) -> Path:
    """Validate and confine a CSV path strictly within the authorized root."""
    if (
        not isinstance(raw_path, str)
        or not raw_path.strip()
        or "\x00" in raw_path
    ):
        raise ValueError("[mcp] ruta de archivo inválida")

    allowed_root = _get_allowed_root()
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (allowed_root / candidate).resolve()

    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"[mcp] ruta fuera del directorio autorizado: {raw_path!r}"
        ) from exc

    if resolved.suffix.lower() != ".csv":
        raise ValueError(
            f"[mcp] solo se permiten archivos .csv: {raw_path!r}"
        )

    if must_exist and not (resolved.exists() and resolved.is_file()):
        raise ValueError(f"[mcp] archivo CSV inexistente: {raw_path!r}")

    if forbid_existing:
        if not (resolved.parent.exists() and resolved.parent.is_dir()):
            raise ValueError(
                f"[mcp] directorio de salida inexistente: {raw_path!r}"
            )
        if resolved.exists():
            raise ValueError(
                "[mcp] el archivo de salida ya existe; sobrescritura "
                "bloqueada por política de seguridad"
            )

    return resolved


def _validate_int(
    name: str,
    value: Any,
    *,
    min_val: int | None = None,
    max_val: int | None = None,
) -> int:
    """Validate an integer parameter, rejecting booleans and out-of-range values."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise ValueError(
            f"[mcp] {name} debe ser un entero (recibido: {value!r})"
        )
    ival = int(value)
    if min_val is not None and ival < min_val:
        raise ValueError(
            f"[mcp] {name} debe ser >= {min_val} (recibido: {ival})"
        )
    if max_val is not None and ival > max_val:
        raise ValueError(
            f"[mcp] {name} debe ser <= {max_val} (recibido: {ival})"
        )
    return ival


def _validate_float(
    name: str,
    value: Any,
    *,
    min_val: float | None = None,
    max_val: float | None = None,
    strict_min: bool = False,
    strict_max: bool = False,
) -> float:
    """Validate a finite numeric parameter, rejecting booleans and NaN/Inf."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        raise ValueError(
            f"[mcp] {name} debe ser un número finito (recibido: {value!r})"
        )
    fval = float(value)
    if not math.isfinite(fval):
        raise ValueError(
            f"[mcp] {name} debe ser un número finito (recibido: {value!r})"
        )
    if min_val is not None:
        if strict_min and not (fval > min_val):
            raise ValueError(
                f"[mcp] {name} debe ser > {min_val} (recibido: {fval})"
            )
        if not strict_min and not (fval >= min_val):
            raise ValueError(
                f"[mcp] {name} debe ser >= {min_val} (recibido: {fval})"
            )
    if max_val is not None:
        if strict_max and not (fval < max_val):
            raise ValueError(
                f"[mcp] {name} debe ser < {max_val} (recibido: {fval})"
            )
        if not strict_max and not (fval <= max_val):
            raise ValueError(
                f"[mcp] {name} debe ser <= {max_val} (recibido: {fval})"
            )
    return fval


def _coerce_target_value(raw_val: Any, observed: list[Any]) -> Any:
    """Coerce a JSON-serialized class value against observed target classes.

    - Rejects booleans when the observed target classes are not boolean.
    - Preserves exact matches (including string classes such as ``"01"``).
    - Coerces canonical string representations (e.g. ``"1"``, ``"-1"``) only
      when matching a unique observed non-bool integer class; avoids crashing
      on Unicode digits such as ``"²"`` and refuses silent coercion of ``"01"``
      into ``1``.
    - Returns ``raw_val`` unchanged if unmatched so ``Session.fix_spec`` emits
      its standard diagnostic ``ValueError``.
    """
    norm_obs: list[Any] = []
    for val in observed:
        if isinstance(val, (bool, np.bool_)):
            norm_obs.append(bool(val))
        elif isinstance(val, (int, np.integer)):
            norm_obs.append(int(val))
        else:
            norm_obs.append(val)

    has_bool_obs = any(isinstance(val, bool) for val in norm_obs)
    if isinstance(raw_val, (bool, np.bool_)) and not has_bool_obs:
        raise ValueError(
            f"[mcp] valor booleano no admitido como clase del target: {raw_val!r}"
        )

    raw_is_bool = isinstance(raw_val, (bool, np.bool_))
    for val in norm_obs:
        val_is_bool = isinstance(val, bool)
        if raw_is_bool != val_is_bool:
            continue
        if isinstance(raw_val, str) != isinstance(val, str):
            continue
        if raw_val == val:
            return val

    if isinstance(raw_val, str):
        int_matches = [
            val
            for val in norm_obs
            if isinstance(val, int)
            and not isinstance(val, bool)
            and str(int(val)) == raw_val
        ]
        if len(int_matches) == 1:
            return int_matches[0]

    return raw_val


app = FastMCP("TreeGov")

# --- Grupo A: Estado y lectura ---


@app.tool()
def get_session_state() -> dict:
    """Current FlowState and a summary of the session."""
    with _session_lock:
        st = _jsonable(_get_session().state)
        st.pop("train_idx", None)
        st.pop("test_idx", None)
        return st


@app.tool()
def load_dataset(csv_path: str) -> dict:
    """Load a local CSV dataset."""
    resolved = _resolve_csv_path(csv_path, must_exist=True)
    with _session_lock:
        return _jsonable(_get_session().load_dataset(str(resolved)))


@app.tool()
def describe_dataset() -> dict:
    """Profile columns and inferred types."""
    with _session_lock:
        cols, types = _get_session().describe_dataset()
        return _jsonable({"columns": cols, "types": types})


@app.tool()
def get_data_preview(n_rows: int = 50) -> dict:
    """Raw JSON-native preview of the CSV."""
    n_rows = _validate_int("n_rows", n_rows, min_val=1, max_val=5000)
    with _session_lock:
        return _jsonable(_get_session().get_data_preview(n_rows))


@app.tool()
def describe_target(target: str) -> dict:
    """Distribution of a candidate target column."""
    with _session_lock:
        return _jsonable(_get_session().describe_target(target))


@app.tool()
def describe_weight_column(col: str) -> dict:
    """Validate a sample-weight column."""
    with _session_lock:
        return _jsonable(_get_session().describe_weight_column(col))


@app.tool()
def describe_population_column(col: str) -> dict:
    """Validate a population-filter column."""
    with _session_lock:
        return _jsonable(_get_session().describe_population_column(col))


# --- Grupo B: Configuración y partición ---


@app.tool()
def fix_spec(
    target: str,
    target_class: int | str,
    class_labels: dict[str, str],
    predictors: list[str] | None = None,
    weight_col: str | None = None,
    population_col: str | None = None,
    population_ok_values: list[str] | None = None,
    cost_matrix: list[list[float]] | None = None,
) -> dict:
    """Fix target, class labels, predictors, weight_col, population_col."""
    if not isinstance(class_labels, Mapping):
        raise ValueError("[mcp] class_labels debe ser un diccionario")
    if population_ok_values is not None and len(population_ok_values) == 0:
        raise ValueError(
            "[mcp] population_ok_values no puede ser una lista vacía"
        )
    p_ok = (
        tuple(population_ok_values)
        if population_ok_values is not None
        else None
    )
    cost = tuple(tuple(row) for row in cost_matrix) if cost_matrix else ()

    with _session_lock:
        session = _get_session()
        try:
            observed = list(session.describe_target(target).keys())
        except (RuntimeError, ValueError):
            observed = []

        parsed_labels: dict[Any, str] = {}
        for k, v in class_labels.items():
            coerced_k = _coerce_target_value(k, observed)
            if coerced_k in parsed_labels:
                raise ValueError(
                    "[mcp] claves duplicadas en class_labels tras normalización"
                )
            parsed_labels[coerced_k] = v

        parsed_tc = _coerce_target_value(target_class, observed)

        return _jsonable(
            session.fix_spec(
                target=target,
                predictors=predictors,
                target_class=parsed_tc,
                class_labels=parsed_labels,
                weight_col=weight_col,
                population_col=population_col,
                population_ok_values=p_ok,
                cost_matrix=cost,
            )
        )


@app.tool()
def partition(train_frac: float = 0.7, seed: int = 42) -> dict:
    """Stratified holdout partition."""
    train_frac = _validate_float(
        "train_frac",
        train_frac,
        min_val=0.0,
        max_val=1.0,
        strict_min=True,
        strict_max=True,
    )
    seed = _validate_int("seed", seed)
    with _session_lock:
        return _jsonable(_get_session().partition(train_frac, seed))


@app.tool()
def reset_to_data_loaded() -> dict:
    """Reset session to DATA_LOADED, keeping the CSV cached."""
    with _session_lock:
        return _jsonable(_get_session().reset_to_data_loaded())


# --- Grupo C: Entrenamiento y evaluación ---


@app.tool()
def train(
    engine: str,
    target_type: str = "binary",
    max_depth: int = 4,
    min_child_size: int = 50,
    min_child_weight: float | None = None,
    governance_mode: str = "banking",
) -> dict:
    """Train the tree using a named engine. governance_mode: banking/research."""
    if not isinstance(target_type, str):
        raise ValueError(
            f"[mcp] target_type inválido: {target_type!r} "
            "(válidos: 'binary', 'categorical')"
        )
    tt_norm = target_type.strip().lower()
    if tt_norm == "binary":
        tt = TargetType.BINARY
    elif tt_norm == "categorical":
        tt = TargetType.CATEGORICAL
    else:
        raise ValueError(
            f"[mcp] target_type inválido: {target_type!r} "
            "(válidos: 'binary', 'categorical')"
        )

    if not isinstance(governance_mode, str):
        raise ValueError(
            f"[mcp] governance_mode inválido: {governance_mode!r} "
            "(válidos: 'banking', 'research')"
        )
    gov_norm = governance_mode.strip().lower()
    if gov_norm == "banking":
        pd_floor = BASEL_PD_FLOOR_MIN
        jeffreys = True
    elif gov_norm == "research":
        pd_floor = None
        jeffreys = False
    else:
        raise ValueError(
            f"[mcp] governance_mode inválido: {governance_mode!r} "
            "(válidos: 'banking', 'research')"
        )

    max_depth = _validate_int("max_depth", max_depth, min_val=1, max_val=20)
    min_child_size = _validate_int(
        "min_child_size", min_child_size, min_val=1
    )
    if min_child_weight is not None:
        min_child_weight = _validate_float(
            "min_child_weight",
            min_child_weight,
            min_val=0.0,
            strict_min=True,
        )

    with _session_lock:
        return _jsonable(
            _get_session().train(
                engine=engine,
                target_type=tt,
                max_depth=max_depth,
                min_child_size=min_child_size,
                min_child_weight=min_child_weight,
                pd_floor=pd_floor,
                apply_jeffreys=jeffreys,
            )
        )


@app.tool()
def evaluate_oos(n_groups: int | None = None) -> dict:
    """Compute OOS metrics."""
    if n_groups is not None:
        n_groups = _validate_int("n_groups", n_groups, min_val=3, max_val=100)
    with _session_lock:
        s = _get_session()
        if n_groups is None:
            n_test = len(s.state.test_idx) if s.state.test_idx else 0
            n_groups = max(3, min(10, n_test // 5))
        return _jsonable(s.evaluate_oos(n_groups=n_groups))


@app.tool()
def get_oos_oot_report() -> dict:
    """Flat DTO of the OOS/OOT report."""
    with _session_lock:
        return _jsonable(_get_session().get_oos_oot_report())


@app.tool()
def get_gains_table(
    partition: str = "oos",
    by: str = "leaf",
    n_buckets: int = 10,
    tie: str = "preserve",
    seed: int | None = None,
) -> dict:
    """Gains table by leaf or bucket."""
    n_buckets = _validate_int("n_buckets", n_buckets, min_val=1, max_val=1000)
    if seed is not None:
        seed = _validate_int("seed", seed)
    with _session_lock:
        return _jsonable(
            _get_session().get_gains_table(
                partition=partition,
                by=by,
                n_buckets=n_buckets,
                tie=tie,
                seed=seed,
            )
        )


@app.tool()
def get_classification_matrix(
    partition: str = "oos", threshold: float = 0.5
) -> dict:
    """Classification matrix."""
    threshold = _validate_float(
        "threshold", threshold, min_val=0.0, max_val=1.0
    )
    with _session_lock:
        return _jsonable(
            _get_session().get_classification_matrix(
                partition=partition, threshold=threshold
            )
        )


@app.tool()
def get_univariate_trees(max_depth: int = 3) -> list:
    """Univariate trees for all predictors."""
    max_depth = _validate_int("max_depth", max_depth, min_val=1, max_val=20)
    with _session_lock:
        return _jsonable(_get_session().get_univariate_trees(max_depth=max_depth))


# --- Grupo D: Interacción ---


@app.tool()
def get_prune_sequence() -> list:
    """Cost-complexity pruning sequence."""
    with _session_lock:
        return _jsonable(_get_session().get_prune_sequence())


@app.tool()
def prune(alpha: float) -> dict:
    """Apply pruning at a given alpha."""
    alpha = _validate_float("alpha", alpha, min_val=0.0)
    with _session_lock:
        return _jsonable(_get_session().prune(alpha))


@app.tool()
def intervene_node(
    node_id: int, action: str, payload: dict | None = None
) -> dict:
    """Manual intervention on a node (prune_branch)."""
    node_id = _validate_int("node_id", node_id, min_val=0)
    with _session_lock:
        return _jsonable(
            _get_session().intervene_node(node_id, action, payload)
        )


# --- Grupo E: OOT ---


@app.tool()
def load_oot(csv_path: str, time_col: str | None = None) -> dict:
    """Load out-of-time cohort."""
    resolved = _resolve_csv_path(csv_path, must_exist=True)
    with _session_lock:
        return _jsonable(_get_session().load_oot(str(resolved), time_col=time_col))


@app.tool()
def evaluate_oot(n_groups: int = 10, weight_oot: bool = True) -> dict:
    """Evaluate OOT metrics and stability."""
    n_groups = _validate_int("n_groups", n_groups, min_val=3, max_val=100)
    with _session_lock:
        return _jsonable(
            _get_session().evaluate_oot(
                n_groups=n_groups, weight_oot=weight_oot
            )
        )


# --- Grupo F: Exportadores ---


@app.tool()
def export_sql(unseen_policy: str = "exclude") -> str:
    """Export as ANSI SQL.

    unseen_policy (default "exclude"): comportamiento ante categorías
    no vistas; ver docs/4.0.1_design_categorical_exporters.md. La
    validación del valor la hace el exportador (ValueError /
    NotImplementedError).
    """
    with _session_lock:
        return _get_session().export_to_sql(unseen_policy=unseen_policy)


@app.tool()
def export_python(unseen_policy: str = "exclude") -> str:
    """Export as Python module.

    unseen_policy (default "exclude"): comportamiento ante categorías
    no vistas; ver docs/4.0.1_design_categorical_exporters.md. La
    validación del valor la hace el exportador (ValueError /
    NotImplementedError).
    """
    with _session_lock:
        return _get_session().export_to_python(unseen_policy=unseen_policy)


@app.tool()
def export_markdown(unseen_policy: str = "exclude") -> str:
    """Export as Markdown.

    unseen_policy (default "exclude"): comportamiento ante categorías
    no vistas; ver docs/4.0.1_design_categorical_exporters.md. La
    validación del valor la hace el exportador (ValueError /
    NotImplementedError).
    """
    with _session_lock:
        return _get_session().export_to_markdown(unseen_policy=unseen_policy)


# --- Grupo G: Scoring y Champion-Challenger (Fase 6) ---


@app.tool()
def score_batch(
    csv_path: str,
    output_path: str,
    unseen_policy: str = "exclude",
    chunksize: int = 50000,
    include_rules: bool = True,
) -> dict:
    """Score a CSV file in chunks using the trained model."""
    chunksize = _validate_int(
        "chunksize", chunksize, min_val=1, max_val=1_000_000
    )
    in_path = _resolve_csv_path(csv_path, must_exist=True)
    out_path = _resolve_csv_path(
        output_path, must_exist=False, forbid_existing=False
    )
    if out_path == in_path:
        raise ValueError("[mcp] output_path no puede ser igual a csv_path")
    out_path = _resolve_csv_path(
        output_path, must_exist=False, forbid_existing=True
    )
    with _session_lock:
        return _jsonable(
            _get_session().score_batch(
                csv_path=str(in_path),
                output_path=str(out_path),
                unseen_policy=unseen_policy,
                chunksize=chunksize,
                include_rules=include_rules,
            )
        )


@app.tool()
def compare_champion_challenger(
    evaluation_csv: str,
    challenger_engine: str | None = None,
    challenger_params: dict | None = None,
    target: str | None = None,
    weight_col: str | None = None,
    unseen_policy: str = "exclude",
    n_groups: int = 10,
) -> dict:
    """Compare champion and challenger models on an evaluation CSV."""
    n_groups = _validate_int("n_groups", n_groups, min_val=3, max_val=100)
    resolved = _resolve_csv_path(evaluation_csv, must_exist=True)
    with _session_lock:
        return _jsonable(
            _get_session().compare_champion_challenger(
                evaluation_csv=str(resolved),
                challenger_engine=challenger_engine,
                challenger_params=challenger_params,
                target=target,
                weight_col=weight_col,
                unseen_policy=unseen_policy,
                n_groups=n_groups,
            )
        )


# --- Grupo H: Fase 7 ---


@app.tool()
def calculate_ecl(
    csv_path: str,
    pd_column: str = "pd_current",
    eir: float | None = None,
) -> dict:
    """Calculate Expected Credit Loss (ECL) per IFRS 9."""
    if not isinstance(pd_column, str) or not pd_column.strip():
        raise ValueError("[mcp] pd_column no puede estar vacío")
    if eir is not None:
        eir = _validate_float("eir", eir, min_val=0.0)
    resolved = _resolve_csv_path(csv_path, must_exist=True)
    with _session_lock:
        return _jsonable(
            _get_session().calculate_ecl(
                csv_path=str(resolved),
                pd_column=pd_column,
                eir=eir,
            )
        )
