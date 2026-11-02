"""MCP tool registry for TreeGov (Phase 5.0).

Tools are represented as plain frozen dataclasses. No MCP SDK is
imported here: the registry is testable headless, and the server
(Phase 5.0.b) only assembles the protocol around it.

Invariant I-4: every tool maps 1:1 to a public method (or property)
of backend_v3.session_state.Session.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend_v3.session_state import FlowState


@dataclass(frozen=True)
class ToolDescriptor:
    """A single tool exposed over MCP."""

    name: str
    description: str
    method_name: str
    min_state: FlowState


TOOLS: tuple[ToolDescriptor, ...] = (
    # --- Grupo A: Estado y lectura del dataset ---
    ToolDescriptor(
        name="get_session_state",
        description="Current FlowState and a summary of the session.",
        method_name="state",
        min_state=FlowState.EMPTY,
    ),
    ToolDescriptor(
        name="load_dataset",
        description="Load a local CSV dataset.",
        method_name="load_dataset",
        min_state=FlowState.EMPTY,
    ),
    ToolDescriptor(
        name="describe_dataset",
        description="Profile columns and inferred types.",
        method_name="describe_dataset",
        min_state=FlowState.DATA_LOADED,
    ),
    ToolDescriptor(
        name="get_data_preview",
        description="Raw JSON-native preview of the CSV.",
        method_name="get_data_preview",
        min_state=FlowState.DATA_LOADED,
    ),
    ToolDescriptor(
        name="describe_target",
        description="Distribution of a candidate target column.",
        method_name="describe_target",
        min_state=FlowState.DATA_LOADED,
    ),
    ToolDescriptor(
        name="describe_weight_column",
        description="Validate a sample-weight column.",
        method_name="describe_weight_column",
        min_state=FlowState.DATA_LOADED,
    ),
    ToolDescriptor(
        name="describe_population_column",
        description="Validate a population-filter column.",
        method_name="describe_population_column",
        min_state=FlowState.DATA_LOADED,
    ),

    # --- Grupo B: Configuración y partición ---
    ToolDescriptor(
        name="fix_spec",
        description="Fix target, class labels, predictors, weight_col, population_col.",
        method_name="fix_spec",
        min_state=FlowState.DATA_LOADED,
    ),
    ToolDescriptor(
        name="partition",
        description="Stratified holdout partition.",
        method_name="partition",
        min_state=FlowState.SPEC_FIXED,
    ),
    ToolDescriptor(
        name="reset_to_data_loaded",
        description="Reset session to DATA_LOADED, keeping the CSV cached.",
        method_name="reset_to_data_loaded",
        min_state=FlowState.DATA_LOADED,
    ),

    # --- Grupo C: Entrenamiento y evaluación ---
    ToolDescriptor(
        name="train",
        description="Train the tree using a named engine.",
        method_name="train",
        min_state=FlowState.PARTITIONED,
    ),
    ToolDescriptor(
        name="evaluate_oos",
        description="Compute OOS metrics.",
        method_name="evaluate_oos",
        min_state=FlowState.TRAINED,
    ),
    ToolDescriptor(
        name="get_oos_oot_report",
        description="Flat DTO of the OOS/OOT report.",
        method_name="get_oos_oot_report",
        min_state=FlowState.TRAINED,
    ),
    ToolDescriptor(
        name="get_gains_table",
        description="Gains table by leaf or bucket.",
        method_name="get_gains_table",
        min_state=FlowState.TRAINED,
    ),
    ToolDescriptor(
        name="get_classification_matrix",
        description="Classification matrix.",
        method_name="get_classification_matrix",
        min_state=FlowState.TRAINED,
    ),
    ToolDescriptor(
        name="get_univariate_trees",
        description="Univariate trees for all predictors.",
        method_name="get_univariate_trees",
        min_state=FlowState.TRAINED,
    ),

    # --- Grupo D: Interacción ---
    ToolDescriptor(
        name="get_prune_sequence",
        description="Cost-complexity pruning sequence.",
        method_name="get_prune_sequence",
        min_state=FlowState.TRAINED,
    ),
    ToolDescriptor(
        name="prune",
        description="Apply pruning at a given alpha.",
        method_name="prune",
        min_state=FlowState.TRAINED,
    ),
    ToolDescriptor(
        name="intervene_node",
        description="Manual intervention on a node (prune_branch).",
        method_name="intervene_node",
        min_state=FlowState.TRAINED,
    ),

    # --- Grupo E: OOT ---
    ToolDescriptor(
        name="load_oot",
        description="Load out-of-time cohort.",
        method_name="load_oot",
        min_state=FlowState.TRAINED,
    ),
    ToolDescriptor(
        name="evaluate_oot",
        description="Evaluate OOT metrics and stability.",
        method_name="evaluate_oot",
        min_state=FlowState.OOT_LOADED,
    ),

    # --- Grupo F: Exportadores ---
    ToolDescriptor(
        name="export_sql",
        description="Export as ANSI SQL.",
        method_name="export_to_sql",
        min_state=FlowState.TRAINED,
    ),
    ToolDescriptor(
        name="export_python",
        description="Export as Python module.",
        method_name="export_to_python",
        min_state=FlowState.TRAINED,
    ),
    ToolDescriptor(
        name="export_markdown",
        description="Export as Markdown.",
        method_name="export_to_markdown",
        min_state=FlowState.TRAINED,
    ),

    # --- Grupo G: Scoring y Champion-Challenger (Fase 6) ---
    ToolDescriptor(
        name="score_batch",
        description="Score a CSV file in chunks using the trained model.",
        method_name="score_batch",
        min_state=FlowState.TRAINED,
    ),
    ToolDescriptor(
        name="compare_champion_challenger",
        description="Compare champion and challenger models on an evaluation CSV.",
        method_name="compare_champion_challenger",
        min_state=FlowState.TRAINED,
    ),
)
