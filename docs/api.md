# API pública de TreeGov

## Estabilidad de la API

Los módulos y símbolos listados aquí son **públicos y estables** dentro de
la versión 1.x. Cualquier cambio rompe compatibilidad y requiere bump de
versión mayor. Los símbolos no listados (en particular, los que empiezan
por guion bajo) son internos y pueden cambiar sin aviso.

## backend_v3.types

- `SplitConfig` (frozen dataclass) — contrato común de los 4 motores.
- `TargetType`, `PredictorType`, `CutKind` (Enums).
- `MethodName`, `StatisticName` (alias Literales de validación del contrato).

## backend_v3.statistics

- `TestResult` (frozen dataclass): salida canónica de una prueba.
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

- `OOSMetrics`, `predict_pd`, `compute_oos_metrics`

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

> **Nota:** esta lista refleja la API al cierre de Fase 1.2. Las fases
> posteriores (ver `docs/roadmap.md`) añadirán nuevos módulos públicos,
> que se documentarán aquí cuando se estabilicen.

*Generado contra el `__all__` real de cada módulo (verificación en Fase 1.2).
`log_config` e `import_guard` no declaran `__all__`; lo listado es su API
pública canónica (solo funciones sin guion bajo).*

> **Mantenimiento:** este documento debe actualizarse tras cada fase que
> añada módulos públicos. Ver `docs/audit_log.md` para el historial.
