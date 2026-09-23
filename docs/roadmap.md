# TreeGov Roadmap

## Completed

- **Phase 0** (algorithmic core): 4 engines + statistics + types +
  import_guard + log_config.
- **Phase 1** (transactional flow): splitting + profiling + tree_builder +
  session_state.
- **Phase 1.2** (OOS evaluation + pruning): validation + pruning.
  - Test suite: 107/107.
- **Phase 1.3** (OOT + stability): stability.py + extensions to
  session_state.py.
  - Test suite: 119/119.

## Upcoming phases

### Phase 2.0 — Application skeleton
**Priority: HIGH**
- Entry point treegov_gui.py.
- QMainWindow with horizontal QSplitter (left panel, central tabs, right HUD).
- Top menu (File / Model / View / Help) and status bar.
- Light/dark theme via QSS.

### Phase 2.1 — Transactional wizard (4 steps)
**Priority: HIGH**
- Step 1: engine selection (CHAID / Exhaustive / C&RT / QUEST).
- Step 2: predictors + target.
- Step 3: validation scheme (train/test, seed).
- Step 4: MRM governance (max_depth, min_child_size, PD floor).

### Phase 2.2 — Interactive tree viewer
**Priority: HIGH**
- QGraphicsView tree render, zoom (Ctrl + +/-), node selection.

### Phase 2.3 — OOS/OOT metrics panel
**Priority: HIGH**
- Gini, KS, HL, Brier, ROC + AUC, PR-AUC.
- PSI, CSI, Gini Drop with Basel/EBA traffic lights.

### Phase 2.4 — Reports + integration
**Priority: MEDIUM**
- Gains table, classification matrix.
- HTML export via QTextBrowser.
- End-to-end GUI tests + screenshots for README.

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
