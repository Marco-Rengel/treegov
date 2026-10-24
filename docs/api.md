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
- `bonferroni_adjust(p, m) -> float`

## backend_v3.chaid_engine

- `ChaidEngine`, `MergeDiagnostics`, `MergeStep`

## backend_v3.crt_engine

- `CrtEngine`, `SurrogateSplit`

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
    cutpoint to the inter-means interval. `False` accepts any real root
    (canonical mode), tie-broken by closeness to the weighted mean. See
    `design_decisions.md` §4.3.

## backend_v3.imputation

- `TrainOnlyImputer`, `ImputationSpec`

## backend_v3.tree_builder

- `TreeBuilder`, `TreeModel`, `TreeNode`

## backend_v3.session_state

- `FlowState` (Enum), `SessionState`, `Session`
- `Session.describe_dataset() -> (columns, types)` — read-only profile of
  the loaded dataset (types as `PredictorType.name` strings; Phase 2.1).
- `Session.fix_spec(target, spec=None, *, predictors=None, target_class,
  class_labels, weight_col=None, population_col=None,
  population_ok_values=None)` — optional predictor subset filter applied
  inside the backend (Phase 2.1). `target_class` and `class_labels` are
  **mandatory** as of Phase 3.1: they name the class of interest and the
  label for each target class (see `docs/3.1_design_multiclass.md` §1bis).
  `weight_col` (Phase 3.2) declares the sample-weight column;
  `population_col` + `population_ok_values` (Phase 3.3) declare the
  opt-in population filter.
- `Session.train(engine, *, target_type, max_depth, min_child_size,
  min_child_weight=None, pd_floor=0.0005, apply_jeffreys=True)` —
  `engine` accepts an engine instance or its name ("CHAID" |
  "CHAID_EXHAUSTIVE" | "CRT" | "QUEST"); `pd_floor=None` +
  `apply_jeffreys=False` yields Research mode (Phase 2.1). Multiclass
  targets (K > 2) are supported by all engines since Phase 3.4;
  downstream metrics, reports and stability monitoring support K > 2
  since Phase 3.5. `min_child_weight` (Phase 3.7.c) is the weighted-mass
  floor per branch, complementary to `min_child_size` (which measures
  physical rows); it is only meaningful when a `weight_col` was declared
  in `fix_spec`. `None` (default) disables the check.
- `Session.get_gains_table(*, partition, by, n_buckets, tie, seed)` —
  flat DTO of a gains table for a routed partition (Phase 2.4.c.1).
  Supports K > 2 since Phase 3.5.
- `Session.get_classification_matrix(*, partition, threshold)` — flat
  DTO of a classification matrix (Phase 2.4.c.1). Supports K > 2 since
  Phase 3.5.c (see the extended entry below).
- `Session.reset_to_data_loaded()` — back to DATA_LOADED keeping the
  cached DataFrame (no CSV re-read; Phase 2.1).
- `Session.get_prune_sequence() -> list[dict[str, Any]]` — Read-only method that returns the cost-complexity pruning sequence for the trained model. Each dictionary contains `alpha` (float), `n_leaves` (int), and `r_subtree` (float). Returns an empty list if the model has no internal nodes. (Phase 3.9).
- `Session.evaluate_oos(*, n_groups=10)` — supports K > 2 since
  Phase 3.5.c. Internally translates `y` to the internal canonical
  order via `_translate_y_to_internal` and calls
  `compute_oos_metrics` with the full 2D probability matrix.
- `Session.evaluate_oot(*, n_groups=10, weight_oot=True)` — supports
  K > 2 since Phase 3.5.c. Same label translation. The Gini Drop
  formula is unchanged; it now feeds from the multiclass Gini.
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
- `predict_pd(model, X, *, unseen_policy="error")` — returns a 2D
  array of shape (n_rows, K) since Phase 3.1.
- `predict_leaf_assignment(model, X, *, unseen_policy="error")`.
- `compute_oos_metrics(p, y, *, n_groups=10, weights=None)` — the
  input `p` accepts two forms (Phase 3.5.a, decision D15): 1D
  (classic binary path) or 2D with shape (n, K) for multiclass. For
  K = 2, the 2D path reduces internally to column 0 and executes
  the binary path; the caller must pass `y_2d = 1 - y_1d` to
  preserve the uniform "column c ↔ label c" contract. For K > 2,
  `y` must be a 1D array of labels in {0, 1, ..., K-1}.

## backend_v3.reporting

- `build_oos_oot_report(st)` — flat OOS/OOT DTO (Phase 2.3.d).
- `GainsRow` (frozen dataclass) — one gains-table line. Extended in
  Phase 3.5.b with 6 additive fields at the end, all empty by default:
  `n_per_class`, `n_per_class_cum`, `n_per_class_decum`, and the
  weighted siblings `w_n_per_class`, `w_n_per_class_cum`,
  `w_n_per_class_decum`. In the binary path they stay empty.
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
  with 12 additive fields: `confusion_matrix`, `n_per_class`,
  `precision_per_class`, `recall_per_class`, `f1_per_class`,
  `accuracy`, and weighted siblings. `accuracy` is populated in both
  K=2 and K>2. The binary fields (`tp`, `tn`, `fp`, `fn`, `precision`,
  `recall`, `f1`, `bad_capture_rate`, `n_good`, `n_bad`) keep their
  meaning in K>2 by grouping the class of interest (index 0) as
  positive and the rest as negative (D19).
- `build_classification_matrix(leaf_assignment, y, pd_per_leaf, *,
  threshold=0.5, weights=None)` — binary, unchanged signature.
  Populates `accuracy` since Phase 3.5.b.
- `build_classification_matrix_multiclass(leaf_assignment, y,
  pd_per_leaf: dict[int, tuple[float, ...]], *, weights=None)` — new
  in Phase 3.5.b. Argmax assignment, K×K matrix, per-class metrics,
  accuracy, binary legacy fields from class 0 vs rest. `threshold`
  records NaN.

## backend_v3.stability

- `PSIReport`, `CSIReport`, `GiniDropReport`, `OOTReport`.
- `StabilityMonitor(*, eps=1e-4, renormalize=False)` (leaf_psi /
  covariate_csi / report).
- `psi_index(expected, actual, *, renormalize=False)`,
  `traffic_light(value)`, `gini_drop_alert(drop)`.
  - `renormalize` (bool, default False) — whether to renormalize both
    distributions after the ε-clip. Default `False` preserves the
    signal of vanishing bins (TreeGov convention); `True` is the
    canonical renormalized variant. See `design_decisions.md` §7.4.

## backend_v3.pruning

- `Pruner`, `PruneStep`
  *(Note: since Phase 3.9, pruning is interactive and weighted — wired into the GUI via `PruneDialog` and exposed via `Session.get_prune_sequence()`.)*

## backend_v3.splitting

- `stratified_split(y, train_frac, seed, log=None)`

## backend_v3.profiling

- `infer_spec(df, target, log=None)`, `MAX_ORDINAL_CATS`

## backend_v3.log_config

- `setup_logging(log_path, level) -> Logger`
- `get_logger(name) -> Logger`

## backend_v3.import_guard

- `install_import_guard()`, `is_installed()`

---

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

> **Note:** this list reflects the API as of the close of Phase 3.6
> (public-dataset validation). Later phases (see `docs/roadmap.md`) will
> add new public modules, which will be documented here once they
> stabilize.

*Generated against the actual `__all__` of each module (verified at Phase
2.1). `log_config` and `import_guard` declare no `__all__`; the listing is
their canonical public API (only non-underscore functions). `frontend_v3`
is the presentation layer (no analytical logic); its modules
(`app`, `main_window`, `wizard`, `theme`, `i18n`) are internal to the GUI
and therefore not listed here.*

Nota (Fase 3.10.a): La clase `TreePanel` expone ahora los métodos públicos `zoom_in()`, `zoom_out()` y `zoom_fit()` para que la `QToolBar` de `MainWindow` pueda controlar la vista sin acceder a atributos privados.

> **Maintenance:** this document must be updated after any phase that adds
> public modules. See `docs/audit_log.md` for the history.
