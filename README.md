# TreeGov — Risk Segmentation Workbench

**Version**: 1.0.0a5
**Author**: Marco Rengel
**License**: Apache 2.0
**Graphics engine**: PySide6
**Analytical engine**: Python (NumPy, pandas, scipy.stats)
**Test suite**: 411/411 passing

> ⚠️ **Regulatory notice.** TreeGov is under technical validation (Model Risk Management - MRM). **Restricted use: technical MRM validation. Not fit for banking production without regulatory approval.** Any use in a regulated production environment (banking or otherwise) requires independent validation, formal approval, and integration with the institution's model governance framework.

**Data scope.** TreeGov is developed exclusively with public datasets (German Credit, UCI) and synthetic data. It is designed for end use with real banking data on the analyst's desktop: the CSV never leaves the machine. No real data is sent to third-party AI APIs during development. When TreeGov is used in production with real data, the DEBUG logs and exported HTML reports contain sensitive model information (per-node PDs, segment counts, real column names, file paths) and should be treated as confidential material by the analyst.

---

## Executive summary

TreeGov is an analytical workbench for **decision-tree segmentation** with **optional native model governance (MRM)** and **IFRS 9** alignment. It implements the three classic decision-tree algorithms — CHAID (with its Exhaustive variant), C&RT, QUEST — with **white-box mathematics**: every statistical formula is written explicitly in the source code and cited to its original publication.

Governance is opt-in, not the product's identity. TreeGov ships with two explicit modes. **Banking mode** (the default, and the natural choice for regulated credit-risk work) applies the full MRM layer: Jeffreys estimator on node probabilities, PD floor per Basel (BCBS CRE 20.39), and fingerprints that record the governance choice. **Research mode** turns both off, producing raw empirical probabilities with no regulatory constraints — opening TreeGov to non-banking domains (health, social sciences, marketing, biology) without sacrificing the white-box, auditable core. The choice is explicit, recorded in the model fingerprint, and never silent.

Unlike general-purpose libraries (scikit-learn, statsmodels, R packages) that require programming, TreeGov provides a **graphical environment** where the analyst focuses on analysis rather than code. Unlike discontinued GUI tools, it is open source, actively maintained, and built from the ground up with regulatory traceability (SR 11-7, Basel, IFRS 9) as a first-class design principle.

---

## Philosophy

> "Python gives you the engine. TreeGov gives you the engine, the brakes, the dashboard, the seatbelt, and the maintenance log. Which would you choose for a model that will be audited by the regulator?"

TreeGov starts from one premise: model governance is not a layer you add at the end, but a principle woven into every component. While statistical libraries and scripting environments provide the analytical engine, TreeGov provides in addition the brakes (MRM controls), the dashboard (graphical display), the seatbelt (auditability), and the maintenance log (the immutable audit trail). For a model that will be audited by a regulator, the choice is not technical: it is about governance.

*Read the full project philosophy → [English](https://github.com/Marco-Rengel/treegov/blob/main/docs/philosophy.md) · [Español](https://github.com/Marco-Rengel/treegov/blob/main/docs/philosophy.es.md)*

---

## What is TreeGov?

An analytical segmentation tool for credit risk with native MRM/IFRS 9 governance. It implements CHAID (Kass, 1980), C&RT (Breiman et al., 1984) and QUEST (Loh & Shih, 1997) with auditable white-box mathematics.

---

## Design principles

1. **Clean-room architecture**: strict separation between the analytical backend (`backend_v3/`, no GUI dependencies) and the presentation layer (`frontend_v3/`, no analytical logic).
2. **White box**: sklearn, statsmodels, and any other black-box library are forbidden. Every statistical formula is written explicitly in the code, with its bibliographic citation.
3. **Native governance**: DEBUG-grade transactional logging, immutable configuration (frozen `SplitConfig`), and mathematical invariant validation at construction time.

---

## Analytical capabilities

| Capability | Reference | Regulatory anchor | Key characteristics |
|---|---|---|---|
| **CHAID** classic and Exhaustive | Kass (1980); Biggs et al. (1991) | — | Iterative category merging with Bonferroni correction, multiclass support, Cochran rule |
| **C&RT** | Breiman et al. (1984) | — | Gini impurity / variance reduction, surrogate splits for missing values, multiclass (K ≥ 2) |
| **QUEST** | Loh & Shih (1997) | — | Unbiased variable selection (ANOVA + χ² + Levene), univariate QDA split for K=2, Gini reduction sweep for K > 2 |
| **Jeffreys estimator + PD Floor** | Jeffreys (1946) | BCBS CRE 20.39 | Mitigation of zero probabilities in low-default portfolios |
| **Hamilton-Hare partition** | — | — | Exact stratified train/test split, no rounding bias |
| **Anti-leakage imputation** | — | SR 11-7 | Train-only statistics (`TrainOnlyImputer`) |
| **Cost-complexity pruning** | Breiman et al. (1984) | — | Post-pruning with the α sequence; deterministic node re-indexing |
| **OOS / OOT validation** | Hanley & McNeil (1982); Hosmer & Lemeshow (1980); Davis & Goadrich (2006) | Basel; SR 11-7 | Gini, KS, HL, Brier, ROC/AUC, PR-AUC; out-of-time cohort support |
| **Stability monitoring** | Siddiqi (2006) | Basel / EBA | PSI (leaves), CSI (covariates), Gini Drop with traffic lights |
| **Gains table + classification matrix** | Siddiqi (2006) | SR 11-7 | Per-leaf / per-bucket view, cumulative / decumulative metrics, KS / AUC / Gini recomputed, HTML export |

---

## Technology stack

- Python 3.11 / 3.12
- PySide6 (graphical interface)
- numpy, pandas, scipy.stats (statistical computation)
- pyarrow, openpyxl (data ingestion)
- pytest (optional: tests are runnable with plain python)

---

## Repository structure

```
TreeGov/
├── backend_v3/              # Pure analytical layer (0 Qt imports)
│   ├── import_guard.py      # Black-box library blocker
│   ├── log_config.py        # DEBUG transactional logger
│   ├── types.py             # SplitConfig (frozen) + enums
│   ├── statistics.py        # chi2, F, Brown-Forsythe, Stirling, Kass
│   ├── imputation.py        # TrainOnlyImputer (anti-leakage)
│   ├── chaid_engine.py      # CHAID classic + Exhaustive
│   ├── crt_engine.py        # C&RT binary + surrogate splits
│   ├── quest_engine.py      # QUEST binary + univariate QDA
│   ├── splitting.py         # Hamilton-Hare stratified split
│   ├── profiling.py         # Predictor type inference
│   ├── tree_builder.py      # BFS tree construction + TreeModel
│   ├── session_state.py     # Flow state machine (EMPTY to TRAINED to OOT)
│   ├── validation.py        # OOS metrics + OOT evaluation
│   ├── pruning.py           # Cost-complexity pruning (Breiman)
│   ├── reporting.py         # Gains table + classification matrix DTOs
│   └── stability.py         # PSI / CSI / Gini Drop
├── frontend_v3/             # Presentation layer (Phase 2)
├── tests/                   # Unit tests (dual: pytest / python direct)
├── docs/                    # Documentation
│   ├── methodology.md       # Mathematical methodology (EN)
│   ├── design_decisions.md  # Implementation decisions (EN)
│   ├── 3.1_design_multiclass.md  # Phase 3.1 design (EN)
│   ├── 3.2_decisions_consolidated.md  # Phase 3.2 decisions (EN)
│   ├── 3.3_design_population_categories.md  # Phase 3.3 design (EN)
│   ├── 3.4_design_multiclass_crt_quest.md  # Phase 3.4 design (EN)
│   ├── 3.5_design_multiclass_weighted_reports.md  # Phase 3.5 design (EN)
│   ├── api.md               # Public API (EN)
│   ├── roadmap.md           # Phase plan (EN)
│   ├── philosophy.md        # Project philosophy (EN)
│   ├── philosophy.es.md     # Philosophy (ES)
│   ├── estado_proyecto.md   # Project state dossier (ES)
│   ├── audit_log.md         # Audit trail (ES)
│   ├── contexto_para_nueva_sesion.md  # Session bootstrap (ES)
│   └── prompt_para_asistente.md       # Assistant brief (ES)
├── archive/                 # Historical documents (read-only)
├── data/                    # Datasets (read-only, Git-ignored)
├── logs/                    # Per-run execution logs (Git-ignored)
├── treegov.py               # Headless orchestrator (CLI)
├── treegov_gui.py           # GUI entry point (Phase 2)
├── pyproject.toml           # Packaging
├── requirements.txt         # Working minimum pins (pyproject.toml is source of truth)
├── opencode.json            # OpenCode project configuration
├── README.md                # This file (EN)
├── README.es.md             # Spanish translation
├── AGENTS.md                # Operating instructions for AI agents
├── CONVENTIONS.md           # Operational conventions for Aider
├── LICENSE                  # Apache 2.0
├── NOTICE.md                # Legal notice and attribution
├── .gitignore               # Git exclusions
├── .aiderignore             # Aider repo-map exclusions
├── .gitattributes           # Line-ending normalization
├── .aider.conf.example.yml  # Aider configuration template
└── .treegovrules            # Governance rules for AI agents
```

---

## Quick start

### Installation

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### Headless demo (Phase 0)

```powershell
.\.venv\Scripts\python treegov.py
```

### Performance benchmark (N=1M)

```powershell
.\.venv\Scripts\python tests\benchmark_1m.py --n 1000000 --seed 42
```

### Test suite

```powershell
.\.venv\Scripts\python -m pytest tests -q
```

---

## Project status

| Phase | Description | Status |
|---|---|---|
| **0** | Algorithmic core: 4 engines + statistics + imputation | Completed |
| **1** | Transactional flow: splitting, profiling, tree_builder, session_state | Completed |
| **1.2** | OOS evaluation + cost-complexity pruning | Completed |
| **1.3** | OOT validation + PSI/CSI stability monitoring | Completed |
| **2.0-2.2** | GUI with PySide6: skeleton, transactional wizard, tree viewer | Completed |
| **2.3** | OOS/OOT metrics panel | Completed |
| **2.4** | Reports + integration | Completed |
| **3.0** | Documentation closure + configurable canonical parameters | Completed |
| **3.1** | Multiclass (target + wizard + MetricsPanel alerts) | Completed |
| **3.2** | Sample weighting | Completed |
| **3.3** | Indet / Insufficient / No Perf categories | Completed |
| **3.4** | Multiclass support in C&RT and QUEST | Completed |
| **3.5** | Reports adapted for multiclass and weighting | Completed |
| **3.6** | Validation with public datasets | Planned |
| **3.6.b** | Non-banking mode (neutral vocabulary + examples) | Planned |
| **3.7** | Phase 3 closure + v1.0.0 stable | Planned |
| **4** | Advanced reports + export (SQL, Python, MD/JSON) | Planned |
| **5** | MCP layer for LLM agents | Planned |
| **6** | Batch scoring + champion-challenger | Planned |
| **7** | IFRS 9 / ECL (staging, ECL = PD x LGD x EAD) | Planned |

**Test suite: 411/411 passing.**

---

## Academic references

- Biggs, D., de Ville, B. & Suen, E. (1991). *A Method of Choosing Multiway Partitions for Classification and Decision Trees*. Journal of Applied Statistics 18(1), 49-62.
- Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984). *Classification and Regression Trees*. Wadsworth.
- Brier, G.W. (1950). *Verification of forecasts expressed in terms of probability*. Monthly Weather Review 78(1), 1-3.
- Brown, M.B. & Forsythe, A.B. (1974). *Robust Tests for the Equality of Variances*. Journal of the American Statistical Association 69(346), 364-367.
- Cochran, W.G. (1954). *Some Methods for Strengthening the Common Chi-2 Tests*. Biometrics 10(4), 417-451.
- Davis, J. & Goadrich, M. (2006). *The relationship between Precision-Recall and ROC curves*. Proceedings of the 23rd International Conference on Machine Learning (ICML), 233-240.
- Fisher, R.A. (1925). *Statistical Methods for Research Workers*. Oliver & Boyd, Edinburgh.
- Hanley, J.A. & McNeil, B.J. (1982). *The meaning and use of the area under a receiver operating characteristic (ROC) curve*. Radiology 143(1), 29-36.
- Heeringa, S.G., West, B.T. & Berglund, P.A. (2010). *Applied Survey Data Analysis*. Chapman & Hall/CRC.
- Hosmer, D.W. & Lemeshow, S. (1980). *A goodness-of-fit test for the multiple logistic regression model*. Communications in Statistics A10, 1043-1069.
- Jeffreys, H. (1946). *An invariant form for the prior probability in estimation problems*. Proceedings of the Royal Society of London A 186(1007), 453-461.
- Kass, G.V. (1980). *An Exploratory Technique for Investigating Large Quantities of Categorical Data*. Applied Statistics 29(2), 119-127.
- Levene, H. (1960). *Robust tests for equality of variances*. In Contributions to Probability and Statistics, Stanford University Press, 278-292.
- Loh, W.-Y. & Shih, Y.-S. (1997). *Split Selection Methods for Classification Trees*. Statistica Sinica 7(4), 815-840.
- Pearson, K. (1900). *On the criterion that a given system of deviations from the probable in the case of a correlated system of variables is such that it can be reasonably supposed to have arisen from random sampling*. Philosophical Magazine Ser. 5, 50(302), 157-175.
- Siddiqi, N. (2006). *Credit Risk Scorecards: Developing and Implementing Intelligent Credit Scoring*. Wiley.

---

## Regulatory references

- **Basel (BCBS CRE 20.39)**: regulatory PD floors.
- **EBA/GL/2017/16**: guidelines on the specification, estimation, and validation of PD/LGD parameters in IRB models.
- **IFRS 9**: staging, ECL, and asymmetric threshold optimization.
- **SR 11-7 / OCC 2011-12**: model risk management (MRM) guidance.

---

## License

Apache License 2.0 — see [LICENSE](https://github.com/Marco-Rengel/treegov/blob/main/LICENSE).

---

## Contact

Marco Rengel — marcrengel@gmail.com — github.com/Marco-Rengel

---

## Translations

- [Español (Spanish)](README.es.md)