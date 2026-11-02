"""Batch scoring de modelos TreeGov (Fase 6.0.a).

El modulo aplica un ``TreeModel`` y su ``ImputationSpec`` congelado a un CSV
por lotes. No reentrena ni reajusta la imputacion, conserva las columnas crudas
y publica el CSV de salida de forma atomica.

Nota de contrato: ``ImputationSpec`` contiene las reglas (medias y modas), pero
no es un transformador. ``_apply_imputation`` reproduce sobre una copia el
``transform`` de ``TrainOnlyImputer`` sin modificar el DTO ni crear otro ajuste.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .imputation import ImputationSpec
from .tree_builder import TreeModel
from .types import PredictorType
from .validation import compute_oos_metrics, predict_leaf_assignment, predict_pd

__all__ = [
    "ScoringBundle",
    "BatchScoreSummary",
    "ChampionChallengerRequest",
    "ChampionChallengerResult",
    "score_batch_to_csv",
    "compare_champion_challenger",
]


@dataclass(frozen=True)
class ScoringBundle:
    """Contexto inmutable necesario para reproducir el scoring de un modelo."""

    model: TreeModel
    imputation: ImputationSpec
    predictor_spec: tuple[tuple[str, PredictorType], ...]
    target_classes: tuple
    target_class: int | str


@dataclass(frozen=True)
class BatchScoreSummary:
    """Resumen acotado de una ejecucion batch completada."""

    input_path: str
    output_path: str
    model_fingerprint: str
    unseen_policy: str
    chunksize: int
    total_rows: int
    scored_rows: int
    excluded_rows: int
    majority_fallback_rows: int
    imputation_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ChampionChallengerRequest:
    """Peticion inmutable de comparacion sobre un dataset etiquetado."""

    champion: ScoringBundle
    challenger: ScoringBundle
    dataset: pd.DataFrame
    target: str
    weight_col: str | None = None
    unseen_policy: str = "exclude"
    n_groups: int = 10


@dataclass(frozen=True)
class ChampionChallengerResult:
    """Metricas comparadas sobre la interseccion enrutable por ambos modelos."""

    champion_fingerprint: str
    challenger_fingerprint: str
    n_total: int
    n_common_routed: int
    champion_coverage: float
    challenger_coverage: float
    metrics: tuple[tuple[str, float | None, float | None, float | None], ...]


def _format_category(value: object) -> str:
    """Representa una categoria como literal legible, no como tupla tecnica."""
    if isinstance(value, np.generic):
        value = value.item()
    return repr(value)


def _generate_rule_path(model: TreeModel, leaf_id: int) -> str:
    """Devuelve el camino canonico raiz -> ``leaf_id`` en formato legible.

    Los umbrales usan ``<=``/``>``, los bins CHAID usan intervalos ``(a, b]``
    y los splits categoricos muestran solo el conjunto de la rama recorrida.
    """
    parent_by_id: dict[int, int] = {}
    for node in model.nodes:
        for child_id in node.child_ids:
            parent_by_id[child_id] = node.node_id

    path_ids = [int(leaf_id)]
    current = int(leaf_id)
    while current != model.root_id:
        if current not in parent_by_id:
            raise ValueError(
                f"[scoring] nodo {current} desconectado de la raiz {model.root_id}"
            )
        current = parent_by_id[current]
        path_ids.append(current)
    path_ids.reverse()

    conditions: list[str] = []
    for parent_id, child_id in zip(path_ids, path_ids[1:]):
        parent = model.nodes[parent_id]
        if parent.split is None:
            raise ValueError(f"[scoring] nodo interno {parent_id} sin SplitConfig")
        split = parent.split
        try:
            branch_index = parent.child_ids.index(child_id)
        except ValueError:
            raise ValueError(
                f"[scoring] nodo {child_id} no es hijo de {parent_id}"
            ) from None
        predictor = split.predictor

        if split.threshold is not None:
            threshold = str(float(split.threshold))
            if branch_index == 0:
                conditions.append(f"{predictor} <= {threshold}")
            elif branch_index == 1:
                conditions.append(f"{predictor} > {threshold}")
            else:
                raise ValueError(
                    f"[scoring] split umbral con rama invalida {branch_index}"
                )
            continue

        if split.bin_edges:
            if split.branches is None:
                raise ValueError("[scoring] split con bin_edges sin branches")
            branch = split.branches[branch_index]
            bins = sorted(int(str(label).split("_", 1)[1]) for label in branch)
            if not bins:
                raise ValueError("[scoring] rama CHAID sin bins")
            lo, hi = bins[0], bins[-1]
            edges = split.bin_edges
            if hi == len(edges):
                lower = str(float(edges[lo - 1]))
                conditions.append(f"{predictor} > {lower}")
            elif lo == 0:
                upper = str(float(edges[hi]))
                conditions.append(f"{predictor} <= {upper}")
            else:
                lower = str(float(edges[lo - 1]))
                upper = str(float(edges[hi]))
                conditions.append(f"{predictor} in ({lower}, {upper}]")
            continue

        if split.branches is not None:
            values = ", ".join(
                _format_category(value) for value in split.branches[branch_index]
            )
            conditions.append(f"{predictor} in {{{values}}}")
            continue

        raise ValueError(
            f"[scoring] split de {predictor!r} sin umbral, bins ni categorias"
        )

    conditions.append(f"Hoja {int(leaf_id)}")
    return " → ".join(conditions)


def _apply_imputation(spec: ImputationSpec, work_df: pd.DataFrame) -> pd.DataFrame:
    """Aplica medias/modos congeladas a una copia de trabajo, sin reajuste."""
    reglas = [(c, v) for c, v in spec.means.items()] + [
        (c, v) for c, v in spec.modes.items()
    ]
    for col, fill in reglas:
        if col not in work_df.columns:
            raise ValueError(f"[scoring] columna ausente en transform: {col!r}")
        work_df[col] = work_df[col].fillna(fill)
    return work_df


def score_batch_to_csv(
    bundle: ScoringBundle,
    input_csv: str,
    output_csv: str,
    *,
    unseen_policy: str = "exclude",
    chunksize: int = 50000,
    include_rules: bool = True,
) -> BatchScoreSummary:
    """Puntua ``input_csv`` por lotes y publica atomicamente ``output_csv``.

    ``scored_rows`` incluye las filas enviadas a la hoja mayoritaria;
    ``majority_fallback_rows`` identifica ese subconjunto. Por tanto,
    ``total_rows == scored_rows + excluded_rows``.
    """
    if unseen_policy not in ("error", "majority", "exclude"):
        raise ValueError(f"[scoring] unseen_policy invalida: {unseen_policy!r}")
    if not isinstance(chunksize, int) or isinstance(chunksize, bool) or chunksize <= 0:
        raise ValueError("[scoring] chunksize debe ser un entero positivo")

    input_path = Path(input_csv)
    output_path = Path(output_csv)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("[scoring] input_csv y output_csv deben ser archivos distintos")

    predictor_columns = tuple(col for col, _ in bundle.predictor_spec)
    imputation_totals = {col: 0 for col in predictor_columns}
    reserved_columns = {
        "treegov_row_id",
        "treegov_model_fingerprint",
        "treegov_leaf_id",
        "treegov_pd",
        "treegov_pd_vector",
        "treegov_rule_path",
        "treegov_route_status",
        "treegov_imputed_columns",
    }

    total_rows = 0
    scored_rows = 0
    excluded_rows = 0
    majority_fallback_rows = 0
    first_chunk = True
    tmp_path: str | None = None
    reader = None
    rule_cache: dict[int, str] = {}

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            mode="w",
            newline="",
            suffix=".tmp",
            dir=str(output_path.parent),
            encoding="utf-8",
        ) as tmp_file:
            tmp_path = tmp_file.name
            reader = pd.read_csv(input_csv, chunksize=chunksize)
            for chunk in reader:
                if first_chunk:
                    collisions = reserved_columns.intersection(chunk.columns)
                    if collisions:
                        raise ValueError(
                            "[scoring] columnas reservadas presentes en input_csv: "
                            f"{sorted(collisions)!r}"
                        )

                missing = [col for col in predictor_columns if col not in chunk.columns]
                if missing:
                    raise ValueError(
                        f"[scoring] columnas predictoras ausentes: {missing!r}"
                    )

                n_rows = len(chunk)
                work_df = chunk.copy()
                original_na = work_df.loc[:, predictor_columns].isna()
                work_df = _apply_imputation(bundle.imputation, work_df)
                imputed_mask = original_na & work_df.loc[:, predictor_columns].notna()
                for col in predictor_columns:
                    imputation_totals[col] += int(imputed_mask[col].sum())

                if unseen_policy == "majority":
                    base_assignment = predict_leaf_assignment(
                        bundle.model, work_df, unseen_policy="exclude"
                    )
                else:
                    base_assignment = None
                leaf_assignment = predict_leaf_assignment(
                    bundle.model, work_df, unseen_policy=unseen_policy
                )
                pd_vectors = predict_pd(
                    bundle.model, work_df, unseen_policy=unseen_policy
                )

                excluded_mask = leaf_assignment < 0
                if base_assignment is None:
                    fallback_mask = np.zeros(n_rows, dtype=bool)
                else:
                    fallback_mask = (base_assignment < 0) & ~excluded_mask

                out = chunk.copy()
                out["treegov_row_id"] = np.arange(
                    total_rows, total_rows + n_rows, dtype=np.int64
                )
                out["treegov_model_fingerprint"] = bundle.model.params_fingerprint
                out["treegov_leaf_id"] = [
                    int(leaf_id) if leaf_id >= 0 else "" for leaf_id in leaf_assignment
                ]
                out["treegov_pd"] = pd_vectors[:, 0]
                out["treegov_pd_vector"] = [
                    ""
                    if np.isnan(pd_vec[0])
                    else json.dumps([float(x) for x in pd_vec])
                    for pd_vec in pd_vectors
                ]

                if include_rules:
                    rule_paths: list[str] = []
                    for leaf_id in leaf_assignment:
                        leaf_id = int(leaf_id)
                        if leaf_id < 0:
                            rule_paths.append("")
                            continue
                        if leaf_id not in rule_cache:
                            rule_cache[leaf_id] = _generate_rule_path(
                                bundle.model, leaf_id
                            )
                        rule_paths.append(rule_cache[leaf_id])
                    out["treegov_rule_path"] = rule_paths
                else:
                    out["treegov_rule_path"] = ""

                statuses = np.full(n_rows, "SCORED", dtype=object)
                statuses[excluded_mask] = "EXCLUDED_UNSEEN"
                statuses[fallback_mask] = "MAJORITY_FALLBACK"
                out["treegov_route_status"] = statuses
                out["treegov_imputed_columns"] = [
                    json.dumps([
                        str(col)
                        for col, was_imputed in zip(predictor_columns, row_mask)
                        if bool(was_imputed)
                    ])
                    for row_mask in imputed_mask.to_numpy()
                ]

                out.to_csv(tmp_file, header=first_chunk, index=False)
                first_chunk = False
                total_rows += n_rows
                scored_rows += int((~excluded_mask).sum())
                excluded_rows += int(excluded_mask.sum())
                majority_fallback_rows += int(fallback_mask.sum())
            reader.close()

        os.replace(tmp_path, output_csv)
    except BaseException:
        if reader is not None:
            reader.close()
        if tmp_path is not None and os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return BatchScoreSummary(
        input_path=str(input_csv),
        output_path=str(output_csv),
        model_fingerprint=bundle.model.params_fingerprint,
        unseen_policy=unseen_policy,
        chunksize=chunksize,
        total_rows=total_rows,
        scored_rows=scored_rows,
        excluded_rows=excluded_rows,
        majority_fallback_rows=majority_fallback_rows,
        imputation_counts=tuple(
            (col, imputation_totals[col]) for col in predictor_columns
        ),
    )


def compare_champion_challenger(
    req: ChampionChallengerRequest,
) -> ChampionChallengerResult:
    """Compara campeon y retador sobre exactamente las mismas filas.

    Cada modelo aplica su propia imputacion congelada. Las coberturas se miden
    sobre toda la cohorte; las metricas, solo sobre la interseccion enrutable.
    """
    if req.target not in req.dataset.columns:
        raise ValueError(f"[scoring] target ausente en dataset: {req.target!r}")

    champ = req.champion
    chall = req.challenger
    y_original = req.dataset[req.target]
    if y_original.isna().any():
        raise ValueError("[scoring] target con NaN en Champion-Challenger")

    observed_classes = set(pd.unique(y_original))
    for role, bundle in (("champion", champ), ("challenger", chall)):
        if observed_classes != set(bundle.target_classes):
            raise ValueError(
                f"[scoring] clases del target no coinciden con {role}: "
                f"{sorted(observed_classes)!r} vs "
                f"{sorted(bundle.target_classes)!r}"
            )
    if champ.target_class != chall.target_class:
        raise ValueError(
            "[scoring] champion y challenger tienen clases de interes distintas"
        )
    if champ.target_class not in champ.target_classes:
        raise ValueError("[scoring] target_class fuera de target_classes")

    X = req.dataset.drop(columns=[req.target])
    if req.weight_col is not None:
        if req.weight_col not in req.dataset.columns:
            raise ValueError(
                f"[scoring] weight_col ausente en dataset: {req.weight_col!r}"
            )
        w = req.dataset[req.weight_col].to_numpy(dtype=float)
    else:
        w = None

    canonical_classes = (champ.target_class,) + tuple(
        sorted(c for c in champ.target_classes if c != champ.target_class)
    )
    class_to_internal = {value: idx for idx, value in enumerate(canonical_classes)}
    y_internal = np.array(
        [class_to_internal[value] for value in y_original], dtype=int
    )

    X_champ = _apply_imputation(champ.imputation, X.copy())
    X_chall = _apply_imputation(chall.imputation, X.copy())
    asign_champ = predict_leaf_assignment(
        champ.model, X_champ, unseen_policy=req.unseen_policy
    )
    asign_chall = predict_leaf_assignment(
        chall.model, X_chall, unseen_policy=req.unseen_policy
    )
    valid_mask = (asign_champ >= 0) & (asign_chall >= 0)
    n_common = int(valid_mask.sum())
    if n_common == 0:
        raise ValueError(
            "[scoring] no hay filas enrutables por champion y challenger"
        )

    X_champ_valid = X_champ.loc[valid_mask]
    X_chall_valid = X_chall.loc[valid_mask]
    y_valid = y_internal[valid_mask]
    w_valid = w[valid_mask] if w is not None else None

    pd_champ = predict_pd(champ.model, X_champ_valid)
    pd_chall = predict_pd(chall.model, X_chall_valid)
    n_classes = len(canonical_classes)
    if n_classes == 2:
        pd_champ_use = pd_champ[:, 0]
        pd_chall_use = pd_chall[:, 0]
        # La API binaria de compute_oos_metrics espera 1 para la clase de
        # interes; el orden canonico la ubica en el indice 0.
        y_eval = (y_valid == 0).astype(int)
    else:
        pd_champ_use = pd_champ
        pd_chall_use = pd_chall
        y_eval = y_valid

    m_champ = compute_oos_metrics(
        pd_champ_use, y_eval, n_groups=req.n_groups, weights=w_valid
    )
    m_chall = compute_oos_metrics(
        pd_chall_use, y_eval, n_groups=req.n_groups, weights=w_valid
    )

    def metric_row(
        name: str, champion_value: float | None, challenger_value: float | None
    ) -> tuple[str, float | None, float | None, float | None]:
        delta = (
            challenger_value - champion_value
            if champion_value is not None and challenger_value is not None
            else None
        )
        return name, champion_value, challenger_value, delta

    metrics = (
        metric_row("AUC", m_champ.auc, m_chall.auc),
        metric_row("Gini", m_champ.gini, m_chall.gini),
        metric_row("KS", m_champ.ks, m_chall.ks),
        metric_row("PR-AUC", m_champ.pr_auc, m_chall.pr_auc),
        metric_row("Brier", m_champ.brier, m_chall.brier),
        metric_row("Brier Skill", m_champ.brier_skill, m_chall.brier_skill),
    )
    return ChampionChallengerResult(
        champion_fingerprint=champ.model.params_fingerprint,
        challenger_fingerprint=chall.model.params_fingerprint,
        n_total=int(len(req.dataset)),
        n_common_routed=n_common,
        champion_coverage=float((asign_champ >= 0).mean()),
        challenger_coverage=float((asign_chall >= 0).mean()),
        metrics=metrics,
    )
