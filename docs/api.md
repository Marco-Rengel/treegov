# TreeGov Public API

## API stability

The modules and symbols listed here are **public and stable** within
version 1.x. Any change breaks compatibility and requires a major version
bump. Symbols not listed (in particular, those starting with an
underscore) are internal and may change without notice.

## backend_v3.types

- `SplitConfig` (frozen dataclass) — common contract of the 4 engines.
- `TargetType`, `PredictorType`, `CutKind` (Enums).
- `GovernanceMode` (Enum): `BANKING` (Jeffreys + PD Floor, default) |
  `RESEARCH` (raw k/n, no floor).
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

- `QuestEngine`, `QuestSelection`

## backend_v3.imputation

- `TrainOnlyImputer`, `ImputationSpec`

## backend_v3.tree_builder

- `TreeBuilder`, `TreeModel`, `TreeNode`

## backend_v3.session_state

- `FlowState` (Enum), `SessionState`, `Session`
- `Session.describe_dataset() -> (columns, types)` — read-only profile of
  the loaded dataset (types as `PredictorType.name` strings; Phase 2.1).
- `Session.fix_spec(target, spec=None, *, predictors=None)` — optional
  predictor subset filter applied inside the backend (Phase 2.1).
- `Session.train(engine, *, target_type, max_depth, min_child_size,
  pd_floor=0.0003, apply_jeffreys=True)` — `engine` accepts an engine
  instance or its name ("CHAID" | "CHAID_EXHAUSTIVE" | "CRT" | "QUEST");
  `pd_floor=None` + `apply_jeffreys=False` yields Research mode
  (Phase 2.1).
- `Session.reset_to_data_loaded()` — back to DATA_LOADED keeping the
  cached DataFrame (no CSV re-read; Phase 2.1).

## backend_v3.validation

- `OOSMetrics`, `predict_pd(model, X, *, unseen_policy="error")`,
  `predict_leaf_assignment(model, X, *, unseen_policy="error")`,
  `compute_oos_metrics`

## backend_v3.stability

- `PSIReport`, `CSIReport`, `GiniDropReport`, `OOTReport`.
- `StabilityMonitor` (leaf_psi / covariate_csi / report).
- `psi_index(expected, actual)`, `traffic_light(value)`, `gini_drop_alert(drop)`.

## backend_v3.pruning

- `Pruner`, `PruneStep`

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

> **Note:** this list reflects the API as of the close of Phase 2.1. Later
> phases (see `docs/roadmap.md`) will add new public modules, which will be
> documented here once they stabilize.

*Generated against the actual `__all__` of each module (verified at Phase
2.1). `log_config` and `import_guard` declare no `__all__`; the listing is
their canonical public API (only non-underscore functions). `frontend_v3`
is the presentation layer (no analytical logic); its modules
(`app`, `main_window`, `wizard`, `theme`, `i18n`) are internal to the GUI
and therefore not listed here.*

> **Maintenance:** this document must be updated after any phase that adds
> public modules. See `docs/audit_log.md` for the history.
