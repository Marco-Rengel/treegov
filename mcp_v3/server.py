"""MCP server implementation for TreeGov (Phase 5.0.b).

Glue code that binds the headless backend_v3.Session to the official
Model Context Protocol SDK. The server uses stdio transport, keeping
all data on the local machine.
"""

from __future__ import annotations
import logging

from mcp.server.fastmcp import FastMCP

from backend_v3.session_state import Session
from backend_v3.types import TargetType
from mcp_v3.dto import _jsonable

logger = logging.getLogger(__name__)

# El proceso MCP tiene una única sesión en memoria.
_session: Session | None = None

def _get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session

app = FastMCP("TreeGov")

# --- Grupo A: Estado y lectura ---

@app.tool()
def get_session_state() -> dict:
    """Current FlowState and a summary of the session."""
    st = _jsonable(_get_session().state)
    st.pop("train_idx", None)
    st.pop("test_idx", None)
    return st

@app.tool()
def load_dataset(csv_path: str) -> dict:
    """Load a local CSV dataset."""
    return _jsonable(_get_session().load_dataset(csv_path))

@app.tool()
def describe_dataset() -> dict:
    """Profile columns and inferred types."""
    cols, types = _get_session().describe_dataset()
    return {"columns": cols, "types": types}

@app.tool()
def get_data_preview(n_rows: int = 50) -> dict:
    """Raw JSON-native preview of the CSV."""
    return _get_session().get_data_preview(n_rows)

@app.tool()
def describe_target(target: str) -> dict:
    """Distribution of a candidate target column."""
    return _get_session().describe_target(target)

@app.tool()
def describe_weight_column(col: str) -> dict:
    """Validate a sample-weight column."""
    return _get_session().describe_weight_column(col)

@app.tool()
def describe_population_column(col: str) -> dict:
    """Validate a population-filter column."""
    return _get_session().describe_population_column(col)

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
    # Pydantic puede enviar los keys de class_labels como str.
    # Si el target_class es int, casteamos los keys a int.
    parsed_labels = {}
    for k, v in class_labels.items():
        try:
            parsed_labels[int(k)] = v
        except ValueError:
            parsed_labels[k] = v

    parsed_tc = target_class
    if isinstance(target_class, str) and target_class.isdigit():
        parsed_tc = int(target_class)

    cost = tuple(tuple(row) for row in cost_matrix) if cost_matrix else ()
    p_ok = tuple(population_ok_values) if population_ok_values else None

    return _jsonable(_get_session().fix_spec(
        target=target,
        predictors=predictors,
        target_class=parsed_tc,
        class_labels=parsed_labels,
        weight_col=weight_col,
        population_col=population_col,
        population_ok_values=p_ok,
        cost_matrix=cost,
    ))

@app.tool()
def partition(train_frac: float = 0.7, seed: int = 42) -> dict:
    """Stratified holdout partition."""
    return _jsonable(_get_session().partition(train_frac, seed))

@app.tool()
def reset_to_data_loaded() -> dict:
    """Reset session to DATA_LOADED, keeping the CSV cached."""
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
    tt = TargetType.BINARY if target_type.lower() == "binary" else TargetType.CATEGORICAL

    if governance_mode.lower() == "research":
        pd_floor = None
        jeffreys = False
    else:
        pd_floor = 0.0005
        jeffreys = True

    return _jsonable(_get_session().train(
        engine=engine,
        target_type=tt,
        max_depth=max_depth,
        min_child_size=min_child_size,
        min_child_weight=min_child_weight,
        pd_floor=pd_floor,
        apply_jeffreys=jeffreys,
    ))

@app.tool()
def evaluate_oos(n_groups: int | None = None) -> dict:
    """Compute OOS metrics."""
    s = _get_session()
    if n_groups is None:
        n_test = len(s.state.test_idx) if s.state.test_idx else 0
        n_groups = max(3, min(10, n_test // 5))
    return _jsonable(s.evaluate_oos(n_groups=n_groups))

@app.tool()
def get_oos_oot_report() -> dict:
    """Flat DTO of the OOS/OOT report."""
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
    return _jsonable(_get_session().get_gains_table(
        partition=partition, by=by, n_buckets=n_buckets, tie=tie, seed=seed
    ))

@app.tool()
def get_classification_matrix(partition: str = "oos", threshold: float = 0.5) -> dict:
    """Classification matrix."""
    return _jsonable(_get_session().get_classification_matrix(partition=partition, threshold=threshold))

@app.tool()
def get_univariate_trees(max_depth: int = 3) -> list:
    """Univariate trees for all predictors."""
    return _jsonable(_get_session().get_univariate_trees(max_depth=max_depth))

# --- Grupo D: Interacción ---

@app.tool()
def get_prune_sequence() -> list:
    """Cost-complexity pruning sequence."""
    return _jsonable(_get_session().get_prune_sequence())

@app.tool()
def prune(alpha: float) -> dict:
    """Apply pruning at a given alpha."""
    return _jsonable(_get_session().prune(alpha))

@app.tool()
def intervene_node(node_id: int, action: str, payload: dict | None = None) -> dict:
    """Manual intervention on a node (prune_branch)."""
    return _jsonable(_get_session().intervene_node(node_id, action, payload))

# --- Grupo E: OOT ---

@app.tool()
def load_oot(csv_path: str, time_col: str | None = None) -> dict:
    """Load out-of-time cohort."""
    return _jsonable(_get_session().load_oot(csv_path, time_col=time_col))

@app.tool()
def evaluate_oot(n_groups: int = 10, weight_oot: bool = True) -> dict:
    """Evaluate OOT metrics and stability."""
    return _jsonable(_get_session().evaluate_oot(n_groups=n_groups, weight_oot=weight_oot))

# --- Grupo F: Exportadores ---

@app.tool()
def export_sql(unseen_policy: str = "exclude") -> str:
    """Export as ANSI SQL.

    unseen_policy (default "exclude"): comportamiento ante categorías
    no vistas; ver docs/4.0.1_design_categorical_exporters.md. La
    validación del valor la hace el exportador (ValueError /
    NotImplementedError).
    """
    return _get_session().export_to_sql(unseen_policy=unseen_policy)

@app.tool()
def export_python(unseen_policy: str = "exclude") -> str:
    """Export as Python module.

    unseen_policy (default "exclude"): comportamiento ante categorías
    no vistas; ver docs/4.0.1_design_categorical_exporters.md. La
    validación del valor la hace el exportador (ValueError /
    NotImplementedError).
    """
    return _get_session().export_to_python(unseen_policy=unseen_policy)

@app.tool()
def export_markdown(unseen_policy: str = "exclude") -> str:
    """Export as Markdown.

    unseen_policy (default "exclude"): comportamiento ante categorías
    no vistas; ver docs/4.0.1_design_categorical_exporters.md. La
    validación del valor la hace el exportador (ValueError /
    NotImplementedError).
    """
    return _get_session().export_to_markdown(unseen_policy=unseen_policy)
