# TreeGov Roadmap

## Completed

- **Phase 0** (algorithmic core): 4 engines + statistics + types +
  import_guard + log_config.
- **Phase 1** (transactional flow): splitting + profiling + tree_builder +
  session_state.
- **Phase 1.2** (OOS evaluation + pruning): validation + pruning.
  - Test suite: 107/107.

## Upcoming phases

### Phase 1.3 — OOT validation and basic monitoring
**Priority: HIGH (indispensable in credit risk)**

- Out-of-Time (OOT) validation: a later time cohort, not a random partition.
- Gini Drop computation (train vs OOS vs OOT).
- Population stability: PSI (leaves) and CSI (covariates) with
  Basel / EBA traffic lights (STABLE < 0.10, MODERATE 0.10-0.25, UNSTABLE >= 0.25).

### Phase 2 — GUI with PySide6
**Priority: HIGH (visible deliverable)**

- Transactional wizard (4 steps).
- Interactive tree viewer with zoom.
- OOS metrics panel.
- Pruning report (original vs pruned tree comparison).

### Phase 3 — Analytical reports + MCP layer
**Priority: MEDIUM**

- Gains table and classification matrix.
- Dual export: nested SQL + pure Python.
- MCP (Model Context Protocol) layer for consumption from LLM agents.
  Headless backend as the base; MCP as an adapter (it does not replace the GUI).

### Phase 4 — Batch scoring and production
**Priority: MEDIUM**

- Apply the tree to the full portfolio.
- Champion-challenger: compare engines and versions.

### Phase 5 — IFRS 9 / ECL
**Priority: LOW (depends on integration with banking systems)**

- PD per segment (tree leaf).
- Staging (Stage 1/2/3).
- ECL computation: PD × LGD × EAD.

## Recorded architectural decisions

- **GUI**: PySide6 (not Streamlit). Reason: banking data confidentiality
  policy; data must not leave the analyst's desktop.
- **MCP**: added as an adapter in Phase 3; it does not replace the GUI.
- **White box**: sklearn/statsmodels/xgboost/lightgbm/catboost are forbidden.
- **Gini**: convention 2·AUC − 1 (credit scoring).
- **License**: Apache 2.0.

## Pending decisions

- **Distribution**: packaging method (PyInstaller / Inno Setup /
  MSI installer), digital signature, and distribution channel. To be
  decided before v1.0.
- **Commercial license format** (if ever considered): the current Apache
  2.0 is open source; a parallel commercial version would require
  legal analysis.
