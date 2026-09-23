# TreeGov Public API

## API stability

The modules and symbols listed here are **public and stable** within
version 1.x. Any change breaks compatibility and requires a major version
bump. Symbols not listed (in particular, those starting with an
underscore) are internal and may change without notice.

## backend_v3.types

- `SplitConfig` (frozen dataclass) — common contract of the 4 engines.
- `TargetType`, `PredictorType`, `CutKind` (Enums).
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

> **Note:** this list reflects the API as of the close of Phase 1.2. Later
> phases (see `docs/roadmap.md`) will add new public modules, which will be
> documented here once they stabilize.

*Generated against the actual `__all__` of each module (verified at Phase
1.2). `log_config` and `import_guard` declare no `__all__`; the listing is
their canonical public API (only non-underscore functions).*

> **Maintenance:** this document must be updated after any phase that adds
> public modules. See `docs/audit_log.md` for the history.
