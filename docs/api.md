# TreeGov Public API

## API stability

The modules and symbols listed here are **public and stable** within
version 1.x. Any change breaks compatibility and requires a major version
bump. Symbols not listed (in particular, those starting with an
underscore) are internal and may change without notice.

## backend_v3.types

- `SplitConfig` (frozen dataclass) — common contract of the 4 engines.
  - `SplitConfig.bin_edges`: tuple[float, ...] (nuevo en Fase 3.10.b). Almacena los cortes numéricos para predictores continuos binned. Vacío por defecto.
- `TargetType`, `PredictorType`, `CutKind` (Enums).
- `GovernanceMode` (Enum): `BANKING` (Jeffreys + PD Floor, default) |
  `RESEARCH` (raw k/n, no floor).
  - Note on terminology: The Python Enum class is `GovernanceMode.BANKING`
    (kept for historical fingerprint compatibility and backward
    compatibility). However, in business and GUI documentation, this is
    referred to as 'Regulatory mode' (Modo Regulatorio) because it applies
    to banks, credit bureaus, and any regulated MRM environment. The
    fingerprint stores the string 'BANKING'.
- `MethodName`, `StatisticName` (Literal validation aliases of the contract).

## backend_v3.statistics

- `TestResult` (frozen dataclass): canonical output of a statistical test.
- `pearson_chi2(table) -> TestResult`
- `f_oneway(*groups) -> TestResult`
- `brown_forsythe(*groups) -> TestResult`
- `stirling_second_kind(c, r) -> int`
- `kass_multiplier(c, r, *, ordinal) -> int`
- `bonferroni_adjust(p, m) -> float` — evaluates `min(1.0, p * m)` in log space
  (`math.log(p) + math.log(m)`) so arbitrarily large integer multipliers
  (`m > 1.8e308`, e.g. high-cardinality Kass multipliers) never raise
  `OverflowError`, returning `0.0` for `p == 0.0`, `1.0` on saturation, and
  accurate finite values even for subnormal `p` (Block 2E, 20/11/2026;
  `design_decisions.md` §31).

## backend_v3.chaid_engine

- `ChaidEngine`, `MergeDiagnostics`, `MergeStep`
  - Since Block 2E (20/11/2026): rejects non-finite `±inf` in continuous
    predictors and continuous targets, centers continuous targets before
    accumulating sufficient statistics (avoiding catastrophic cancellation),
    handles constant `CONTINUOUS` predictors cleanly under `exhaustive=True`,
    and restricts Exhaustive CHAID final selection to Cochran-valid steps
    whenever at least one exists (while keeping the full merge history in
    `diagnostics.exhaustive_steps`).

## backend_v3.crt_engine

- `CrtEngine`, `SurrogateSplit`
  - Since Block 2E (20/11/2026): Gini evaluation normalizes class probabilities
    before squaring and avoids subtraction cancellation under extreme weight
    magnitudes or weight ratios (reverse cumulative sums / direct complement),
    regression centers targets (`y - mean`) before variance evaluation, and
    `surrogate_splits` rejects `±inf` in numeric primary/candidate predictors.

## backend_v3.quest_engine

- `QuestEngine(*, alpha=0.05, max_exhaustive_cardinality=10,
  bonferroni_family=2, nominal_high_card="rate",
  qda_root_restriction=True)`, `QuestSelection`
  - `bonferroni_family` (int ≥ 1, default 2) — family multiplier in the
    Stage-1 Bonferroni threshold `alpha / (family * J)`. Default 2
    controls the FWER over the two test families (means + variance);
    `1` reproduces the canonical Loh & Shih (1997) single-family
    threshold. See `design_decisions.md` §4.1.
  - `nominal_high_card` (str, default "rate") — strategy for nominal
    predictors with K > `max_exhaustive_cardinality`. `"rate"` uses the
    supervised-rate heuristic (Breiman/C&RT style); `"dummies_lda"`
    (canonical Loh & Shih) is reserved for Phase 3.4 and raises
    `NotImplementedError` if requested. See `design_decisions.md` §4.2.
  - `qda_root_restriction` (bool, default True) — restricts the QDA
    cutpoint (and linear LDA cutpoint) to the inter-means interval. `False`
    accepts any real root (canonical mode), tie-broken by closeness to the
    weighted mean. See `design_decisions.md` §4.3.
  - Numerical & Stage-1 guarantees (Block 2E, 20/11/2026; `design_decisions.md`
    §13.4 & §31): weighted QDA variance uses Kish's unbiased reliability-weight
    divisor `W_k - sum(w_i^2) / W_k` (strictly scale-invariant under
    `w -> c * w`, safe for normalized weights `sum(w) = 1`, exact `n_k - 1`
    parity under uniform weights); QDA roots are solved via Citardauq's stable
    quadratic formula; all returned thresholds are bounded to `[min(x), max(x))`
    so child splits are never empty; and Stage 1 prioritizes finite significant
    statistics so a degenerate predictor with `F = inf` never hijacks valid
    finite predictors (preserving the `"no representable"` warning + `None`
    return only when no finite significant predictor exists).

## backend_v3.imputation

- `TrainOnlyImputer`, `ImputationSpec`
  - Since Block 2E (20/11/2026): both `fit()` and `transform()` reject
    non-finite values (`±inf`) in numeric columns with `ValueError`
    (`design_decisions.md` §31).

## backend_v3.tree_builder

- `BASEL_PD_FLOOR_MIN: float = 0.0005` — minimum Basel III CRE 32.4 PD floor
  required for `BANKING` governance classification (Block 2B, 20/11/2026).
- `classify_governance_mode(apply_jeffreys: bool, pd_floor: float | None) -> str` —
  single source of truth for effective governance mode classification
  (`"BANKING"` iff `apply_jeffreys is True` and `pd_floor >= BASEL_PD_FLOOR_MIN`;
  `"RESEARCH"` iff `apply_jeffreys is False` and `pd_floor is None`;
  `"CUSTOM"` otherwise, including `0.0` or legacy `0.0003`).
- `TreeBuilder`, `TreeModel`, `TreeNode`
  - `TreeNode.gini_impurity -> float` (read-only property, Block 2G,
    20/11/2026): empirical node Gini impurity
    $I_G(t) = 1 - \sum_{k=0}^{K-1} (n_k / n)^2$ computed from raw counts
    (`n_events / n`, Breiman et al. 1984 §4.3; `0.0` if `n <= 0`), avoiding
    Jeffreys/floor distortion and keeping impurity calculations out of
    `frontend_v3` (rendered in `TreeView` as `Impurity (I_G)` to prevent
    terminological collision with discriminatory Gini `2*AUC - 1`).
- `TreeBuilder(..., validation_scheme="holdout", cv_k=None)` — kwargs
  keyword-only nuevos (Fase 2.1.b). `validation_scheme` y `cv_k`
  entran en `params_fingerprint` SOLO si difieren del default
  ("holdout" / None). Los fingerprints holdout existentes no cambian.
  Since Block 2B, `pd_floor` must be `None` or a finite float in `[0.0, 0.5)`
  (booleans and non-finite values raise `ValueError`).

## backend_v3.exporters

- `export_to_sql(model: TreeModel, imputer: ImputationSpec, *, unseen_policy: str = "exclude", node_id: int | None = None) -> str` —
  ANSI SQL with nested `CASE WHEN` and `COALESCE` for training-time
  imputation; the fingerprint rides as a leading comment. (Phase
  4.0.a, 31/10/2026.)
- `export_to_python(model: TreeModel, imputer: ImputationSpec, *, unseen_policy: str = "exclude", node_id: int | None = None) -> str` —
  dependency-free Python module (`predict(row: dict) -> float | None`),
  same fingerprint header. (Phase 4.0.a, 31/10/2026.)
- `export_to_markdown(model: TreeModel, *, unseen_policy: str = "exclude", node_id: int | None = None) -> str` — human-readable
  Markdown report (fingerprint + method + nested decision rules).
  Takes only the model: no imputation is needed because the
  artefact is descriptive, not scoring. (Phase 4.0.b, 01/11/2026.)

Since Phase 3.12.a, all three accept the additive keyword-only `node_id`.
`None` (default) preserves the previous whole-tree output. An explicit id
exports that node and its descendants as a new root, without prepending the
path from the original root; an unknown id raises `KeyError`. The global
`unseen_policy` contract is unchanged.

Since Phase 4.0.1.a, `unseen_policy="exclude"` leaves unseen categorical
rows unscored (`NULL` in SQL, `None` in Python).

Since Phase 5.0.c, all three exporters route CHAID continuous splits by
their consolidated `SplitConfig.branches`, not by individual bins: each
branch yields a condition from its real merged-bin interval (H-5.0.c-1;
`docs/design_decisions.md` §16.4).

Since Phase 4.0.1.b, `unseen_policy` accepts `"error"`, `"exclude"`
(default), and `"majority"`. In `"error"` mode, SQL emits `ELSE 1/0`:
fatal on PostgreSQL/SQL Server/Oracle, but `NULL` with a warning on
MySQL/SQLite, where the receiver must filter the row. Python raises
`ValueError` identifying the predictor and the unseen/missing value. In
`"majority"` mode, the fallback is the majority leaf's `pd_final[0]`,
selected via `backend_v3.validation.select_majority_leaf` (maximum physical
`n`, deterministic minimum `node_id` tie-break). The generated Python
functions are annotated `float` in `"error"` and `"majority"` modes; they
remain `float | None` in `"exclude"` mode.

Since Block 2A (20/11/2026; `docs/design_decisions.md` §27), the exporters
enforce strict scoring parity and hardening:
- ANSI SQL double-quoted identifiers (`"..."`) on every predictor column and
  sanitized single-line header comments.
- Preserved numeric vs. text scalar types in categorical `IN (...)` / Python
  tuples and imputation modes.
- Dependency-free `None` and `NaN` handling (`val is None or val != val`) in
  Python imputation and numeric split guards, plus explicit `WHEN >` and
  policy-governed `ELSE` on merged CHAID SQL splits so `NULL` never falls
  into the top bin.
- Fail-fast `ValueError` on non-finite constants (`NaN`/`±inf`), booleans in
  numeric contexts, and cycles in `child_ids`; f-string-free `ValueError`
  emission in Python `"error"` mode.
- Explicit multiclass transparency (`len(model.class_labels) > 2`): SQL and
  Python add a header comment documenting that class index 0 is exported and
  classes `1..K-1` are omitted, while Markdown adds a header note and renders
  the full class probability vector on every leaf (binary `K == 2` output
  contract unchanged).

## backend_v3.scoring

Phase 6.0 public scoring contracts:

- `ScoringBundle` (frozen dataclass) — immutable scoring context containing a
  `TreeModel`, its training-fitted `ImputationSpec`, predictor spec, original
  target classes and class of interest.
- `BatchScoreSummary` (frozen dataclass) — bounded batch metadata: paths,
  fingerprint, policy, chunksize, row/fallback counts and per-predictor
  imputation counts.
- `score_batch_to_csv(bundle, input_csv, output_csv, *, unseen_policy="exclude",
  chunksize=50000, include_rules=True) -> BatchScoreSummary` — scores a CSV in
  chunks, preserves input rows/order and publishes atomically. An existing
  output raises `FileExistsError` before the temporary file is created; input
  and output must be different paths.
- `ChampionChallengerRequest` and `ChampionChallengerResult` (frozen
  dataclasses) — comparison inputs/outputs, including both bundles, common
  routed count, coverage and six metric rows `(name, champion, challenger,
  delta)`.
- `compare_champion_challenger(req) -> ChampionChallengerResult` — applies each
  bundle's frozen imputation and computes AUC, Gini, KS, PR-AUC, Brier and
  Brier Skill on the intersection routed by both models. Missing metric values
  and their deltas remain `None`; no champion promotion is performed.

## backend_v3.ecl

Phase 7.0 public IFRS 9 / ECL contracts (hardened in Block 2C, 20/11/2026):

- `ECLConfig(eir: float | None = None)` (frozen dataclass) — immutable
  configuration for the simplified ECL calculation. `eir=None` disables
  discounting; otherwise `eir` must be a non-boolean finite float in annual
  decimal scale with **`eir >= 0.0`** (negative rates are rejected to prevent
  discount factors `> 1`), defining the v1 one-period discount factor
  `1 / (1 + eir)`.
- `ECLRow` (frozen dataclass) — immutable exposure-level result with fields
  `exposure_id`, `stage`, `pd_12m`, `pd_lifetime`, `lgd`, `ead`, `ecl_12m`,
  `ecl_lifetime`, and `ecl_applicable` (`ecl_12m` for Stage 1; `ecl_lifetime`
  for Stages 2 and 3).
- `ECLSummary` (frozen dataclass) — immutable portfolio summary with fields
  `total_ecl_12m`, `total_ecl_lifetime`, `stage_counts` (Stage 1, Stage 2,
  Stage 3), and `total_ecl_staged` (`math.fsum` of `ecl_applicable` across
  exposures: Stage 1 at 12-month horizon plus Stages 2 and 3 at lifetime
  horizon per IFRS 9 §5.5).
- `calculate_ecl(df, pd_column, config) -> tuple[ECLSummary, list[ECLRow]]` —
  validates input types (`pd.DataFrame`, non-empty, `ECLConfig`), non-empty
  `pd_column` not colliding with reserved input columns (`exposure_id`, `ead`,
  `lgd`, `days_past_due`, `pd_initial`, `is_default`), rejects boolean numeric
  columns and `pd_lifetime + 1e-12 < pd_12m`, assigns Stages 1/2/3 with
  deterministic rules, forces **`pd_12m = 1.0` and `pd_lifetime = 1.0` for
  Stage 3** (credit-impaired / default per IFRS 9 §5.5 & Appendix A), and
  computes discounted 12-month, lifetime and staged applicable ECL.
  `pd_lifetime` is optional; when absent, the 12-month PD is reused with an
  explicit `UserWarning`. The input DataFrame is not mutated. This is a
  single-scenario, single-period simplification anchored to IFRS 9 §5.5, not a
  full accounting-compliance engine.

## backend_v3.session_state

- `FlowState` (Enum), `SessionState`, `Session`
- `Session.active_tree -> TreeModel | None` — read-only property returning the
  active model (`state.pruned_tree` when cost-complexity pruning has been
  applied, otherwise `state.tree`; Block 2B, 20/11/2026). All downstream
  analytical consumers (`get_gains_table`, `get_classification_matrix`,
  `evaluate_oos`, `evaluate_oot`, `get_summary`, `get_node_cases`,
  `score_batch`, `compare_champion_challenger`, `export_to_*`, `get_rules`,
  `intervene_node`) operate on `active_tree`.
- Nuevos campos de `SessionState` (Fase 2.1.b):
  - `validation_scheme: str = "holdout"`
  - `cv_k: int | None = None`
  - `cv_folds: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...] = ()`
- `Session.describe_dataset() -> (columns, types)` — read-only profile of
  the loaded dataset (types as `PredictorType.name` strings; Phase 2.1).
- `Session.get_data_preview(n_rows=50) -> dict` — read-only raw preview
  of the loaded CSV (no imputation, no encoding, no split):
  `{"columns": list[str], "rows": list[tuple], "n_total": int,
  "truncated": bool}`. Every cell is a native Python type
  (`int`/`float`/`str`/`bool`) and missing CSV values are returned as
  `None` — no numpy/pandas scalars, JSON-serializable. Without a loaded
  dataset it returns the empty dict (`n_total=0`, `truncated=False`)
  instead of raising `RuntimeError` — conscious divergence from the
  `describe_*` family, see `docs/design_decisions.md` §18.7. (Phase
  3.11.b.1).
- `Session.get_rules(format="markdown", node_id=None,
  unseen_policy="exclude") -> str | None` — read-only rules facade (Phase
  3.12.a). `format` accepts `"markdown"`, `"sql"` or `"python"`; other
  values raise `ValueError`. Returns `None` without a trained model.
  `node_id=None` is byte-equivalent to the corresponding exporter; an
  explicit id exports only that node and its descendants as a new root.
  SQL/Python require the training imputer cache.
- `Session.get_summary() -> dict | None` — read-only model-act DTO (Phase
  3.12.b), `None` without a trained model. Top-level keys are `model`,
  `dataset`, `partition`, `governance`, `validation`, `manual_overrides`
  and `event_log`; all values are native Python types. Validation reuses
  the existing OOS/OOT and CV reports. `model.governance_mode` records the
  effective `BANKING`/`RESEARCH`/`CUSTOM` mode. In CV, `partition.n_train`
  is the population-approved row count and `partition.n_test` is 0.
- `Session.get_node_cases(node_id, *, partition="train", n_rows=50) -> dict`
  — read-only raw cases routed to the requested node or any descendant
  (Phase 3.12.c). Returns the same native DTO shape as `get_data_preview`.
  `partition` accepts `"train"`, `"oos"`, `"oot"` and `"all"`. Displayed
  cells come from the raw CSV (`None` for missing values), while routing
  uses the partition's imputed matrix so missing predictors do not silently
  discard train/OOS/OOT rows. `"all"` routes the raw development frame with
  `unseen_policy="exclude"`. An empty/unloaded partition returns columns,
  no rows, `n_total=0` and `truncated=False`. No model or an unknown node
  raises `ValueError`; an unknown partition also raises `ValueError`.
- `Session.fix_spec(target, spec=None, *, predictors=None, target_class,
  class_labels, weight_col=None, population_col=None,
  population_ok_values=None)` — optional predictor subset filter applied
  inside the backend (Phase 2.1). `target_class` and `class_labels` are
  **mandatory** as of Phase 3.1: they name the class of interest and the
  label for each target class (see `docs/3.1_design_multiclass.md` §1bis).
  `weight_col` (Phase 3.2) declares the sample-weight column;
  `population_col` + `population_ok_values` (Phase 3.3) declare the
  opt-in population filter.
- `Session.train(engine, *, target_type=None, max_depth=4, min_child_size=50,
  min_child_weight=None, pd_floor=0.0005, apply_jeffreys=True)` —
  `engine` accepts an engine instance or its name ("CHAID" |
  "CHAID_EXHAUSTIVE" | "CRT" | "QUEST"); `pd_floor=None` +
  `apply_jeffreys=False` yields Research mode (Phase 2.1). Since Block 2D
  (20/11/2026), `target_type: TargetType | str | None = None` auto-resolves
  from `len(state.target_classes)` when `None` (`TargetType.BINARY` for
  `K == 2`, `TargetType.CATEGORICAL` for `K > 2`), accepts strict `"binary"`
  or `"categorical"` strings (case-insensitive; any other string/type raises
  `ValueError`), preserves fail-fast `TargetType` pass-through to
  `TreeBuilder`, and stores the resolved `TargetType` in
  `_last_train_params`. Multiclass targets (K > 2, including string targets
  such as `"Low"/"Mid"/"High"` or `"01"/"02"/"A3"` and negative integers) are
  supported end to end across `partition`, CV, `train`, `evaluate_oos`,
  `get_gains_table`, `get_classification_matrix`, `load_oot` and
  `evaluate_oot`. `min_child_weight` (Phase 3.7.c) is the weighted-mass
  floor per branch, complementary to `min_child_size` (which measures
  physical rows); it is only meaningful when a `weight_col` was declared
  in `fix_spec`. `None` (default) disables the check.
- `Session.get_gains_table(*, partition, by, n_buckets, tie, seed)` —
  flat DTO of a gains table for a routed partition (Phase 2.4.c.1).
  Supports K > 2 since Phase 3.5; since Block 2D (20/11/2026), translates
  multiclass targets via `_translate_y_to_internal` before calling
  `build_gains_table` so `n_bad` and index 0 always correspond to
  `target_class` (including string targets; binary `K == 2` unchanged).
- `Session.get_classification_matrix(*, partition, threshold)` — flat
  DTO of a classification matrix (Phase 2.4.c.1). Supports K > 2 since
  Phase 3.5.c and propagates `tree.class_labels` in canonical order since
  Block 2D (20/11/2026; see the extended entry below).
- `Session.reset_to_data_loaded()` — back to DATA_LOADED keeping the
  cached DataFrame (no CSV re-read; Phase 2.1).
- `Session.partition(train_frac=0.7, seed=42, *, scheme="holdout", k=5)`
  — partición del dataset (Fase 2.1.b). `scheme="holdout"` (default)
  es el comportamiento histórico. `scheme="cv"` aplica k-fold
  estratificado: `_X_train` = 100% de los datos, `_X_test` = None,
  `cv_folds` se pobla en SessionState. En CV, el modelo final se
  entrena con el 100%.
- `Session.get_cv_report() -> dict | None` — DTO de solo lectura del
  último informe de CV calculado. None si no hay CV. Estructura:
  `{"scheme": "cv", "k": int, "metrics_mean": dict, "metrics_std":
  dict, "metrics_per_fold": list[dict]}`.
- `Session.get_prune_sequence() -> list[dict[str, Any]]` — Read-only method that returns the cost-complexity pruning sequence for the trained model (`state.tree`). Each dictionary contains `alpha` (float), `n_leaves` (int), and `r_subtree` (float). Returns an empty list if the model has no internal nodes. (Phase 3.9).
- `Session.prune(alpha: float) -> SessionState` — applies cost-complexity
  pruning idempotently from the original `state.tree`, stores the result in
  `state.pruned_tree` (activating it via `Session.active_tree`), and
  invalidates stale metrics (`oos_metrics=None`, `oot_report=None`,
  `_cv_report=None`; Block 2B, 20/11/2026).
- `Session.load_oot(csv_path, *, time_col=None) -> SessionState` — atomically
  validates and loads an external OOT cohort. Rejects empty cohorts after
  population filtering, `NaN` or unseen target classes outside
  `state.target_classes` (preserving string/non-int multiclass dtypes since
  Block 2D), non-finite/non-positive OOT weights, and any missing /
  `NaT` values in `time_col` (in development or OOT) before checking
  `t_oot.min() > t_dev.max()`. Failed calls leave `FlowState` and OOT caches
  untouched (Block 2B/2D, 20/11/2026).
- `Session.get_univariate_trees(max_depth=3) -> list[dict]` — read-only
  batch univariate trees (Phase 3.11.c.1): trains one depth-`max_depth`
  tree per predictor in the spec using the SAME engine as the trained
  model and BANKING governance, evaluates it on the test partition (same
  path as `evaluate_oos`) and returns one flat dict per predictor with
  keys `predictor` (str), `gini` (float), `ks` (float) and `cut_points`
  (list[tuple[str, float]] of internal-node thresholds). A failing
  predictor degrades to `0.0` metrics with a WARNING in the log.
  Requires a trained model (`ValueError` otherwise).
- `Session.score_batch(csv_path, output_path, *, unseen_policy="exclude",
  chunksize=50000, include_rules=True) -> dict[str, Any]` — public Phase 6
  facade over `backend_v3.scoring.score_batch_to_csv`. Builds a `ScoringBundle`
  from the active tree and training imputer, writes the scored CSV and returns
  `BatchScoreSummary` as a plain dict. Requires a trained model and a populated
  imputer cache; does not change `FlowState` or the model. Existing output paths
  are rejected without being overwritten.
- `Session.compare_champion_challenger(evaluation_csv, *,
  challenger_engine=None, challenger_params=None, target=None, weight_col=None,
  unseen_policy="exclude", n_groups=10) -> dict[str, Any]` — trains an isolated
  challenger with a new engine instance and the cloned training parameters plus
  explicit overrides, then evaluates champion and challenger on the common
  routed population. Returns `ChampionChallengerResult` as a plain dict with
  both fingerprints, coverage and metric deltas. The champion, its fingerprint,
  training caches and session state remain unchanged; no promotion is applied.
- `Session.calculate_ecl(csv_path, *, pd_column="pd_current", eir=None) -> dict[str, Any]` —
  Phase 7 facade over `backend_v3.ecl.calculate_ecl`. Requires a trained model,
  reads the exposure CSV and returns only the bounded summary with
  `total_ecl_12m`, `total_ecl_lifetime`, `stage_counts` and `total_ecl_staged`
  (Block 2C, 20/11/2026). The per-exposure detail is discarded; `FlowState`,
  the tree and the session event log remain unchanged.
- `Session.export_to_sql(*, unseen_policy: str = "exclude") -> str | None` — wrapper of
  `backend_v3.exporters.export_to_sql` using the trained tree and
  the training-partition imputer. `None` without a trained model;
  `RuntimeError` if the model exists but the imputer cache is empty
  (defensive guard for a broken invariant). (Phase 4.0.c,
  01/11/2026.)
- `Session.export_to_python(*, unseen_policy: str = "exclude") -> str | None` — wrapper of
  `backend_v3.exporters.export_to_python`. Same contract as
  `export_to_sql`. (Phase 4.0.c, 01/11/2026.)
- `Session.export_to_markdown(*, unseen_policy: str = "exclude") -> str | None` — wrapper of
  `backend_v3.exporters.export_to_markdown`. `None` without a
  trained model; does not require the imputer (the Markdown
  artefact is descriptive, not scoring). (Phase 4.0.c,
  01/11/2026.)
- `Session.intervene_node(node_id, action, payload=None) -> SessionState` —
  manual intervention entry point (Phase 3.11.d.1). Implemented action:
  `"prune_branch"` (the node becomes a leaf with `leaf_reason="podado"`,
  its descendants are dropped and the tree is BFS-reindexed via
  `_reindex_tree`, preserving the `node_id == index` invariant). The
  original frozen `TreeModel` is never mutated: a new one is built with
  the fingerprint suffixed `-iN` (N = override counter; renamed from
  `-pN` on 25/10/2026 to avoid collision with the pruning suffix
  `-p{alpha}` of `pruning.py`) and the action
  is appended to the immutable `SessionState.manual_overrides` log
  `(timestamp, node_id, action, params_str, fp_before, fp_after)`
  (see `docs/design_decisions.md` §18.9). Requires a trained model
  (`ValueError` otherwise; also if `node_id` is a `bool`, does not exist, or
  is already a leaf). Since Block 2B (20/11/2026), operates on
  `Session.active_tree`, remaps `parent_id` during BFS re-indexing so
  non-root internal nodes in trees of depth ≥ 3 re-index cleanly, and
  invalidates stale artifacts (`pruned_tree=None`, `prune_alpha=None`,
  `oos_metrics=None`, `oot_report=None`, `_cv_report=None`). Unimplemented
  actions raise `NotImplementedError`.
- `Session.fix_spec(..., cost_matrix=None)` — Phase 3.11.c.3 adds the
  keyword-only `cost_matrix` parameter: an immutable N×N
  misclassification-cost matrix (rows: actual class; columns: predicted
  class), stored in `SessionState.cost_matrix` as a tuple of tuples.
  Validated BEFORE the state transition (square with N = number of
  target classes, diagonal fixed at 0, finite values ≥ 0). The empty
  tuple `()` means "no costs" (default). It is NOT part of
  `params_fingerprint` in this phase — the growth engine does not use
  it (see `docs/design_decisions.md` §18.8).
- `Session.evaluate_oos(*, n_groups=10)` — evalúa el modelo sobre la
  partición de test. Soporta K > 2 desde 3.5.c. En modo `scheme="cv"`
  (Fase 2.1.b), calcula métricas sobre los k folds de `cv_folds`
  (entrenando un modelo temporal por fold) y devuelve un dict con
  `scheme`, `k`, `metrics_mean`, `metrics_std`, `metrics_per_fold`.
  `SessionState.oos_metrics` queda None en modo CV.
- `Session.evaluate_oot(*, n_groups=10, weight_oot=True)` — supports
  K > 2 since Phase 3.5.c. Same label translation. Since Block 2F
  (20/11/2026): works under `scheme="cv"` without prior `oos_metrics`
  (or after `prune()`), setting `gini_oos=None` and
  `alert_oos="UNDETERMINED"` when no holdout partition exists (when
  holdout exists, computes `gini_oos` over routable rows via
  `unseen_policy="exclude"`); returns `drop=None` (`"UNDETERMINED"`)
  with a warning whenever `gini_train <= 0.0` to prevent sign inversion.
- `Session.get_classification_matrix(*, partition="oos",
  threshold=0.5)` — supports K > 2 since Phase 3.5.c. With K = 2 it
  calls the binary function with the threshold; with K > 2 it calls
  `build_classification_matrix_multiclass` (argmax assignment,
  threshold ignored and recorded as NaN).

## backend_v3.validation

- `OOSMetrics` (frozen dataclass) — multiclass-aware metrics
  container. Fields `hl_stat`, `hl_df`, `hl_p` are Optional as of
  Phase 3.5.a (None in multiclass mode); `hl_groups` remains int.
  Three new fields since Phase 3.5.a, all with empty defaults:
  `ks_pairs: tuple[tuple[int, int, float], ...]`,
  `auc_pairs: tuple[tuple[int, int, float], ...]`,
  `roc_per_class: tuple[tuple[tuple[float, float, float], ...], ...]`.
- `select_majority_leaf(model: TreeModel) -> TreeNode` — single source of
  truth for `unseen_policy="majority"` (Block 2A, 20/11/2026): selects the
  leaf with maximum physical `n` (not weighted) and breaks ties
  deterministically by minimum `node_id`; raises `ValueError` if the model
  contains no leaves.
- `predict_pd(model, X, *, unseen_policy="error")` — returns a 2D
  array of shape (n_rows, K) since Phase 3.1.
- `predict_leaf_assignment(model, X, *, unseen_policy="error")`.
- `compute_oos_metrics(p, y, *, n_groups=10, weights=None)` — the
  input `p` accepts two forms (Phase 3.5.a, decision D15): 1D
  (classic binary path) or 2D with shape (n, K) for multiclass. For
  K = 2, the 2D path reduces internally to column 0 and executes
  the binary path; the caller must pass `y_2d = 1 - y_1d` to
  preserve the uniform "column c ↔ label c" contract. For K > 2,
  `y` must be a 1D array of labels in {0, 1, ..., K-1}. Since Block 2F
  (20/11/2026): strictly validates `p` (non-empty, finite, in `[0, 1]`)
  and `y` prior to integer casting (rejects `NaN`, `None`, `±inf`,
  booleans, strings and fractional floats; binary 1D requires `y` in
  `{0, 1}`); binary Hosmer-Lemeshow uses tie-preserving grouping
  (invariant to row order), external OOS degrees of freedom
  `hl_df = hl_groups = g_eff` (Hosmer, Lemeshow & Sturdivant 2013,
  §5.2.2) and `_HL_EPS = 1e-6` with warning on extreme clipping.

## backend_v3.reporting

- `build_oos_oot_report(st)` — flat OOS/OOT DTO (Phase 2.3.d). Since
  Block 2G (20/11/2026), when `st.oot_report is not None`, precomputes
  `oot["csi_worst_flag"]` in the backend (`None` if `csi` is empty,
  `"UNDETERMINED"` if any CSI value is non-finite, otherwise the `.flag`
  of the covariate with maximum `csi`), eliminating frontend aggregation.
- `GainsRow` (frozen dataclass) — one gains-table line. Extended in
  Phase 3.5.b with 6 additive fields (`n_per_class`, `n_per_class_cum`,
  `n_per_class_decum`, and the weighted siblings `w_n_per_class`,
  `w_n_per_class_cum`, `w_n_per_class_decum`; empty in the binary path)
  and in Block 2G (20/11/2026) with 2 additive cumulative-share fields
  defaulting to `0.0`: `pop_cum_pct` (`n_cum / n_total`) and
  `bad_cum_pct` (`n_bad_cum / n_bad` if `n_bad > 0` else `0.0`),
  populated by `build_gains_table()` for direct consumption by gains
  charts without frontend arithmetic.
- `GainsTableResult` (frozen dataclass) — extended in Phase 3.5.b
  with 5 additive fields: `class_labels`, `n_per_class_global`,
  `w_n_per_class_global`, `ks_pairs`, `auc_pairs`. Empty in the binary
  path.
- `build_gains_table(model, leaf_assignment, y, *, by="leaf",
  n_buckets=10, tie="preserve", seed=None, weights=None)` — dispatch
  by K since Phase 3.5.b. K=2 keeps the pre-3.5.b path (weight-aware
  via `validation._pair_auc_ks`); K>2 uses
  `validation.compute_oos_metrics` with adaptive `n_groups =
  min(10, max(3, n // 5))` and returns ks/auc/gini = None when
  n < 15 (D20).
- `ClassificationMatrix` (frozen dataclass) — extended in Phase 3.5.b
  with 12 additive fields (`confusion_matrix`, `n_per_class`,
  `precision_per_class`, `recall_per_class`, `f1_per_class`, `accuracy`,
  and weighted siblings) and in Block 2D (20/11/2026) with additive
  `class_labels: tuple[str, ...] = ()` (empty in `K == 2`, canonical class
  labels in `K > 2`). `accuracy` is populated in both K=2 and K>2. The
  binary fields (`tp`, `tn`, `fp`, `fn`, `precision`, `recall`, `f1`,
  `bad_capture_rate`, `n_good`, `n_bad`) keep their meaning in K>2 by
  grouping the class of interest (index 0) as positive and the rest as
  negative (D19).
- `build_classification_matrix(leaf_assignment, y, pd_per_leaf, *,
  threshold=0.5, weights=None)` — binary, unchanged signature.
  Populates `accuracy` since Phase 3.5.b and `w_accuracy` since
  Block 2F (20/11/2026, exact parity `w_accuracy == accuracy` when
  `weights=None`); rejects `NaN`/non-finite/non-integer values in
  `leaf_assignment` and `y`, and non-finite or out-of-`[0, 1]`
  probabilities in `pd_per_leaf`.
- `build_classification_matrix_multiclass(leaf_assignment, y,
  pd_per_leaf: dict[int, tuple[float, ...]], *, weights=None,
  class_labels=())` — new in Phase 3.5.b; extended in Block 2D (20/11/2026)
  with optional keyword-only `class_labels: tuple[str, ...] = ()` (validated
  for `len(class_labels) == K` when non-empty). Argmax assignment, K×K
  matrix, per-class metrics, accuracy, binary legacy fields from class 0 vs
  rest. `threshold` records NaN. Since Block 2F (20/11/2026): validates
  all `pd_per_leaf` probability components are finite in `[0, 1]` and
  rejects `NaN`/non-integer entries in `leaf_assignment` and `y`.

## backend_v3.stability

- `PSIReport`, `CSIReport`, `GiniDropReport`, `OOTReport`.
- `StabilityMonitor(*, eps=1e-4, renormalize=False)` (`leaf_psi` /
  `covariate_csi` / `report`). Since Block 2F (20/11/2026): validates
  `eps` in `(0, 0.5)` finite (no booleans) and forwards `self.eps` to
  `psi_index`; `leaf_psi` is scale-invariant for OOT weight sums `< 1`
  and rejects empty/zero-mass cohorts; `covariate_csi` uses `(a, b]`
  decile bins (`right=True`), handles constant and all-`NaN` continuous
  predictors, tracks missing values in an explicit `"<MISSING>"` bin
  for both continuous and nominal predictors, and rejects `±inf`.
- `psi_index(expected, actual, *, eps=1e-4, renormalize=False)`,
  `traffic_light(value)`, `gini_drop_alert(drop)`.
  - `eps` (float, default `1e-4`, Block 2F) — finite clip floor in
    `(0, 0.5)` applied before the logarithm (booleans rejected).
  - `renormalize` (bool, default False) — whether to renormalize both
    distributions after the ε-clip. Default `False` preserves the
    signal of vanishing bins (TreeGov convention); `True` is the
    canonical renormalized variant. See `design_decisions.md` §7.4.

## backend_v3.pruning

- `Pruner`, `PruneStep`
  *(Note: since Phase 3.9, pruning is interactive and weighted — wired into the GUI via `PruneDialog` and exposed via `Session.get_prune_sequence()`.)*

## backend_v3.splitting

- `stratified_split(y, train_frac, seed, log=None, *, weights=None)` —
  holdout estratificado Hamilton-Hare (desde Bloque 2F, 20/11/2026:
  rechaza `NaN`/ausentes en `y` con `ValueError`).
- `stratified_kfold(y, k, seed, log=None) -> list[tuple[np.ndarray, np.ndarray]]`
  — k-fold estratificado (Fase 2.1.b). Devuelve k pares
  (train_idx, val_idx) disjuntos y deterministas. Misma proporción
  de clase por fold (desde Bloque 2F: rechaza `NaN`/ausentes en `y`).

## backend_v3.profiling

- `infer_spec(df, target, log=None)`, `MAX_ORDINAL_CATS`

## backend_v3.log_config

- `setup_logging(log_path, level) -> Logger`
- `get_logger(name) -> Logger`

## backend_v3.import_guard

- `install_import_guard()`, `is_installed()`
  - White-box meta-path blocker (`_BANNED_ROOTS`): blocks `sklearn`,
    `scikit-learn`, `scikit_learn`, `statsmodels`, `xgboost`, `lightgbm`,
    `catboost` and, since Block 2G (20/11/2026), also `torch`,
    `optbinning`, `scorecardpy`, `tensorflow` and `keras`.
  - Auto-installed idempotently at package/entry-point load in
    `backend_v3/__init__.py`, `mcp_v3/__init__.py`,
    `frontend_v3/__init__.py`, `treegov_mcp.py` and
    `scripts/validate_uci.py`.

## mcp_v3 (Phase 5.0 — headless MCP layer, stable since 5.0.b)

- `mcp_v3.tools.TOOLS` — registry of 27 frozen `ToolDescriptor`
  entries (`name`, `description`, `method_name`, `min_state`), each
  mapping 1:1 to a public `Session` method/property (Invariant I-4).
  Intended consumer: the MCP server built in Phase 5.0.b. The three
  entries added by Phases 6.0 and 7.0 are `score_batch`,
  `compare_champion_challenger` and `calculate_ecl`.
- `mcp_v3.dto._jsonable` — underscore prefix = internal under the
  stability rule above. Invariant I-3: `json.dumps(_jsonable(x),
  allow_nan=False)` never raises (NaN/Inf → None). Enums serialize
  as their `.name` (Phase 5.0.b: `FlowState` rides as `"DATA_LOADED"`
  etc.). Since Block 2C (20/11/2026), dictionary keys are also normalized
  (`np.bool_` → `bool`, `np.integer` → `int`, finite `np.floating` → `float`,
  `enum.Enum` → `.name`).
- `mcp_v3.server` (Phase 5.0.b; hardened in Block 2C, 20/11/2026) — FastMCP
  server exposing the exact **27** registered tools against
  `backend_v3.Session` over stdio; SDK pinned `mcp>=1.0.0,<2.0.0` (v2 renames
  FastMCP → MCPServer). `evaluate_oos` adapts `n_groups` to the OOS partition
  size by default (D20 rule); all dict/list outputs go through `_jsonable`
  (Invariant I-3) and session access is guarded by a module-level
  `threading.RLock`. Security and validation contract (Block 2C):
  - **Path confinement (`TREEGOV_MCP_ROOT`):** file-accepting tools
    (`load_dataset`, `load_oot`, `compare_champion_challenger`,
    `calculate_ecl`, `score_batch`) confine all paths strictly within the
    existing directory configured by `TREEGOV_MCP_ROOT` (or `Path.cwd()` if
    unset), reject null bytes, symlinks/`..` escaping the root, and any
    non-`.csv` extension. `score_batch` additionally blocks
    `output_path == csv_path` and forbids overwriting existing output files.
  - **Fail-fast parameter validation:** `train()` uses `BASEL_PD_FLOOR_MIN`
    and accepts only `"binary"`/`"categorical"` for `target_type` and
    `"banking"`/`"research"` for `governance_mode`; `fix_spec()` rejects
    `population_ok_values=[]` and coerces class keys safely against observed
    target classes (rejecting booleans and key collisions); all numeric tool
    arguments enforce explicit bounds, finiteness (`math.isfinite`) and
    rejection of `bool`.
  Phase 5.0.c verifies the full four-engine flow and strict JSON output
  end to end (`tests/test_mcp_parity.py`); no public symbol was added.
  Since Phase 4.0.1.a, the `export_sql`, `export_python` and
  `export_markdown` tools accept the keyword argument
  `unseen_policy: str = "exclude"` and forward it to the corresponding
  `Session` wrapper.
- `treegov_mcp` — root entry point registered as the `treegov-mcp`
  console script (`treegov_mcp:main`); installs `install_import_guard()`
  (white-box guardrail) before importing `mcp_v3.server`; requires the `[mcp]`
  extra.

> **Stability (Phase 5.0.b, 01/11/2026).** The MCP adapter is a stable 1.x public API. The public surface is: `mcp_v3.tools.TOOLS` (registry of 27 frozen `ToolDescriptor` entries), `mcp_v3.dto._jsonable` (JSON-native converter, Invariant I-3), `mcp_v3.server.app` (FastMCP stdio server) and `treegov_mcp.main` (console script `treegov-mcp`). The SDK dependency is optional (`pip install treegov[mcp]`, pin `mcp>=1.0.0,<2.0.0`). The `_jsonable` name keeps its underscore prefix per the stability rule above (internal helper), but its contract is public and covered by tests.

---

Nota (Fase 2.1.b, 03/11/2026): dos cambios en la capa de
presentación, sin alterar la API pública del backend. (a) El paquete
`frontend_v3` instala el guardrail de imports de
`backend_v3.import_guard` en su `__init__` (idempotente; bloquea
sklearn/statsmodels/xgboost/lightgbm/catboost también en procesos
GUI). (b) Nuevo helper interno
`frontend_v3.icons.load_icon(name: str, theme: str = "light") -> QIcon`
que carga SVG de Bootstrap Icons v1.11.3 (MIT) desde
`frontend_v3/resources/icons/`. Sustituye los iconos
`QStyle.StandardPixmap` en toolbar y wizard. Ninguno de los dos es
parte de la API pública del backend; se documentan aquí por
completitud de la capa de presentación.

## Cross-reference — design decisions

For the rationale behind the API's behaviour (defaults, invariants,
governance modes, non-canonical choices), see
[`docs/design_decisions.md`](design_decisions.md). That document
explains, for each public symbol, the design choices it embodies.

In particular:
- `GovernanceMode.BANKING` vs `RESEARCH`: `design_decisions.md` §0.3.
- `predict_pd(unseen_policy="error")` default: `design_decisions.md` §7.6.
- `SplitConfig` invariants: `design_decisions.md` §1.3.
- Fingerprint composition: `design_decisions.md` §10.1, §10.2.
- QUEST Bonferroni family and other canonical deviations:
  `design_decisions.md` §11.
- `compute_oos_metrics` input contract and `OOSMetrics` field
  additions: `docs/3.5_design_multiclass_weighted_reports.md` §2.0
  (D15), §2.4 (D16), §2.7 (D17).
- Reporting dispatch by K, superset DTOs, adaptive n_groups:
  `docs/3.5_design_multiclass_weighted_reports.md` §3.1 (D18, D20),
  §3.3 (D19).
- Session-level multiclass unblocking and label translation:
  `docs/3.5_design_multiclass_weighted_reports.md` §4 (Gini Drop),
  §5 (Session changes).
- Multiclass formulas (Hand & Till AUC, worst-case KS, Brier with
  1/2 factor, blocked Hosmer-Lemeshow, PR-AUC micro, K×K matrix,
  adaptive n_groups): `docs/methodology.md` §8.11 to §8.14.

> **Note:** this list reflects the stable 1.x public API through Phase 7,
> Phase 3.12, and Phase 2 MRM Audit Remediation (Blocks 2A–2G, `v1.0.0rc8`).
> Later phases (see `docs/roadmap.md`) will add new public modules, which
> will be documented here once they stabilize.

*Generated against the actual `__all__` of each module (verified at Phase
2.1). `log_config` and `import_guard` declare no `__all__`; the listing is
their canonical public API (only non-underscore functions). `frontend_v3`
is the presentation layer (no analytical logic); its modules
(`app`, `main_window`, `wizard`, `theme`, `i18n`) are internal to the GUI
and therefore not listed here.*

Nota (Fase 3.10.a): La clase `TreePanel` expone ahora los métodos públicos `zoom_in()`, `zoom_out()` y `zoom_fit()` para que la `QToolBar` de `MainWindow` pueda controlar la vista sin acceder a atributos privados.

Nota (Fase 3.11.a.1, 24/10/2026): fase puramente visual (frontend: layout clásico, nodos QPainter, tema forzado vía QPalette, copia TSV en tablas). No alteró la superficie de la API pública: `backend_v3/` intacto y ningún módulo de `frontend_v3` ganó símbolos públicos nuevos (el método de copia TSV es privado: `ReportsPanel._copy_selection_to_clipboard`).

Nota (saneamiento post-auditoría externa, 25/10/2026): sin cambios de firma pública. Tres correcciones de coherencia interna con reflejo en este documento: (a) el sufijo del fingerprint de `Session.intervene_node` pasa de `-pN` a `-iN` (ver arriba); (b) el routing por `bin_edges` (`TreeBuilder._partition`, `predict_leaf_assignment`) y el binning de `ChaidEngine` usan `np.digitize(..., right=True)` — convención `(a, b]` ya documentada en `methodology.md`; (c) la pestaña Costs del wizard (interna, fuera de la API pública) es ahora N×N dinámica (`AdvancedOptionsDialog(n_classes=...)`), alineada con la validación N = nº de clases de `Session.fix_spec(cost_matrix=...)`.

Nota (Fase 3.6.e, 25/10/2026): terminología dinámica por modo de gobernanza. El frontend gana el resolvedor `tr_term(concept: str, mode: str) -> str` en `frontend_v3/i18n.py` (mapea `concept` a la clave `term_{banking|research}_{concept}`; paridad EN/ES). Es interno de la GUI (no forma parte de la API pública del backend, que sigue emitiendo los mismos campos de DTO: `pd`, `bad_rate`, `n_bad`, …). Los paneles `ReportsPanel`, `MetricsPanel` y `TreePanel` exponen `set_governance_mode(mode)`; el modo visible queda atado al `GovernanceMode` congelado en el `params_fingerprint` del modelo entrenado (sin toggle en caliente). En BANKING las etiquetas visibles son bit a bit idénticas a las anteriores a la fase (diseño `docs/3.6.e_design_non_banking.md` §5).

Nota (Fase 3.12, 14/11/2026): la API pública de consulta gana `get_rules`,
`get_summary` y `get_node_cases`; los exportadores ganan el filtro aditivo
`node_id=None`. Los nuevos contratos de partición, subárbol y DTO nativo se
documentan en `backend_v3.session_state` y su justificación en
`docs/design_decisions.md` §26.

Nota (Bloque 2D, 20/11/2026): en la capa de presentación interna (`frontend_v3`,
Sala Limpia), `ModelWizard.current_config()` expone `"target_type"` (`"BINARY"`
o `"CATEGORICAL"` como string plano) y rechaza con `ValueError` el esquema
`"NONE"` (radio `"No validar"` deshabilitado conforme a SR 11-7);
`AdvancedOptionsDialog` valida estrictamente celdas finitas `>= 0` y devuelve
`()` ante tablas todo-ceros; `GovernancePage` limpia `_cost_matrix` al cambiar
el target y muestra el esquema CV real (`k=<cv_k>`) en su resumen HTML
escapado; `ReportsPanel` renderiza la matriz $K \times K$ completa con
etiquetas reales en UI y exportación HTML cuando $K \ge 3$ (paridad `2 × 2`
intacta para $K = 2$). Ver `docs/design_decisions.md` §30.

> **Maintenance:** this document must be updated after any phase that adds
> public modules. See `docs/audit_log.md` for the history.
