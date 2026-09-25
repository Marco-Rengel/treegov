# TreeGov Philosophy

## The core sentence

> "Python gives you the engine. TreeGov gives you the engine, the brakes, the dashboard, the seatbelt, and the maintenance log. Which would you choose for a model that will be audited by the regulator?"

## Why TreeGov exists

There is a generation of risk analysts who need GUI tools to build auditable trees, and the tools that existed were discontinued without replacement. Statistical libraries and scripting environments offer analytical power, but not native governance. TreeGov fills that void.

## The differentiator

Governance is not an add-on. It is the starting point:

- Immutable configuration (frozen SplitConfig) = auditable evidence.
- Transactional DEBUG logging = regulatory traceability.
- White-box mathematics = citable and verifiable formulas.
- Black-box library blocking = auditability by design.

## Who it serves

- Credit risk analysts who want to spend time on analysis, not programming.
- MRM validation teams that need full traceability.
- Regulators who demand auditability of PD and classification models.

## Commitment

TreeGov does not compete on raw predictive accuracy. It competes on governance and auditability. If a bank needs XGBoost to gain 2 AUC points, it should use Python. If it needs a model that can be defended before a regulator, it uses TreeGov.

## Regulatory references

- Basel (BCBS CRE 20.39): PD Floors.
- EBA/GL/2017/16: PD/LGD parameter validation.
- IFRS 9: staging and ECL.
- SR 11-7 / OCC 2011-12: Model Risk Management.

## How this maps to the design

The philosophy is not abstract: it translates into concrete design
decisions that are auditable in the source code.

- **Clean-room architecture** → `backend_v3/` has zero GUI imports;
  `frontend_v3/` has zero analytical logic. Enforced by an AST-based
  test (`test_frontend_clean_room`).
- **White-box mathematics** → Every statistical formula is written
  explicitly, with bibliographic citations (Kass 1980, Breiman 1984,
  Loh & Shih 1997, Cochran 1954). Black-box libraries (sklearn,
  statsmodels) are blocked at the interpreter level by
  `backend_v3/import_guard.py`.
- **Native governance** → `SplitConfig` is a frozen dataclass (immutable
  auditable evidence); `params_fingerprint` identifies every model
  uniquely; the DEBUG transactional logger records each decision.
- **Optional governance, banking by default** → `GovernanceMode`
  (BANKING / RESEARCH) makes the regulatory layer opt-out, opening the
  tool to non-banking domains (health, social sciences) without
  sacrificing MRM rigor where it matters.

---
*[Leer en español](philosophy.es.md)*
