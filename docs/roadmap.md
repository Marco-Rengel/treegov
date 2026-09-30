# TreeGov Roadmap

**Legend:** ✅ Completed · 🟡 In progress · ⏳ Planned

## Completed

- ✅ **Phase 0** (algorithmic core): 4 engines + statistics + types +
  import_guard + log_config.
- ✅ **Phase 1** (transactional flow): splitting + profiling + tree_builder +
  session_state.
- ✅ **Phase 1.2** (OOS evaluation + pruning): validation + pruning.
  - Test suite: 107/107.
- ✅ **Phase 1.3** (OOT + stability): stability.py + extensions to
  session_state.py.
  - Test suite: 119/119.
- ✅ **Phase 2.0** (GUI skeleton): PySide6 QMainWindow (menus, 3-panel
  splitter, status bar), QSS light/dark themes, bilingual EN/ES i18n via
  plain-Python dictionary with live retranslate.
  - Test suite: 128/128.
- ✅ **Phase 2.1** (transactional wizard): 4-step QWizard (engine,
  predictors/target, validation scheme, MRM governance) feeding Session.
  Governance Mode (Banking/Research) added: Banking is the default;
  Research disables Jeffreys + PD Floor for non-banking domains (health,
  social sciences). Backend gained Session.describe_dataset() /
  fix_spec(predictors=...) / train(engine by name) /
  reset_to_data_loaded().
  - Test suite: 148/148.
- ✅ **Phase 2.2** (interactive tree viewer): QGraphicsView render with
  deterministic Reingold-Tilford layout, idempotent zoom (Ctrl + +/-),
  exclusive node selection, live retranslation, theme recolor.
  - Test suite: 158/158.

## Upcoming phases

### 🟡 Phase 2.1.b — Hardening extras
**Priority: MEDIUM**
- Cross-validation scheme (Step 3 combo placeholder already in place).
- Runtime backend-import guardrail in the GUI process (deferred from
  Phase 2.0; the AST smoke check only covers numpy/pandas/scipy).

### 🟡 Phase 2.3 — OOS/OOT metrics panel
**Priority: HIGH**

**Métricas requeridas:**
- Gini, KS, HL, Brier, ROC + AUC, PR-AUC (`backend_v3/validation.py`)
- PSI, CSI, Gini Drop con semáforos Basel/EBA (`backend_v3/stability.py`)
- Mnemonics de teclado ("&") para menús

**Metodología de trabajo (actualizada 29/09/2026):**

La Fase 2.3 se divide en sub-pasos cortos. Todas las sub-fases se ejecutan
con **Aider 0.86.2 + Kimi K3 (NVIDIA NIM)** con tool calls (migrado desde
OpenCode el 27/09/2026; ver `docs/audit_log.md`).

| Sub-paso | Estado | Alcance |
|---|---|---|
| 2.3.a Diseño estructural | ✅ | Dónde encaja el panel; archivos a crear/modificar |
| 2.3.b Claves i18n | ✅ | 23 claves EN/ES con paridad estricta |
| 2.3.c Esqueleto del panel | ✅ | Clase widget + 3 tests de construcción |
| 2.3.d Backend de reporting | ✅ | `backend_v3/reporting.py` + `Session.get_oos_oot_report()` + 6 tests |
| 2.3.e.1 Normalización de semáforos | ✅ | Alfabeto backend en inglés (`STABLE`/`MODERATE`/`UNSTABLE`/`UNDETERMINED`/`CRITICAL`/`WARNING`/`NONE`) |
| 2.3.e.2 Claves i18n por estado | ✅ | Renombrado `status_green/yellow/red` → `status_stable/moderate/unstable` + 4 claves nuevas |
| 2.3.e.3 Tokens QSS semánticos | ✅ | 4 tokens (`STATUS_OK/WARN/CRIT/UNKNOWN`) en ambas paletas + 4 selectores QSS |
| 2.3.e.4 MetricsPanel funcional | ⏳ Próxima | UI del panel con badges de estado consumiendo el DTO del backend |
| 2.3.e.5 Cableado MainWindow ↔ MetricsPanel | ⏳ | Handlers de menú + refresco del panel |
| 2.3.f Tests E2E + cierre | ⏳ | Suite completa + audit_log + roadmap + estado |

**Regla de proveedor:**
- **Aider 0.86.2 + Kimi K3 (NVIDIA NIM)**: implementación, edición de archivos,
  tests, refactor, documentación.
- **Instalación:** global vía `pipx` con Python 3.11.9 (fuera del `.venv/`).

Cada sub-paso se audita antes de pasar al siguiente. Verificación manual
obligatoria (`python -m pytest tests -q`, `git status`, `git diff` del
archivo tocado) tras cada tarea de Aider.

### 🟡 Phase 2.4 — Reports + integration
**Priority: MEDIUM**
- Gains table, classification matrix.
- HTML export via QTextBrowser.
- End-to-end GUI tests + screenshots for README.

### ⏳ Phase 3 — Analytical reports + MCP layer
**Priority: MEDIUM**

- Gains table and classification matrix.
- Dual export: nested SQL + pure Python.
- MCP (Model Context Protocol) layer for consumption from LLM agents.
  Headless backend as the base; MCP as an adapter (it does not replace the GUI).

### ⏳ Phase 4 — Batch scoring and production
**Priority: MEDIUM**

- Apply the tree to the full portfolio.
- Champion-challenger: compare engines and versions.

### ⏳ Phase 5 — IFRS 9 / ECL
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