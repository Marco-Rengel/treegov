# TreeGov Philosophy

## The core sentence

> “Python gives you the engine. TreeGov gives you the engine, the brakes, the dashboard, the seatbelt, and the maintenance log. Which would you choose for a model that will be audited by the regulator?”

## Why does TreeGov exist?

There is a generation of risk analysts who need GUI tools to build auditable trees, and the tools that existed were discontinued without replacement. Statistical libraries and scripting environments offer analytical power, but not native governance. TreeGov fills that void.

## The differentiator

Governance is not an add-on. It is the starting point:

- Immutable configuration (*SplitConfig frozen*) = auditable evidence.
- Transactional *DEBUG logging* = regulatory traceability.
- White-box mathematics = citable and verifiable formulas.
- Black-box library blocking = auditability by design.

## Technological Independence

TreeGov is a modern mathematical reimplementation built exclusively from academic papers (Kass, Breiman, Loh & Shih) and the documented classic tree-station standard (circa 2001). All of its logic is white-box, guaranteeing algorithmic independence and maximum auditability: no third-party implementations, no black boxes, every formula explicit and traceable to its bibliographic source (see `docs/design_decisions.md` §0.5).

## Who it serves

- Credit risk analysts who want to spend time on analysis, not programming.
- MRM validation teams that need full traceability.
- Regulators who demand auditability of PD and classification models.
- Data scientists and business analysts who prefer to focus on model interpretation rather than writing infrastructure code.

## Commitment

TreeGov competes on transparency, governance, and regulatory defensibility. Predictive accuracy remains important, but never at the expense of explainability and auditability. If a team needs raw predictive power, they should use *XGBoost*. If they need a model that can be defended before a regulator, they use TreeGov.

## Regulatory references

- Basel (BCBS CRE 32.4): PD floors (0.05% for non-sovereign exposures).
- EBA/GL/2017/16: PD/LGD parameter validation.
- IFRS 9: staging and ECL.
- SR 11-7 / OCC 2011-12: Model Risk Management.

## Work methodology

TreeGov is developed with AI assistance under a workflow with MRM discipline:

- Methodological rigor: Design, then audit the design, then implement, then test, then document. Code is never written without first auditing the design.
- Short bursts, verification at the end of the block. The prompts for a sub-phase are grouped; the test suite is run when closing each block, not between prompts. This preserves the AI provider's cache, reduces cost, and keeps verification as a clear control point.
- Empirical verification over blind obedience. The AI assistant may report success without having executed the task. Therefore, every commit requires a green `pytest`, a clean `git status`, and a coherent `git diff --stat` before accepting the change.
- No agent runs alone for hours or days. Every change affects structural invariants (for example, the K=2 binary parity since Phase 3.1, or the `TreeModel` invariants). The human audits every sub-phase. Long-running agents have their place in disposable or low-risk projects; not in a model auditable by a regulator.
- Mandatory closure documentation. Each sub-phase closes with the synchronized update of the status, context, and audit log documents. Nothing is deferred to the next session.

## MRM Discipline in Software Development

TreeGov is not just a tool that *implements* MRM; the software itself is *built* under the same MRM discipline. This means:
- **Design before Code**: Every phase or sub-phase requires a formal design audit before a single line of code is written. The design document is the source of truth.
- **Human-in-the-Loop**: No autonomous agent runs unchecked. Every architectural decision, every state transition, and every numerical default is explicitly reviewed, challenged, and approved by the human modeller.
- **Adversarial Verification**: We assume the AI assistant can hallucinate. The AI is used as a co-auditor to challenge the human, but empirical verification (pytest, git diff, isolated environment tests) is always the final arbiter.
- **Immutable Traceability**: Every release, every change to a default, and every bug fix is documented in the audit log with its rationale, numerical impact, and regulatory citation before the commit is accepted.

## Development vs end use: two different data regimes

TreeGov is currently developed with public datasets (German Credit, UCI) and synthetic data. During development, the privacy rule is strict: no real data is ever sent to third-party AI APIs. Only *open-source* code, public documentation, and synthetic data are shared.

When TreeGov is used in production, the scenario is different: the analyst loads their own *CSV* with real data on their desktop, and the model is trained and evaluated locally. The data never leaves the analyst's machine. TreeGov has no server, no remote authentication, no database, and no internet connection at runtime.

This distinction has consequences that the project explicitly assumes:

- *DEBUG logs* contain sensitive information. When training on real data, the log records PD per node, leaf distributions, real *CSV* column names, model fingerprint, and file paths. The analyst must treat them as confidential material.
- Exported *HTML* reports contain sensitive information. Gains table, classification matrix, segment counts, PD per leaf. Sharing a report is sharing part of the model.
- The sensitive data policy is treated as explicit work. Before declaring the stable 1.0.0 version, the project plans a specific security and privacy audit block: log retention and cleanup, *GUI* warnings, and a document dedicated to the threat model.

Operational summary: during development, zero real data in AI APIs. In end use, the data remains on the analyst's desktop, under their responsibility and their institution's policies.

Note on population stability: while model training applies strict filters (e.g., excluding Indet/No Perf categories), stability monitoring (PSI/CSI) can and should be evaluated on the entire incoming population to capture true drift.

## How this maps to the design

The philosophy is not abstract: it translates into concrete design
decisions that are auditable in the source code.

- Clean-room architecture → `backend_v3/` has zero GUI imports;
  `frontend_v3/` has zero analytical logic. Enforced by an AST-based
  test (`test_frontend_clean_room`).
- White-box mathematics → Every statistical formula is written
  explicitly, with bibliographic citations (Kass 1980, Breiman 1984,
  Loh & Shih 1997, Cochran 1954). Black-box libraries (sklearn,
  statsmodels) are blocked at the interpreter level by
  `backend_v3/import_guard.py`.
- Native governance → `SplitConfig` is a *frozen dataclass* (immutable
  auditable evidence); `params_fingerprint` identifies every model
  uniquely; the DEBUG transactional logger records each decision.
- Optional governance, regulatory mode by default → `GovernanceMode`
  (BANKING / RESEARCH) makes the regulatory layer opt-out, opening the
  tool to non-banking domains (health, social sciences) without
  sacrificing MRM rigor where it matters. Although born in credit risk,
  TreeGov can be used in any domain where traceability, explainability,
  and governance are important.

---
*[Leer en español](philosophy.es.md)*
