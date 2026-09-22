# TreeGov — Risk Segmentation Workbench

**Version**: 1.0.0a0
**Author**: Marco Rengel
**License**: Apache 2.0
**Graphics engine**: PySide6
**Analytical engine**: Python (NumPy, pandas, scipy.stats)
**Regulatory notice**: Software under technical validation (Model Risk Management - MRM).

---

## Philosophy

> "Python gives you the engine. TreeGov gives you the engine, the brakes, the dashboard, the seatbelt, and the maintenance log. Which would you choose for a model that will be audited by the regulator?"

TreeGov starts from one premise: model governance is not a layer you add at the end, but a principle woven into every component. While statistical libraries and scripting environments provide the analytical engine, TreeGov provides in addition the brakes (MRM controls), the dashboard (graphical display), the seatbelt (auditability), and the maintenance log (the immutable audit trail). For a model that will be audited by a regulator, the choice is not technical: it is about governance.

---

## What is TreeGov?

An analytical segmentation tool for credit risk with native MRM/IFRS 9 governance. It implements CHAID (Kass, 1980), C&RT (Breiman et al., 1984) and QUEST (Loh & Shih, 1997) with auditable white-box mathematics.

---

## Design principles

1. **Clean-room architecture**: strict separation between the analytical backend (backend_v3/, with no GUI dependencies) and the presentation layer (frontend_v3/, with no analytical logic).
2. **White box**: sklearn, statsmodels, and any other black-box library are forbidden. Every statistical formula is written explicitly in the code, with its bibliographic citation.
3. **Native governance**: DEBUG-grade transactional logging, immutable configuration (frozen SplitConfig), and mathematical invariant validation at construction time.

---

## Analytical capabilities

- **Classic CHAID and Exhaustive CHAID**: iterative category merging with the Bonferroni correction of Kass (1980), multiclass support.
- **Binary C&RT**: Gini impurity partitioning (classification) and variance (regression), with surrogate splits (Breiman et al., 1984).
- **Binary QUEST**: unbiased variable selection (ANOVA + chi-square + Levene) with univariate QDA split point (Loh & Shih, 1997).
- **Jeffreys estimator + PD Floor**: mitigation of zero probabilities in low-default portfolios (BCBS CRE 20.39).
- **Hamilton-Hare partition**: exact stratified train/test split, with no rounding bias.
- **Anti-leakage imputation**: TrainOnlyImputer fitted exclusively on the train fold.

---

## Technology stack

- Python 3.11 / 3.12
- PySide6 (graphical interface)
- numpy, pandas, scipy.stats (statistical computation)
- pyarrow, openpyxl (data ingestion)
- pytest (optional: the tests are also runnable with plain python)

---

## Repository structure

TreeGov/
- backend_v3/  — Pure analytical layer (0 Qt imports)
  - import_guard.py
  - log_config.py
  - types.py
  - statistics.py
  - imputation.py
  - chaid_engine.py
  - crt_engine.py
  - quest_engine.py
  - splitting.py
  - profiling.py
  - tree_builder.py
  - session_state.py
  - validation.py
  - pruning.py
- frontend_v3/  — Presentation layer (Phase 2 placeholder)
- tests/  — Unit tests
- docs/  — Current documentation (methodology.md, api.md, roadmap.md, philosophy.md, audit_log.md)
- archive/  — Historical documents and code (do NOT edit)
- data/  — Datasets (read-only)
- logs/  — Per-run execution logs
- treegov.py  — Headless orchestrator
- requirements.txt  — Dependencies
- .treegovrules  — Governance rules for AI agents

---

## Execution

### Installation

.\.venv\Scripts\python -m pip install -r requirements.txt

### Headless demo (Phase 0)

.\.venv\Scripts\python treegov.py

### Performance benchmark (N=1M)

.\.venv\Scripts\python tests\benchmark_1m.py --n 1000000 --seed 42

### Test suite

.\.venv\Scripts\python -m pytest tests -q

---

## Project status

**Phase 0 (algorithmic core)**: completed. 4 engines + imputation + orchestrator + benchmark, audited.
**Phases 1-4 (interface, wizard, reports)**: in development.

---

## Academic references

- Kass, G.V. (1980). An Exploratory Technique for Investigating Large Quantities of Categorical Data. Applied Statistics 29(2), 119-127.
- Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984). Classification and Regression Trees. Wadsworth.
- Cochran, W.G. (1954). Some Methods for Strengthening the Common Chi-2 Tests. Biometrics 10(4), 417-451.
- Loh, W.-Y. & Shih, Y.-S. (1997). Split Selection Methods for Classification Trees. Statistica Sinica 7(4), 815-840.
- Biggs, D., de Ville, B. & Suen, E. (1991). A Method of Choosing Multiway Partitions for Classification and Decision Trees. Journal of Applied Statistics 18(1), 49-62.

---

## License

Apache License 2.0

---

## Contact

Marco Rengel — marcrengel@gmail.com — github.com/Marco-Rengel

---

## Translations

- [Español (Spanish)](README.es.md)
