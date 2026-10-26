# TreeGov — Design Decisions

**Purpose.** This document records the *implementation decisions* that
shape TreeGov's behaviour but are not derivable from the mathematical
methodology alone. It is the missing link between `docs/methodology.md`
(what the formulas are) and the actual code (what the code does). For
every decision: context, alternatives considered, what was chosen, why,
and consequences.

**Audience.** MRM auditors, project maintainers, future contributors, and
the author six months from now. It is written so that a reader who only
reads the docs — never the code — can reconstruct why the model behaves
as it does.

**Companion documents.**
- `docs/methodology.md` — mathematical formulas with citations.
- `docs/api.md` — public API surface.
- `docs/audit_log.md` — chronological log of changes.
- `docs/roadmap.md` — phase plan.

**Status.** Living document. Any decision that changes the numerical
result, the API contract, or the architectural boundaries must add or
update an entry here. Cross-reference: `.treegovrules` (governance),
`CONVENTIONS.md` (operational conventions).

---

## §0. Domain, scope and target users

TreeGov was born as a credit-risk segmentation workbench. Its internal
vocabulary, defaults, and regulatory anchors come from banking
(Basel, IFRS 9, SR 11-7). Over time, it became clear that the analytical
core is domain-agnostic — CHAID, C&RT, QUEST do not care whether the
target is "default" or "diagnosis" — but the *presentation* is
credit-specific.

This section documents the coverage of two distinct user profiles, so
that the project is honest about what it does and does not cover today.

### 0.1 Credit-risk econometrician

**Profile.** A modeller in a bank or bureau who builds segmentation
models on default/attrition/prepayment, subject to MRM review.

**Needs and current coverage (as of v1.0.0a1, end of Phase 2):**

| Need | Covered? | Where |
|---|---|---|
| Decision-tree engines (CHAID / C&RT / QUEST) | ✅ | `backend_v3/*_engine.py` |
| White-box math with citations | ✅ | `docs/methodology.md` |
| MRM governance (Basel PD floors, SR 11-7) | ✅ | `GovernanceMode.BANKING` |
| OOS evaluation (Gini, KS, HL, Brier, ROC, PR-AUC) | ✅ | `backend_v3/validation.py` |
| OOT monitoring (PSI, CSI, Gini Drop) | ✅ | `backend_v3/stability.py` |
| Gains table + classification matrix | ✅ | `backend_v3/reporting.py` |
| HTML export of reports | ✅ | `frontend_v3/reports_panel.py` |
| **Sample weighting** (biased samples from bureaus) | ❌ | Planned: Phase 3.2 |
| **Indet / Insufficient / No Perf categories** | ❌ | Planned: Phase 3.3 |
| **Multiclass targets** (low/medium/high risk) | ❌ | Planned: Phase 3.1 |
| **Cost-optimal threshold** (IFRS 9 §8.6) | 🟡 | Formula documented, not implemented |
| **Monotonicity constraints** (age, income) | ❌ | Expert idea; not scheduled |
| **Champion-challenger** | ❌ | Phase 6 |
| **Batch scoring** (apply to full portfolio) | ❌ | Phase 6 |
| **Export to production** (SQL, pure Python) | ❌ | Phase 4 |

**Verdict.** A credit-risk econometrician **can use TreeGov today** for
exploratory modelling, metrics validation, and report generation on a
single development sample. The tool is **not yet production-ready** for
banking deployment until at least Phase 3.2 (weighting) and Phase 4
(export).

### 0.2 Biologist / social scientist

**Profile.** A researcher in ecology, health, or social sciences who
builds classification or regression trees on domain data. No regulatory
constraints; needs a clear, honest tool.

**Needs and current coverage:**

| Need | Covered? | Where |
|---|---|---|
| Decision-tree engines | ✅ | Same as above |
| **RESEARCH mode** (no Jeffreys, no PD floor) | ✅ | `GovernanceMode.RESEARCH` |
| **Multiclass targets** (species, diagnoses) | ❌ | Phase 3.1 |
| **Continuous targets** (regression trees) | ❌ | `TargetType.CONTINUOUS` exists but blocked by `TreeBuilder.build()` |
| **Class-imbalanced samples** | ❌ | Phase 3.2 (weighting) |
| **Regression metrics** (RMSE, MAE) | ❌ | Only binary metrics implemented |
| **Neutral vocabulary** (no "PD", "default", "bad/good") | ❌ | Phase 3.6.e |
| **Non-credit examples and datasets** | ❌ | Phase 3.6 |
| **Domain-agnostic documentation** | ❌ | This section is the first step |

**Verdict.** A biologist or social scientist **cannot use TreeGov with
real data today**. Reason: (a) multiclass is blocked by the builder,
(b) vocabulary is credit-specific, (c) no regression support, (d) no
non-credit example datasets. Fixing this requires Phase 3.1
(multiclass) and Phase 3.6.e (neutral vocabulary + examples).

**Honesty rule.** The README's regulatory notice says "not fit for
banking production". We should add an equivalent note for non-credit
domains: "not yet validated outside credit risk; see §0.2 for gaps".

### 0.3 MRM as an explicit choice, not an imposition

**Decision.** Governance is an opt-in mode, not a hidden default that
silently alters the mathematics.

**Alternatives considered.**
- **(a)** Always apply MRM (Jeffreys + floor). Rejected: hostile to
  non-banking users, violates the "no silent bias" principle.
- **(b)** Never apply MRM. Rejected: hostile to banking users, no
  regulatory anchor.
- **(c)** Two explicit modes, chosen by the user, labelled in the
  fingerprint. **Chosen.**

**Consequences.**
- `GovernanceMode.BANKING` (default): Jeffreys estimator + PD floor.
  Fingerprint suffix: `BANKING`.
- `GovernanceMode.RESEARCH`: raw empirical PD `k/n`, no smoothing, no
  floor. Fingerprint suffix: `RESEARCH`.
- Custom combinations reachable through the API: fingerprint suffix
  `CUSTOM`.
- Two trees trained on the same data with different modes **never share
  the same fingerprint**. This is the MRM evidence that the choice was
  explicit.

**Note on terminology.** The Python Enum class is `GovernanceMode.BANKING`
(kept for historical fingerprint compatibility and backward compatibility).
However, in business and GUI documentation, this is referred to as
"Regulatory mode" (Modo Regulatorio) because it applies to banks, credit
bureaus, and any regulated MRM environment. The fingerprint stores the
string `BANKING`.

### 0.4 Vocabulary policy

**Decision.** Internal identifiers (class fields, function names,
parameter names) keep the credit-specific terminology for historical
and backward-compatibility reasons. External surfaces (GUI labels, doc
strings, report headers, user-facing messages) will use **neutral
vocabulary** when the user selects a non-credit domain. This policy is
implemented progressively; Phase 3.6.e is the first concrete step.

**Rationale.** Renaming internal fields (e.g., `pd_final` → `score`)
would break the public API (`docs/api.md`), invalidate cached
fingerprints, and touch every test. The cost/benefit is negative. But
presenting a biologist with a GUI label that says "PD (final)" is also
unacceptable. Hence the split: internal stays, external translates.

**Neutral-vocabulary map (draft, to be finalised in 3.6.e):**

| Internal (credit) | External (neutral) |
|---|---|
| `pd_final` | Probability |
| `bad_rate` | Event rate |
| `n_bad` | Events |
| `n_good` | Non-events |
| "gains table" | Lift table |
| "default" (example target) | Outcome |
| "PD" (display) | Probability |

**Update (09/10/2026, Fase 3.1.c).** With the introduction of
mandatory `class_labels` (see §5.7), the analyst now provides
human-readable labels for every target class. These labels are
user input; TreeGov does not impose "Malo"/"Bueno" or any other
credit-specific default. The split is thus refined: internal
identifiers stay credit-specific (backward compat, fingerprints,
tests), while external *labels* — including the labels shown in
the target-class combo, reports, and the fingerprint — become
explicit user choices. This is the first concrete step toward the
full neutral-vocabulary mode planned for Phase 3.6.e.

### 0.5 Clean-Room Development and Academic Provenance

**Declaration.** TreeGov is a *Clean Room* development: every line of
its analytical logic derives exclusively from public academic
literature (Kass 1980; Biggs, de Ville & Suen 1991; Breiman et al.
1984; Loh & Shih 1997; Cochran 1954; and the other sources listed in
the README's Academic references) and from the documented classic
tree-station standard (circa 2001, transcribed in
`docs/3.11_classic_tree_ui_reference.md`). No third-party
implementation was read, copied, ported, or decompiled: all algorithms
are explicit, auditable mathematics, each one traceable to its
bibliographic source (see `docs/methodology.md` and the per-engine
docstrings).

**Consequences.**
- There are no black-box dependencies and no third-party algorithmic
  implementations: black-box libraries are blocked at the interpreter
  level by `backend_v3/import_guard.py` (hard rule in
  `.treegovrules`).
- Every formula carries its citation in the docstring; a formula
  without a citable source does not enter the codebase.
- Any logic that cannot be traced to an explicit, auditable
  mathematical formula is forbidden (governance rule replicated in
  `.treegovrules` and `AGENTS.md`).

---

## §1. Type and contract decisions

### 1.1 `SplitConfig` has no `cut_kind` field

**Context.** A split can be geometric (threshold) or categorical
(groups of labels). It would be natural to store this as a field.

**Decision.** `cut_kind` is a **derived property** (`CutKind.THRESHOLD`
if `threshold is not None`, else `CutKind.CATEGORY_GROUPS`), not a
stored field.

**Rationale.** Storing it would allow the field to disagree with the
actual shape of the split (threshold present but `cut_kind =
CATEGORY_GROUPS`). Deriving it enforces consistency by construction.
`SplitConfig` is frozen; adding a redundant field would also make the
freeze less useful.

**Consequences.** Callers read `cfg.cut_kind` (a property, not an
attribute). No change to the invariants in `__post_init__`.

### 1.2 `SplitConfig` has no reference to its node

**Context.** A `SplitConfig` is emitted from a node during tree
construction. It would be natural to store `node_id` inside the config.

**Decision.** `SplitConfig` does **not** know which node it belongs to.

**Rationale.** The same split configuration (same predictor, threshold,
child sizes, statistic) could appear at two different nodes with
identical characteristics. Making it node-agnostic keeps the config
as a pure "candidate partition" object; the *tree* holds the topology.

**Consequences.** Iterating over a `TreeModel` returns
`(node, split)` pairs. `SplitConfig` alone never locates itself.

### 1.3 `SplitConfig` invariants validated in `__post_init__`

**Context.** A malformed split (e.g., threshold and branches both
defined, negative degrees of freedom, `child_ns` sum exceeding
`parent_n`) would poison the tree downstream.

**Decision.** Every invariant is validated **at construction**, not
later.

**Rationale.** Fail-fast is a governance rule of the project. A
`SplitConfig` that exists is a `SplitConfig` that satisfies every
contract. Any downstream code can assume the invariants hold without
re-checking.

**Consequences.** Construction is slightly slower (negligible for the
volumes involved). Any buggy engine that tries to emit an invalid split
crashes immediately, with a message that pinpoints the cause. This is
documented in the class docstring.

### 1.4 Frozen dataclasses everywhere

**Context.** `SplitConfig`, `TestResult`, `TreeNode`, `TreeModel`,
`OOSMetrics`, `PSIReport`, `CSIReport`, `GiniDropReport`, `OOTReport`,
`GainsRow`, `GainsTableResult`, `ClassificationMatrix`, `PruneStep`,
`MergeStep`, `MergeDiagnostics`, `QuestSelection`, `SurrogateSplit`,
`ImputationSpec` — all frozen.

**Decision.** Immutability is a project-wide rule.

**Rationale.** (a) Hashability is required for `params_fingerprint`
construction. (b) Determinism requires that two trees built with the
same inputs be equal (`==`) by structural comparison. (c) MRM
traceability: an artefact, once emitted, cannot be silently mutated by
downstream code.

**Consequences.** Every update produces a new object (`dataclasses.replace`).
This is the reason `SessionState` transitions use `replace` (see
`session_state.py`).

---

## §2. Engine decisions — CHAID

### 2.1 Pair p-value computed on the 2×K pair sub-table

**Context.** During iterative merging, at each step we need a p-value
for each *pair* of current groups. Two natural choices:
- **(a)** Compute the p-value on the full (r × K) table, collapsing
  the other groups somehow.
- **(b)** Compute the p-value on the **2×K sub-table of the two groups
  being considered**, ignoring the other groups.

**Decision.** **(b)** — pair p-value on the 2×K sub-table.

**Rationale.** This is the Kass (1980) convention and it is replicated
by classic CHAID implementations. It isolates the association between
the two candidate groups, free from interference by the rest of the
table. Using (a) would require deciding what to do with the other
groups (average them? keep them? exclude them?), each with a different
interpretation.

**Consequences.** The merge step is well-defined and deterministic.
Documented in `chaid_engine.py` module docstring. Reference: Kass
(1980), *Applied Statistics* 29(2):119-127.

### 2.2 Cochran forced merges counted in c → r

**Context.** Cochran's rule (1954) triggers *forced merges* to satisfy
the expected-frequency condition of χ². Question: do forced merges
count for the Bonferroni multiplier `M(c, r)` computed **after** the
merging process ends?

**Decision.** **Yes** — forced merges count.

**Rationale.** The Bonferroni multiplier corrects for the number of
ways the original `c` categories could have ended up in `r` groups. A
forced merge is still a merge: the final `r` reflects the total number
of groups, regardless of *why* each merge happened. Excluding forced
merges would undercorrect the FWER.

**Consequences.** The final `p_value_adjusted` correctly reflects the
full search space. Documented in `chaid_engine.py`; no change to
`methodology.md` yet (this is one of the items to add in Phase 3.0.c).
Reference: Cochran (1954), *Biometrics* 10(4):417-451.

### 2.3 Exhaustive CHAID includes step 0

**Context.** Exhaustive CHAID merges pairs until only 2 groups remain,
recording a history of every intermediate state. The question is
whether the *unmerged* state (step 0) participates in the final
selection.

**Decision.** **Yes** — step 0 participates, with `M = 1` (no merges,
no correction).

**Rationale.** If the unmerged partition has the smallest adjusted
p-value, it means the predictor is *already* maximally associated with
the target without any merging. Excluding step 0 would force at least
one merge, distorting the result. This is the correct reading of
Biggs, de Ville & Suen (1991).

**Consequences.** A predictor can win with `n_merges = 0`. The
`bonferroni_multiplier` for that case is 1. Documented in
`chaid_engine.py`. Reference: Biggs, de Ville & Suen (1991), *Journal
of Applied Statistics* 18(1):49-62.

---

## §3. Engine decisions — C&RT

### 3.1 `min_impurity_decrease` default = 1e-9

**Context.** Impurity gain `ΔI` must exceed a threshold to justify a
split. The default is `1e-9`.

**Alternatives considered.**
- **(a)** `0` — accept any positive gain. Rejected: floating-point
  noise could accept a split with `ΔI = 1e-17` that has no analytical
  meaning.
- **(b)** A "sensible" threshold like `1e-6` or `1e-3`. Rejected: any
  choice would be arbitrary and domain-specific; users with different
  needs would have to override it anyway.
- **(c)** `1e-9` — near-zero but well above floating-point noise.
  **Chosen.**

**Rationale.** The parameter must exist for users to tune, but the
default should be "any mathematically meaningful gain is accepted".
`1e-9` is the smallest round value comfortably above the noise floor
for the sums-of-squares operations C&RT performs on typical credit
data sizes.

**Consequences.** Documented in `crt_engine.py` constructor and
docstring. Not added to `methodology.md` yet (item for Phase 3.0.c).

### 3.2 Surrogate agreement — quadrant identity

**Context.** A surrogate split on predictor `B` replicates the primary
split on predictor `A`. The agreement is the fraction of rows where
both assignments match (or both flip). Computing this requires counting
four quadrants: `(primary L/R) × (candidate L/R)`.

**Decision.** The four quadrants are computed explicitly and must
satisfy the identity:

    q_ll + q_lr + q_rl + q_rr = n_used

where `q_ab = |P_<a> ∩ C_<b>|` (P = primary, C = candidate).

**Rationale.** This is the source of a **critical bug** found in an
audit during Phase 1.2: a confusion of `q_lr` and `q_rl` inflated
agreement on asymmetric 2×2 tables. The fix rewrote the computation
with explicit quadrants. Making the identity an invariant in the code
prevents regression.

**Consequences.** The identity is documented in `crt_engine.py`. Test
suite includes explicit asymmetric fixtures that would fail if the
quadrants were confused again. See `docs/audit_log.md` entry of the
Phase 1.2 audit.

### 3.3 Surrogate retention rule

**Context.** Not every candidate that "sort of agrees" with the primary
should be kept as a surrogate. Keeping weak surrogates pollutes the
model.

**Alternatives considered.**
- **(a)** Keep any candidate with `agreement > 0.5`. Rejected: 0.5 is
  the trivial benchmark (predict all rows to the majority side of the
  primary); anything below has no information.
- **(b)** Keep any candidate with `agreement > majority_to_beat`,
  where `majority_to_beat = max(n_L, n_R) / n_used` of the primary.
  **Chosen.**

**Rationale.** The "majority rule" is the trivial baseline: always
predict the child that has more rows. A surrogate is only useful if it
*beats* this trivial rule. This is Breiman et al. (1984), §5.3.

**Consequences.** On highly asymmetric primaries (e.g., 90/10 split),
`majority_to_beat` is 0.9 — a hard threshold. On balanced primaries,
the threshold is close to 0.5. Documented in `crt_engine.py`.
Reference: Breiman et al. (1984), *Classification and Regression
Trees*, §5.3.

---

## §4. Engine decisions — QUEST

### 4.1 Bonferroni family M = 2J (vs canonical J) — CONFIGURABLE

**Context.** QUEST (Loh & Shih 1997) selects a variable via a
family-wise correction: `α / J`, where `J` is the number of predictors.
TreeGov's implementation runs **two** families of tests:
1. Tests on means/association (F or χ²).
2. Robust tie-breaker tests on variances (Brown-Forsythe).

**Alternatives considered.**
- **(a)** Canonical Loh & Shih: `M = J` (one family). Rejected as the
  default: would not correct for the second family.
- **(b)** TreeGov: `M = 2J` (two families, conservative). **Chosen as
  default.**

**Decision.** Default `M = 2J`. **This decision is now on the list
for Phase 3.0.g**, which will expose it as a parameter
`bonferroni_family: int = 2` (canonical: 1). Users needing the strict
Loh & Shih behaviour will set `bonferroni_family = 1`.

**Consequences.** TreeGov's QUEST is currently **more conservative**
than the canonical algorithm. It requires a stronger signal to select
a variable. Documented in `quest_engine.py`. This is one of the four
"canonical vs TreeGov" decisions identified in the Phase 3.0 audit.

### 4.2 Nominal high-cardinality — rate-based heuristic (vs dummies+LDA) — CONFIGURABLE

**Context.** For a nominal predictor with K > 10 categories, enumerating
all `2^(K-1) - 1` binary partitions is computationally infeasible.
Loh & Shih (1997) propose a different route (dummies + LDA).

**Alternatives considered.**
- **(a)** Canonical: dummies + LDA. Rejected: inconsistent with the
  rest of the codebase (C&RT already uses the rate-based heuristic);
  also adds a new statistical dependency (LDA) that would need its own
  documentation and audit.
- **(b)** Heuristic by class rate, sorted descending, cuts between
  adjacent positions. **Chosen.**

**Decision.** Rate-based heuristic. **On the list for Phase 3.0.g** as
`nominal_high_card: str = "rate"` (canonical: `"dummies_lda"`).

**Consequences.** The result for K > 10 differs from canonical QUEST.
Documented as a fidelity note in `quest_engine.py`. This is one of the
four "canonical vs TreeGov" decisions.

### 4.3 QDA root restricted to inter-means interval — CONFIGURABLE

**Context.** The QDA cutpoint is the root of a quadratic equation.
When both roots exist, the code accepts only roots in
`[min(m0, m1), max(m0, m1)]` — the interval between the two class
means.

**Alternatives considered.**
- **(a)** Canonical (Loh & Shih 1997): accept any real root.
- **(b)** Restrict to the inter-means interval. **Chosen.**

**Rationale.** A root far outside the inter-means interval produces a
cutpoint that does not respect the natural ordering suggested by the
data — practically, it would generate extreme cuts like "90% of the
data goes left". The restriction is a defensive choice, operational
rather than optimal.

**Consequences.** Some valid canonical roots are discarded; the code
falls back to the weighted midpoint in those cases. **On the list for
Phase 3.0.g** as `qda_root_restriction: bool = True` (canonical:
`False`). This is one of the four "canonical vs TreeGov" decisions.

### 4.4 Empirical priors π_k = n_k / N

**Context.** The QDA cut uses class priors. Two natural choices:
uniform (`π_k = 1/K`) or empirical (`π_k = n_k / N`).

**Decision.** Empirical priors.

**Rationale.** In credit scoring, the class proportions carry real
information (event rate is a business quantity). Using uniform priors
would ignore this. This is the natural reading of Loh & Shih (1997),
which assumes the sample reflects the population. The same reasoning
applies outside credit: the sample proportions are informative unless
there is an explicit reason to believe otherwise.

**Consequences.** The QDA boundary shifts toward the majority class,
consistent with the empirical prior. Documented in `quest_engine.py`.

### 4.5 QUEST multiclass extension — Stage 1 (K-group F) and Stage 2 (Gini sweep)

**Context.** QUEST (Loh & Shih 1997) is strictly binary in its
canonical formulation: Stage 1 uses a two-group ANOVA F (continuous
predictors) or a c×2 Pearson χ² (nominal), and Stage 2 uses a
univariate QDA cut. Phase 3.4.b opens QUEST to K ≥ 3 classes. Both
stages require an extension.

**Alternatives considered.**

- *Stage 1, one-vs-rest F*: K separate binary F-tests, take the minimum
  p-value. Rejected: multiplies the multiple-testing surface and breaks
  the Bonferroni correction logic in `_mk_selection`.
- *Stage 1, χ² for all predictors*: reject continuity, treat every
  predictor as nominal. Rejected: discards the ordinal/continuous
  structure of the predictor.
- *Stage 1, K-group F*: natural generalisation of the ANOVA F to K
  groups. Adopted.
- *Stage 2, multivariate QDA*: K×K covariance matrices. Rejected:
  introduces new mathematics not covered by `methodology.md`, breaks
  the univariate-split promise of QUEST.
- *Stage 2, one-vs-rest QDA*: K binary cuts per node. Rejected:
  breaks the single-cut-per-node promise.
- *Stage 2, Gini reduction sweep*: find the best binary cut for K
  classes, identical to what C&RT does. Adopted.
- *Tie-breaker, one-vs-rest Brown-Forsythe*: rejected, same
  multiplicity problem as one-vs-rest F.
- *Tie-breaker, K-group Brown-Forsythe*: natural generalisation of
  Levene's test. Adopted.

**Decision.** Two documented extensions, both preserving the K=2 parity
invariant.

- **Stage 1**. Replace the two-group F-test with the K-group F-test
  `F = (SSB / (K − 1)) / (SSW / (N − K))`. For K = 2 this reduces
  exactly to the current binary F. The nominal χ² is unchanged in
  form: it already operates on a c × K table.
- **Stage 1 tie-breaker**. Replace two-group Brown-Forsythe with the
  K-group version (Levene's z-scores, K-group ANOVA).
- **Stage 2**. Bifurcate by K:
  - K = 2 → existing QDA path (parity invariant).
  - K > 2 → Gini reduction sweep over the selected predictor.
    Continuous/ordinal: midpoints between consecutive distinct values.
    Nominal with k_cats ≤ 10: exhaustive over 2^(k_cats−1)−1 binary
    partitions (same kernel as C&RT). Nominal with k_cats > 10:
    rate-based heuristic on the modal class of the node (same
    convention as `crt_engine._rates_cls`).
- **New method `QuestEngine._gini_sweep_numeric`** duplicates ~12 lines
  of the sweep kernel in `CrtEngine._sweep_values`. Deliberate:
  deferred debt (extract to `backend_v3/tree_kernels.py` only if a
  third engine needs the same kernel).
- **No new fingerprint field**. The multiclass behaviour is a property
  of the model, not a configuration toggle. Already captured by
  `class_labels` / `n_classes` (Phase 3.1).

**Rationale.** K-group F is the natural generalisation preserving the
"predictor discriminates between classes" reading without new machinery.
The Gini sweep makes Stage 2 "find the best binary cut for K classes",
identical to C&RT; coherent with the tree builder's binary-split-per-node
contract.

**Fidelity note.** Documented deviation from canonical Loh & Shih (1997),
which is strictly binary. Mirrors the existing fidelity notes in §4.1
(Bonferroni family), §4.2 (nominal high-card), §4.3 (QDA restriction).

**Consequences.**

- QUEST produces valid K>2 trees through the same Session pipeline as
  CHAID and C&RT.
- `Session.train` no longer blocks any engine on class count.
- Downstream metrics (`validation.py`, `reporting.py`, `stability.py`)
  continue to block K>2 until Phase 3.5.
- K=2 parity verified by `test_quest_binary_parity_after_3_4`.
- `_prepare` relabels classes locally within each sub-node, avoiding
  empty columns that `pearson_chi2` rejects.

**References.**

- Loh, W.-Y. & Shih, Y.-S. (1997). *Statistica Sinica* 7(4), 815-840.
- Breiman, L. et al. (1984). *Classification and Regression Trees*.
- `docs/methodology.md` §3.8.
- `docs/3.4_design_multiclass_crt_quest.md` §3.1–§3.3.
- `docs/audit_log.md` 12/10/2026 (3.4.b).

---

## §5. Tree builder decisions

### 5.1 `min_child_size` as absolute floor per branch

**Context.** A split is only accepted if every child branch has at
least `min_child_size` rows. Alternatives:
- **(a)** Reject the split if any branch is too small (absolute floor).
- **(b)** Merge small branches with their siblings and retry.

**Decision.** **(a) Absolute floor.** If any child is too small, the
split is rejected entirely, and the node becomes a leaf.

**Rationale.** Merging small branches would produce "phantom" splits
that no longer respect the engine's mathematical criterion (the merged
partition was not what the engine proposed). Silent post-processing
would corrupt the audit trail: the code would report a split, but the
split as implemented would not match the split as computed.

**Consequences.** Trees are more conservative in their lower levels
(some potential splits are simply not taken). This is documented in
`tree_builder.py` and is one of the items to add to `methodology.md` in
Phase 3.0.c.

**Note on weighting.** Today, `min_child_size` counts rows. When
sample weighting is added in Phase 3.2, the question "does
`min_child_size` measure row count or weight mass?" will need an
explicit answer. Working hypothesis: row count (physical minimum for
statistical validity), with a possible future `min_child_weight`
parameter for weighted minima.

### 5.2 `TreeNode.pd_final` is a tuple (was scalar)

**Context.** `pd_final` is the operational probability vector for a
leaf. Before 3.1 it was typed `float` and restricted TreeGov to
binary targets.

**Decision (post 3.1).** `pd_final` is typed `tuple[float, ...]`,
one component per target class, in canonical order (index 0 =
`target_class`). The same applies to `pd_jeffreys` and `n_events`.

**Historical rationale (Phases 0/1).** Phase 0/1 was designed for
binary credit-risk modelling, where scalar PD dominates. Multiclass
was deferred: the engines supported it (CHAID uses χ² with K
classes; C&RT uses Gini impurity with K classes) but the container
(`TreeBuilder`, `TreeNode`) did not.

**Rationale for the change (Phase 3.1.a).** The biggest obstacle to
multiclass support — and, by extension, to non-credit use — was the
scalar `pd_final`. Phase 3.1.a converted it to a tuple, added a new
field `TreeNode.class_labels` (human-readable label per class), and
adapted every downstream consumer (`validation`, `reporting`,
`stability`, `tree_view`). The invariant `sum(pd_final) == 1` is
enforced at construction (`TreeModel.__post_init__`).

**Backward compatibility (K = 2).** For a binary target with
`target_class=1`, the tuple is `(pd_0, pd_1)` and `pd_final[0]` is
numerically identical to the pre-3.1 scalar. Consumers that read
`pd_final[0]` see no change.

**Consequences.** Non-binary targets are now reachable through the
tree-building pipeline (subject to engine restrictions; see §5.3).
Non-credit use (biology, social sciences) is unblocked at the
container level. Consumer code that read `pd_final` as a scalar must
read `pd_final[0]`.

### 5.3 `target_type` allows BINARY `{0,1}` or CATEGORICAL K≥3

**Context.** `TargetType` (see `types.py`) has three values: BINARY,
CATEGORICAL, CONTINUOUS. The engines handle all three. Before 3.1,
`TreeBuilder.build()` raised `ValueError` if `set(y) != {0, 1}`.

**Decision (post 3.1).** `TreeBuilder.build()` accepts:
- **BINARY** with strict encoding `{0, 1}` (K = 2).
- **CATEGORICAL** with any encoding, K ≥ 3 (multiclass).

It rejects:
- K < 2 (constant target, no split value).
- NaN in the target.
- BINARY with encoding different from `{0, 1}` (e.g., `{1, 2}` or
  `{-1, 1}`), for the same reason documented in §10.1 (the K=2
  binary parity invariant).

`TargetType.CONTINUOUS` remains blocked at the builder level
(regression trees deferred to a future phase).

**Rationale.** The non-negotiable invariant of Phase 3.1 (§10.1 of
`docs/3.1_design_multiclass.md`) is that a binary model with
`target_class=1` be **numerically identical** to the pre-3.1 model.
That invariant is guaranteed only if the binary encoding stays
strictly `{0, 1}`. For K ≥ 3, there is no pre-3.1 behaviour to
preserve, so any encoding is accepted.

**Reconciliation note (09/10/2026).** The original 3.1 design said
the binary validation would be "relaxed to K ≥ 2". During
implementation (Pasos 4.1-4.6) it was decided to **keep binary
strict at `{0, 1}`** and to **open multiclass only for K ≥ 3**. This
is stricter than the original design, not more permissive. The
K ≥ 3 case is genuinely new; the K = 2 case is deliberately
unchanged.

**Consequences.** A binary target that is not encoded as `{0, 1}`
must be recoded before `fix_spec`. This is documented in the error
message raised by `fix_spec`. A multiclass target with any encoding
is accepted.

**Deferred to a future phase.** Continuous regression targets
(`target_type=CONTINUOUS`), pending a decision on which metric to
attach to a leaf's "prediction" (mean? median? quantile?).

### 5.4 `grow_full` mode (`max_depth=None`)

**Context.** A tree needs a stopping rule. `max_depth` is one.
Alternative: grow until `min_child_size` blocks further splitting.

**Decision.** Both. `max_depth = None` triggers `grow_full`, which
grows until `min_child_size` stops the process. `max_depth` with a
positive integer triggers pre-pruning.

**Rationale.** `grow_full` exists to **feed the cost-complexity
pruning** (`pruning.py`): a pruned tree only makes sense if the
original tree is deep. Without `grow_full`, users cannot use pruning
effectively.

**Consequences.** This mode was promised in the docstring since Phase
1.2 but was broken: `TreeBuilder.__init__` called `int(max_depth)`
unconditionally, so `None` raised `TypeError`. The bug was found and
fixed in Phase 2.1 (see `audit_log.md`). Test
`test_grow_full_max_depth_none` covers it.

### 5.5 BFS growth with FIFO queue

**Context.** Tree construction can be depth-first (DFS, stack) or
breadth-first (BFS, queue).

**Decision.** BFS with a FIFO queue. `node_id` is assigned level by
level, in the order nodes are expanded.

**Rationale.** BFS yields a **deterministic, level-contiguous numbering**
convention: node 0 is the root, nodes 1..k are depth-1, and so on. This
makes the tree easy to inspect, easy to serialize, and easy to compare
between runs. DFS would produce a numbering that depends on child
ordering, less natural for auditing.

**Consequences.** Deep trees allocate more memory before producing
leaves (BFS holds all frontier nodes). For the sizes TreeGov handles
(thousands to hundreds of thousands of nodes), memory is negligible.
Documented in `tree_builder.py`.

### 5.6 Fingerprint includes `engine_params` and `governance_mode`

**Context.** The `params_fingerprint` is a 16-hex sha256 digest
identifying a model. Question: what exactly is hashed?

**Decision.** The fingerprint payload includes:
- method (CHAID, CRT, etc.);
- `engine_params` (all non-underscore, non-callable attributes of the
  engine instance);
- the spec (`{name: PredictorType.name}`);
- `max_depth`, `min_child_size`;
- `governance_mode` (effective: BANKING / RESEARCH / CUSTOM);
- `apply_jeffreys`, `pd_floor`;
- `seed`.

**Rationale.** Two trees with different hyperparameters, specs, or
governance modes are **different models**, even if trained on the same
data. The fingerprint must reflect this. Otherwise, an auditor could
mistake two substantively different models for the same one.

**Consequences.**
- Adding a new parameter to any engine automatically changes the
  fingerprint of future models.
- Changing governance mode changes the fingerprint even with identical
  data and parameters. This is intentional (see §0.3).
- The fingerprint is 16 hex (64 bits), not the full sha256 digest. This
  is documented in §10.1.

**Reference.** See `tree_builder.py::_fingerprint`.

### 5.7 `class_labels` is mandatory in `TreeBuilder` and `Session.fix_spec`

**Context.** When a tree is trained on a multiclass target, the
reports (gains table, confusion matrix), the GUI, and the fingerprint
all need a human-readable label for each class. A generic default
("Class 0", "Class 1") would be neutral but unhelpful. A silent
default drawn from the data ("0", "1") would be even worse: it hides
the analyst's semantic intent.

**Alternatives considered.**
- **(a)** No labels; derive them as `str(class_value)`. Rejected:
  unhelpful and hides intent.
- **(b)** Generic default `"Class {i}"`. Rejected: same problem.
- **(c)** Mandatory explicit labels from the analyst. **Chosen.**

**Decision.** `class_labels` is a mandatory keyword-only parameter in
both `TreeBuilder.__init__` and `Session.fix_spec`. It is a mapping
from every observed class value to a non-empty string. Missing keys,
extra keys, or non-string/empty labels raise `ValueError`. Duplicate
labels are allowed but produce a `WARNING` in the log.

**Rationale.** Making `class_labels` mandatory forces the analyst to
think about the semantics of each class at configuration time. This
mirrors the decision made for `target_class` (§5.6 and the parallel
reasoning in `docs/3.1_design_multiclass.md` §1bis). The labels are
domain-neutral: TreeGov does not impose credit-specific or
domain-specific values.

**Fingerprint.** The `class_labels` enter the `params_fingerprint`
payload (as a tuple of strings, in canonical order). Two trees with
the same data and hyperparameters but different labels produce
different fingerprints. Rationale: labels appear in reports and are
part of the model artefact identity.

**Consequences.**
- `Session.fix_spec` calls without `class_labels` fail with
  `TypeError` (missing required argument).
- The wizard (Phase 3.1.e) offers the observed classes with editable
  labels and row counts; the analyst confirms the mapping before
  training.
- Downstream consumers (`reporting`, `tree_view`) read
  `TreeNode.class_labels[c]` and `TreeModel.class_labels[c]` to
  display human-readable labels.
- Fingerprints computed before 3.1.c will not match those computed
  after, on the same data. Acceptable at v1.0.0a1 (alpha; no
  production models).

**Reference.** `docs/3.1_design_multiclass.md` §1bis.1 (target_class
mandatory), §1bis.2 (class_labels mandatory), §7.1 (fingerprint
changes).

---

## §6. Splitting and imputation

### 6.1 Hamilton-Hare largest remainder for stratification

**Context.** Splitting a dataset into train/test while preserving the
target distribution exactly (up to integer rounding) requires an
algorithm. Alternatives:
- **(a)** Random split with `train_test_split`. Rejected: introduces
  rounding noise in class proportions.
- **(b)** Round each class proportion. Rejected: independent rounding
  can over- or under-allocate the total.
- **(c)** Hamilton-Hare largest remainder. **Chosen.**

**Decision.** Hamilton-Hare per stratum: floor each ideal quota, then
distribute the remainder to the strata with the largest fractional
part (ties by ascending class code → deterministic).

**Rationale.** This is the exact-stratification convention used in
electoral apportionment. In credit scoring, the event rate in train
must match the population — it is a regulatory expectation (SR 11-7).
Random splits or naive rounding introduce drift that would be visible
in the audit trail.

**Consequences.** `stratified_split` returns positional indices
covering `0..N-1`; the train event rate matches the population rate
exactly when the allocation is feasible. Documented in
`backend_v3/splitting.py`. Deterministic given the seed.

### 6.2 Train-only imputation (anti-leakage)

**Context.** Missing values must be imputed with *something*. The
question is: which fold's statistics should feed the imputation?

**Alternatives considered.**
- **(a)** Compute means/modes over the full dataset. Rejected: data
  leakage. The model would "see" test-set information before
  evaluation.
- **(b)** Compute means/modes only on the training fold, apply the
  same values to test/OOS/OOT. **Chosen.**

**Rationale.** Anti-leakage is a hard rule in ML pipelines and a
regulatory requirement (SR 11-7). Computing statistics on data that
will later evaluate the model is a silent inflation of performance.

**Consequences.**
- `TrainOnlyImputer.fit` is called only on `X_train`.
- `transform` applies the fitted rules to any fold without
  recalculating.
- The imputer instance is retained in the `Session` cache so that
  `load_oot` can reuse it.
- Documented in `imputation.py` docstring and in `methodology.md` §5.

### 6.3 Mode tie-breaking — orderable → smallest, otherwise first-seen

**Context.** When the mode is tied between two or more labels, the
choice must be deterministic. Alternatives:
- **(a)** Use pandas' internal order. Rejected: not contractual;
  changes between pandas versions.
- **(b)** Sort labels and pick the first. Works only if labels are
  comparable.
- **(c)** Fall back to first-seen order when labels are not
  comparable. **Chosen.**

**Decision.** If labels are orderable (e.g., strings, numbers), pick
the smallest. If not (e.g., mixed types), pick the first one in the
order of appearance in the series.

**Rationale.** The fallback preserves determinism without imposing a
comparison that may raise `TypeError`. The "order of appearance" is
stable and reproducible.

**Consequences.** Documented in `imputation.py::_mode`. The behavior
is stable across pandas versions.

---

## §7. Validation and stability

### 7.1 Gini = 2·AUC − 1 convention

**Context.** Three different "Gini" conventions coexist in the credit
industry:
1. `Gini = 2·AUC − 1` (range −1 to 1).
2. `Gini = AUC − 0.5` (range −0.5 to 0.5).
3. The economic Gini coefficient (income inequality).

**Decision.** Convention 1 — `Gini = 2·AUC − 1`.

**Rationale.** This is the standard convention in credit scoring and
banking MRM (Siddiqi 2006). Using a different one would confuse
auditors and produce numbers that do not match industry reports.

**Consequences.** All internal Gini values follow this convention.
Documented explicitly in `methodology.md` §8.1 and in
`validation.py`. Confusion between the three conventions is common in
the industry; documenting the choice is an MRM traceability
requirement.

### 7.2 Hosmer-Lemeshow: `pi_g` clipped to [1e-15, 1-1e-15]

**Context.** Hosmer-Lemeshow divides the sample into G groups and
computes, per group, `π_g = mean(p_i)` and the χ²-like statistic:

    H = Σ_g (O_g − N_g π_g)² / [N_g π_g (1 − π_g)]

If `π_g` is exactly 0 or 1, the denominator is zero.

**Alternatives considered.**
- **(a)** Skip the group. Rejected: loses information, changes G.
- **(b)** Clip `π_g` to `[1e-15, 1−1e-15]`. **Chosen.**

**Rationale.** A model that predicts π = 0 or π = 1 for a group is
itself suspect; clipping keeps the statistic computable without
silently discarding the group. `1e-15` is above floating-point epsilon
but below any analytically meaningful probability.

**Consequences.** The HL statistic is always finite. Documented in
`validation.py` (constant `_HL_EPS`). Item to add to
`methodology.md` §8.3 in Phase 3.0.c.

### 7.3 PR-AUC as step-wise Average Precision

**Context.** Precision-Recall AUC admits multiple definitions
(trapezoidal, step-wise, interpolated).

**Decision.** Step-wise Average Precision, without trapezoidal
interpolation:

    AP = Σ_i (R_i − R_{i−1}) · P_i

**Rationale.** Davis & Goadrich (2006) show that linear interpolation
between operating points of a PR curve is incorrect (the interpolated
points are not achievable by any threshold). The step-wise sum is the
correct estimator for the expected precision under the empirical
distribution.

**Consequences.** TreeGov's `pr_auc` matches the standard definition
used by `sklearn.metrics.average_precision_score`, though the two
implementations are independent. Documented in `validation.py` and in
`methodology.md` §8.x (item to add in Phase 3.0.c). Reference: Davis
& Goadrich (2006), ICML.

### 7.4 PSI clip ε=1e-4 without renormalization — CONFIGURABLE

**Context.** The PSI (Population Stability Index) formula:

    PSI = Σ_k (p_act,k − p_exp,k) · ln(p_act,k / p_exp,k)

has a logarithm. When `p_act` or `p_exp` is 0 (e.g., a bin present in
train but not in OOT, or vice versa), the log is undefined.

**Alternatives considered.**
- **(a)** Clip and renormalize the probabilities to sum to 1.
  Rejected: hides the fact that a bin vanished, which is itself
  information (potential drift).
- **(b)** Clip without renormalizing. **Chosen.**

**Decision.** Clip ε = 1e-4, no renormalization.

**Rationale.** If a bin present in train disappears in OOT, the
correct signal is "this bin's probability dropped to ~0", not "the
distribution is unchanged except slightly renormalized". Renormalizing
would dilute the drift signal, which is precisely what PSI is meant to
detect.

**Consequences.** The overall PSI is slightly larger than under a
renormalized definition when bins vanish. The scale error is
negligible compared to the 0.10 / 0.25 thresholds when bins are
non-empty. **On the list for Phase 3.0.g** as
`psi_renormalize: bool = False` (canonical: `True`). Documented in
`stability.py`. Reference: Siddiqi (2006).

### 7.5 CSI deciles learned on train; open first/last bins

**Context.** CSI (Characteristic Stability Index) is PSI computed per
covariate. Continuous covariates must be binned. Question: how many
bins, and where are the cut points learned?

**Decision.**
- Cut points are the **deciles learned on the training partition**.
- The first and last bins are open (`−inf` and `+inf`) so that
  out-of-range OOT values land in the extreme bins instead of being
  silently dropped.
- For nominal covariates, categories observed in train define the bins;
  unseen OOT categories go into `<OTHER>` with `p_expected = ε`.

**Rationale.** Learning the bins on train is the anti-leakage rule
(see §6.2). Open extreme bins are a policy decision: an OOT value
outside the train range is genuine drift and should contribute to the
CSI, not vanish.

**Consequences.** CSI is always well-defined for continuous
predictors, and the extremes of the OOT distribution are captured.
Documented in `stability.py`.

### 7.6 `unseen_policy` default = 'error' in `predict_pd`

**Context.** During scoring, some rows may not route through the tree
(NaN residual, unseen category). Three policies:
- `"error"`: raise `ValueError`.
- `"majority"`: route to the most-populated leaf.
- `"exclude"`: mark as −1 (caller decides).

**Decision.** `predict_pd` default is `"error"`.

**Rationale.** A silent default (`"majority"` or `"exclude"`) would
hide a real problem: the model cannot score some rows. In a
production scoring pipeline, that is a critical issue that must
surface. The caller may override with `"exclude"` when transparency
("n_excluded" reported) is preferable.

**Consequences.**
- `Session.evaluate_oos` uses the default (`"error"`) — OOS assumes
  data compatible with training.
- `Session.evaluate_oot` uses `"exclude"` — OOT explicitly expects
  novel categories and reports them in `n_excluded`.
- Documented in `validation.py` and `session_state.py`. Item for
  `methodology.md` in Phase 3.0.c.

### 7.7 Symmetrized pairwise KS in multiclass (resolved in Phase 3.7.b)

**Context.** For K > 2, `compute_oos_metrics` reports per-pair KS values (`ks_pairs`) and their minimum as the aggregate `ks` (Phase 3.5, decision D4). Originally, the pairwise KS was computed unidirectionally (evaluating only `p_i` for `i < j`), which made it sensitive to the indexing order of secondary classes and asymmetric with respect to Hand & Till's AUC.

**Decision.** As of Phase 3.7.b, the pairwise KS is symmetrized by averaging both directions:
`KS_ij = 0.5 * (KS(p_i) + KS(p_j))`.
This aligns the KS with the Hand & Till AUC symmetrization logic.

**Consequences.** Reported `ks_pairs` and the worst-case `ks` for K > 2 are now direction-independent. For K = 2 the two directions coincide exactly (`p_1 = 1 - p_0`), so the binary KS is unaffected. This resolves the limitation previously scheduled for Phase 3.7.

---

## §8. Pruning

### 8.1 `r(t)` in count form (Breiman scale-invariant)

**Context.** Breiman's cost-complexity pruning defines `g(t)` as:

    g(t) = (R(t) − R(T_t)) / (|T_t| − 1)

where `R` can be expressed in two forms:
- **(a)** `R(t) = p(t) · r(t)` (probability-weighted).
- **(b)** `R(t) = r(t)` (raw counts).

**Decision.** **(b)** — raw counts.

**Rationale.** The two forms differ by a positive constant factor `p(t)`
common to the whole tree. The **sequence** of alphas (the order in
which nodes are pruned) is identical; only the units of alpha change
(errors per node, not errors per unit probability). Since the public
API is "prune at alpha X", not "prune at cost X", the choice of units
is a documented convention.

**Consequences.** The alpha values are on a different scale from a
naïve reading of Breiman's book. Documented in `pruning.py` and to be
added to `methodology.md` §7 in Phase 3.0.c.

### 8.2 Simultaneous tie pruning

**Context.** Multiple nodes may have the same minimal `g(t)`. Question:
prune them one at a time (recompute g after each) or all at once?

**Decision.** **All at once** — all nodes with `g(t) = min(g)` are
pruned in the same step.

**Rationale.** This is the standard Breiman (1984) convention for ties.
Pruning one at a time would change the sequence, and the order within
the tie would be arbitrary.

**Consequences.** The sequence of `PruneStep`s reflects simultaneous
prunings. Documented in `pruning.py`.

### 8.3 `prune(alpha)` idempotent, always from original

**Context.** Calling `prune(alpha)` twice — does the second call prune
from the already-pruned tree, or re-prune from the original?

**Decision.** Always from the **original** tree.

**Rationale.** The pruning sequence is a property of the original
tree. If `prune` accepted a pruned tree as input, the sequence would
depend on history, which is confusing and error-prone. Idempotence:
`prune(alpha)` returns the same tree regardless of how many times it
is called.

**Consequences.** `prune` never mutates the input `TreeModel` (which
is frozen anyway). The returned tree is a new object with re-indexed
nodes. Documented in `pruning.py`.

### 8.4 BFS re-indexing + `leaf_reason="podado"`

**Context.** After pruning, the node IDs of the surviving nodes are
non-contiguous. Question: keep the original IDs or renumber?

**Decision.** Renumber by BFS from the root: `0..m−1`, contiguous.

**Rationale.** `TreeModel.__post_init__` requires `node_id == index in
nodes tuple` (contiguity is part of the `TreeModel` contract). Breaking
it would violate a core invariant. BFS ordering is consistent with the
growth order (`TreeBuilder`).

**Consequences.** The reindexed tree is a valid `TreeModel`. Leaves
created by pruning receive `leaf_reason="podado"` (in Spanish,
consistent with the other leaf reasons). Documented in `pruning.py`.

### 8.5 Weighted pruning (`r_w(t)`) over physical counts

**Context.** The cost-complexity pruning originally used `r(t) = n - max(n_events)`. With the introduction of sample weights (Phase 3.2), the tree grows with weighted Gini, but the pruning still used physical counts. This created a statistical incoherence.

**Decision.** If `TreeNode.w_events` is populated, the Pruner uses `r_w(t) = sum(w_events) - max(w_events)`. If `w_events` is empty, it uses the original `r(t)`.

**Consequences.**
- Trees built with `weights=None` retain exact parity with the pre-3.9 behavior.
- Trees built with non-trivial weights now produce a pruning sequence coherent with their growth.
- The `Pruner.sequence()` API does not change; only the internal calculation of `g(t)` is adjusted.

**Nota sobre tipos (20/10/2026).** La anotación de `PruneStep.r_subtree` pasó de `int` a `float` para acomodar la masa ponderada. En árboles sin pesos, el valor sigue siendo numéricamente idéntico (paridad), aunque viaje como `float` (ej. `1.0` en lugar de `1`).

**Status (20/10/2026).** Implemented in `backend_v3/pruning.py` and verified by `tests/test_pruning.py`.

### 8.6 `Session.get_prune_sequence()` — exposing the analyst's discretion

**Context.** Classic interactive tree tools of the CART tradition allowed the analyst to see the cost-complexity sequence and decide where to stop. TreeGov's GUI had no such mechanism.

**Decision.** `Session` gains a read-only method `get_prune_sequence()` that returns a list of dicts (a flat DTO) representing `Pruner.sequence(model)`. This exposes `alpha`, `n_leaves`, and `r_subtree` to the frontend without breaking the clean-room architecture.

**Consequences.**
- The GUI can display a table of alphas.
- The analyst retains the discretion to choose the optimal tree size for their business case, complying with MRM human-in-the-loop principles.
- Fingerprints of pruned trees are derived from the original tree's fingerprint plus the alpha.

### 8.7 Interactive Pruning Dialog (GUI)

**Context.** The user needs a way to visualize the pruning sequence and apply an alpha.

**Decision.** The GUI implements a modal dialog `PruneDialog` accessible from the Model menu. The dialog presents a `QTableWidget` with the output of `Session.get_prune_sequence()`.
- When the user selects a row and confirms, the GUI calls `Session.prune(alpha)`.
- The tree viewer and metrics panel are refreshed.
- A button allows the user to revert to the original tree (if a pruned tree exists).

**Consequences.**
- The GUI reflects the backend's mathematical rigor while giving the analyst interactive control.
- No new analytical logic is introduced in `frontend_v3/`; it only consumes the DTO.

**Implementation Note (20/10/2026).** Al vincular el árbol podado al visor, se descubrió que `TreePanel.refresh()` solo re-renderiza el modelo existente. Para reflejar el nuevo `TreeModel` podado, el handler `_on_prune` del `MainWindow` debe llamar a `TreePanel.set_model(st.pruned_tree, mode)` en lugar de `refresh()`. Esta desviación está documentada en el docstring del handler y en el test E2E.

---

## §9. Reporting

### 9.1 Gains table by leaf — ascending PD (bureau convention)

**Context.** When building a gains table (one row per leaf), the
ordering of rows is a design choice.

**Alternatives considered.**
- **(a)** Descending PD (worst first). Common in some academic
  presentations.
- **(b)** Ascending PD (best first). **Chosen.**

**Rationale.** Bureau convention (Equifax, Experian, TransUnion) and
credit-scoring practice: the "best" segments appear first so that
cumulative statistics read top-down as "what happens if we approve
the top N% of applicants". Reversing the order would invert the
reading of `bad_rate_cum`, `lift_cum`, and the intercept of the
cumulative curve with the diagonal.

**Consequences.** `GainsTableResult.rows[0]` is the lowest-PD leaf.
`lift_cum` starts below 1 and rises; a well-behaved model crosses 1 at
the high-risk end. Documented in `reporting.py`.

### 9.2 Bucket tie-breaking — preserve (deterministic) vs random (needs seed)

**Context.** When bucketing rows by PD (`by="bucket"`), ties in PD
must be resolved. Alternatives:
- **(a)** Break ties randomly at every call.
- **(b)** Preserve all tied rows in the same bucket (may produce
  fewer than `n_buckets`).
- **(c)** Random with an explicit seed.

**Decision.** **(b) as default**; (c) available with `tie="random"`
requiring an explicit `seed`. (a) is never allowed.

**Rationale.** MRM requires determinism: two runs on the same data
with the same parameters must produce identical reports. Random
tie-breaking without a seed violates this. Preserving ties is
deterministic and reflects the natural structure of the data
(identical PDs from a tree come from the same leaf or cluster). The
"random with seed" mode exists for users who want exactly N buckets
and accept reproducible randomness.

**Consequences.** With `tie="preserve"`, the number of buckets can be
less than `n_buckets` if PDs are heavily tied. This is documented in
the `GainsTableResult` docstring and in the `build_gains_table`
docstring. Calling with `tie="random"` and no seed raises
`ValueError` (fail-fast).

### 9.3 Classification matrix threshold default = 0.5

**Context.** A classification matrix classifies each row as predicted
"bad" if its PD exceeds a threshold. Which default?

**Alternatives considered.**
- **(a)** `0.5` — the "natural" midpoint. **Chosen.**
- **(b)** The event rate of the training sample.
- **(c)** No default; force the user to choose.

**Rationale.** `0.5` is neutral: it is the boundary where predicted
"bad" becomes more likely than not. It is also the default in almost
every textbook and library, so it does not surprise a reader. Users
who need a business-optimal threshold (IFRS 9, §8.6 of
`methodology.md`) set it explicitly through the API.

**Consequences.** The default matrix reflects a symmetric 50/50
decision boundary. This is rarely the operational threshold in credit
scoring, but it is the right *default* to compute and then discuss.
Documented in `reporting.py`.

### 9.4 HTML export self-contained (no external assets)

**Context.** The `ReportsPanel` can export a report as HTML. Two
choices:
- **(a)** Reference external CSS/JS/images from CDNs or relative paths.
- **(b)** Embed all CSS inline, no external assets. **Chosen.**

**Decision.** Self-contained HTML.

**Rationale.** A report is meant to be archived, emailed, or attached
to a submission dossier. External references break when the recipient
opens the file offline, or when the referenced asset changes upstream.
Self-contained HTML is a stable artefact: what was reviewed is what is
preserved.

**Consequences.** The HTML file is larger (no shared CSS), and the CSS
must be maintained inside the Python string. This is acceptable
because the report CSS is small (~1 KB) and stable. Documented in
`reports_panel.py::_build_report_html`.

---

## §10. Governance and traceability

### 10.1 Fingerprint = sha256 truncated to 16 hex

**Context.** `params_fingerprint` is a digest of the model's
configuration. The full sha256 is 64 hex characters. Question: use the
full digest, or a truncation?

**Alternatives considered.**
- **(a)** Full 64-character digest.
- **(b)** Truncated to 16 characters. **Chosen.**

**Rationale.** The fingerprint is a human-readable identifier shown in
the GUI status bar, in the audit log, and in the `TreeNode` docstrings.
16 hex characters give 64 bits of entropy — enough to avoid collisions
for the realistic number of models a single user builds (millions of
models would still have < 1% collision probability). A longer digest
would be noisier to read with no practical benefit.

**Consequences.** The fingerprint is **not cryptographically secure**
against deliberate collision attacks. This is acceptable: the
fingerprint exists for human traceability, not for adversarial
integrity. Documented in `tree_builder.py::_fingerprint`.

### 10.2 BANKING/RESEARCH/CUSTOM distinction in fingerprint

**Context.** A tree trained under `GovernanceMode.BANKING` differs
numerically from one trained under `RESEARCH` (Jeffreys + floor vs raw
PD). Two trees with the same data and hyperparameters but different
modes must be distinguishable.

**Decision.** The fingerprint payload includes a `governance_mode`
field with values:
- `"BANKING"` — Jeffreys estimator with PD floor.
- `"RESEARCH"` — raw empirical PD, no floor.
- `"CUSTOM"` — any other combination (e.g., Jeffreys without a floor).

**Rationale.** Two models that look identical in the GUI (same data,
same engine) but produce different PDs would be a governance trap.
Making the mode part of the fingerprint ensures they never collide.

**Consequences.** Changing governance mode produces a new fingerprint
without changing anything else. This is intentional: the fingerprint
identifies the *model*, not the dataset. Documented in
`tree_builder.py::_governance_label`.

**Note on terminology.** The Python Enum class is `GovernanceMode.BANKING`
(kept for historical fingerprint compatibility and backward compatibility).
However, in business and GUI documentation, this is referred to as
"Regulatory mode" (Modo Regulatorio) because it applies to banks, credit
bureaus, and any regulated MRM environment. The fingerprint stores the
string `BANKING`.

### 10.3 Event log — append-only, no timestamps in memory

**Context.** `SessionState.event_log` records the sequence of state
transitions. Two design questions:
- Where do timestamps live?
- Can entries be removed?

**Decision.**
- **No timestamps** in the in-memory `event_log`.
- **Append-only** by construction (`tuple` concatenation).
- The **file logger** (via `log_config`) carries the ISO 8601
  timestamps.

**Rationale.** Timestamps in the in-memory log would break
determinism: two sessions with the same operations but different
wall-clock moments would have different `event_log` values, so
`SessionState` comparisons in tests would fail. Keeping the in-memory
log time-free makes it a **structural** trace; the time-stamped
version lives in the file log.

**Consequences.** `SessionState.event_log` is deterministic and
hashable. The audit trail in the file log carries timestamps. This
split is documented in `session_state.py` module docstring.

### 10.4 Default PD floor value and the sovereign exception (Phase 3.8)

**Context.** The Basel Framework (CRE 32.4) sets a hard PD floor of
0.05% (5 bps) for corporate, bank, and retail exposures. Sovereign
exposures are exempt or subject to a 0.03% floor depending on the
jurisdiction.

**Decision.** TreeGov's default `pd_floor` in Banking mode is **0.0005**
(0.05%), applying to all non-sovereign exposures. The sovereign
exception is deliberately **not modelled** as an automatic branch.

**Rationale.** TreeGov is designed for banking and credit bureau use
cases where corporate/retail exposures dominate. Hard-coding a
sovereign branch would add API complexity for a niche case. Analysts
with sovereign exposure must pass `pd_floor=0.0003` explicitly.

**Consequences.**
- Default fingerprints changed in Phase 3.8 (expected, as `pd_floor`
  is part of the payload).
- Analysts must be aware of the sovereign exception (documented in
  `methodology.md` §6.3 and in the wizard's `step4_govmode_banking_desc`).

---

## §11. Decisions to expose as parameters (Phase 3.0.g scope)

The audit in Phase 3.0 identified four decisions where the TreeGov
implementation deviates from the canonical literature. In each case,
the deviation is documented and deliberate — but a user might
legitimately want the canonical behaviour. Phase 3.0.g will expose each
as a parameter, keeping the current behaviour as the default so that
existing models remain reproducible.

| # | Decision | Current default (TreeGov) | Canonical alternative | Parameter (implemented) |
|---|---|---|---|---|
| 1 | QUEST Bonferroni family (§4.1) | `M = 2J` | `M = J` | `bonferroni_family: int = 2` |
| 2 | QUEST nominal high-cardinality (§4.2) | rate-based heuristic | dummies + LDA | `nominal_high_card: str = "rate"` |
| 3 | QUEST QDA root restriction (§4.3) | restricted to `[min, max]` | unrestricted | `qda_root_restriction: bool = True` |
| 4 | PSI renormalization after clip (§7.4) | not renormalized | renormalized | `psi_renormalize: bool = False` |

**Design principles.**

1. **Defaults preserve current behaviour.** A user who does not touch
   the parameter gets the same model as before. No silent change.
2. **Canonical mode is one parameter away.** `bonferroni_family = 1`,
   `nominal_high_card = "dummies_lda"`, `qda_root_restriction = False`,
   `psi_renormalize = True`.
3. **Fingerprint reflects the choice.** All four parameters enter
   `engine_params` (for QUEST) or the stability configuration, so two
   models with different choices get different fingerprints.
4. **Documentation follows the code.** `docs/methodology.md` gains a
   subsection per parameter ("TreeGov default vs canonical
   behaviour"), and the parameter is highlighted in `docs/api.md`.
5. **Tests cover both modes.** For each parameter, at least one test
   exercises the canonical setting and asserts that the output
   matches the alternative expectation.

**Scheduling.** Phase 3.0.g follows the documentation closure
(3.0.b-3.0.e). It is small (~1 session) and unblocks the QUEST
multiclass work in Phase 3.4 by removing the risk of silently
diverging from canonical QUEST behaviour when that phase opens up the
engine to more target types.

**Status (04/10/2026).** All four parameters are implemented as of
Phase 3.0.g. Defaults preserve the pre-3.0.g behaviour; canonical mode
is one parameter away; fingerprints (for QUEST) reflect the choice.
See `docs/audit_log.md` entry of 04/10/2026 for the implementation log.

---

## §12. GUI presentation decisions

### 12.1 Clear-content pattern in repaintable panels (`setParent(None)` + `deleteLater()`)

**Context.** `MetricsPanel` and `ReportsPanel` rebuild their entire
content on every `refresh()` by emptying their layout. In Qt,
`takeAt()` detaches a widget from the layout but NOT from the widget
parent tree: the widget remains a child of the panel, and
`findChildren` still returns it, until the event loop processes the
pending `deleteLater()`. In headless environments with
`QT_QPA_PLATFORM=offscreen` and no explicit `processEvents()` calls,
that interval can be arbitrarily long and produces false positives in
tests that inspect the panel (for example, `_badges()` in
`tests/test_e2e_mainwindow.py` found a badge that should already have
been removed). This surfaced in Phase 3.1.f.2, when the negative-Gini
badge of `MetricsPanel` — legitimately painted, then cleared by a
session reset — kept appearing to `findChildren` and broke
`test_e2e_new_wizard_resets_panel`.

**Alternatives considered.**

- (a) Call `app.processEvents()` in every test after a `refresh()`:
  discarded. It couples the tests to event-loop details and does not
  remove the problem in production.
- (b) Call `widget.hide()` before `deleteLater()`: discarded.
  `findChildren` would still find the widget (hidden but present).
- (c) `widget.setParent(None)` + `widget.deleteLater()`: chosen.
  Detaches the widget from the parent tree immediately and delegates
  the actual destruction to the event loop — the standard Qt pattern.

**Decision.** Option (c). Applied in `MetricsPanel._clear_content`
(sub-step 3.1.f.2).

**Consequences.**

- The widget becomes orphaned immediately. Any code holding a
  reference to a widget after `refresh()` must tolerate its `parent()`
  being `None` (expected behaviour).
- `findChildren` over the panel no longer finds deleted widgets.
  Tests may assume a clean state right after `refresh()`.
- The pattern MUST be replicated in any future panel that uses the
  same clear + rebuild mechanism (for example, if `ReportsPanel`
  follows the same scheme).

**Cross-reference.** This decision was not in the original 3.1.f plan
and was applied during implementation; it is recorded here per the
project's "no grey zones" policy (Phase 3.0) and follows the usual
context / alternatives / decision / consequences structure.

---

## §13. Sample weighting decisions (Phase 3.2)

### 13.1 Weighted median — interpolation at exact half-mass

**Context.** `_weighted_median` in `backend_v3/statistics.py` returns
the weighted median of a group. When the cumulative weight of the
sorted observations reaches exactly half of the total weight, a
convention is needed to decide which value to return.

**Alternatives considered.**

- (a) Return the observation where the cumulative weight crosses the
  half (the first one whose cumulative weight is greater than or equal
  to the half), without interpolating. The classic survey-analysis
  convention (Heeringa, West & Berglund 2010, §5.3). This was the definition written in the original 3.2.a
  plan.
- (b) Average that observation with the next one. The NumPy
  convention (linear percentile). It coincides exactly with
  `numpy.median` when all weights are equal, including even-length
  groups.

**Decision.** Option (b) — interpolation. Implemented in
`_weighted_median`.

**Rationale.** With uniform weights, `numpy.median` of an even-length
group averages the two central values. If `_weighted_median` with
uniform weights returned only the first one, `brown_forsythe` with
uniform weights would produce a result slightly different from
`brown_forsythe` without weights, breaking the C1 parity invariant
(`weights=None` must be bit-identical to pre-3.2 behaviour, and
all-ones weights must match the unweighted path). Interpolation
preserves parity.

**Consequences.**

- `brown_forsythe(g1, g2, weights=(ones, ones))` numerically matches
  `brown_forsythe(g1, g2)`.
- The convention is documented in the `_weighted_median` docstring
  and covered by the test
  `test_weighted_median_equal_weights_even_length`.
- Users expecting the alternative first-crossing convention can obtain it with their
  own implementation; it is not offered as a parameter because parity
  is more important than compatibility with other conventions.

**Cross-reference.** `backend_v3/statistics.py::_weighted_median`;
`docs/audit_log.md` entry of 10/10/2026 (Fase 3.2.a).

### 13.2 Pearson χ² on weighted tables — scale sensitivity

**Context.** With non-trivial sample weights, the Pearson χ² statistic
computed over a contingency table whose cells are weight sums scales
linearly with the total weight mass: if all weights are multiplied by
k, the χ² is multiplied by k. The F statistic, by contrast, is a ratio
and is scale-invariant. Consequence: in CHAID with a binary target,
two analysts with the same sample but rescaled weights would obtain
different χ² values and different p-values.

**Alternatives considered.**

- (a) Automatically normalize the weights so they sum to n (the number
  of physical rows) before any computation. Rejected: it hides a
  decision from the analyst and breaks the parity invariant when the
  analyst has already normalized on their own.
- (b) Keep the standard behaviour and document it: the scale is the
  analyst's responsibility. Adopted.
- (c) Add a `normalize_weights` parameter in `Session.fix_spec`.
  Rejected for now: it enlarges the API surface without a clear need.
  If real usage demands it, it will be added in a later sub-phase.

**Decision.** Option (b). Standard complex-survey behaviour (Heeringa,
West & Berglund 2010, §5.4). TreeGov reports; it does not decide
silently.

**Consequences.**

- Documented in `docs/methodology.md` §1.9bis.
- The analyst may normalize their weights before uploading the CSV if
  they want χ² to behave as if the effective sample size were n.
- This behaviour also applies to QUEST with nominal predictors (same
  Pearson χ²); it will be documented again in 3.2.d.
- C&RT is unaffected: it uses weighted Gini proportions and weighted
  variance, both scale-invariant.

**Cross-reference.** `backend_v3/chaid_engine.py`;
`docs/methodology.md` §1.9bis; `docs/audit_log.md` entry of 10/10/2026
(Fase 3.2.b).

### 13.3 C&RT surrogates — agreement is not weighted

**Context.** In C&RT, surrogates are secondary splits that replicate
the left/right assignment of the primary split. Phase 3.2 introduces
sample weights. The question is whether the agreement computation
(proportion of coincidences between the primary's assignment and the
candidate's) should be weighted.

**Alternatives considered.**

- (a) Weight the agreement using the same weights as the gain.
  Rejected: agreement counts binary label coincidences (each row goes
  left or right in both splits; coincidence is yes or no). There is no
  statistical quantity to accumulate per row; weighting it would
  produce a number with no clear interpretation.
- (b) Do not weight the agreement. The embedded `SplitConfig` does
  evaluate the genuine gain with weights. Adopted.

**Decision.** Option (b). `_best_agreement` and `_agreement_nominal`
are untouched. `_embedded_split` does compute the weighted gain,
because that gain is an impurity and impurities are weighted.

**Rationale.** The general principle of 3.2: what gets weighted is
the mass contributing to a statistical quantity (impurities, χ², F,
proportions). What stays untouched is structure (branch orientation,
label coincidence, number of merges in CHAID). This separation is
consistent with the CHAID decision to weight the cells but not the
Kass multiplier.

**Consequences.**

- The surrogate ranking by agreement is identical without weights and
  with uniform weights.
- With non-trivial weights, the ranking may differ from the unweighted
  ranking only through the set of accepted surrogates, never through
  the agreement values themselves: both the agreement and the
  `majority_to_beat` threshold are computed on physical row counts
  (label coincidences), so neither is weighted. The retention
  criterion (`agreement > majority_to_beat`) is therefore entirely
  weight-free; weights only affect the embedded split's gain.
- Covered by the tests
  `test_weighted_crt_surrogate_parity_with_uniform_weights` and
  `test_weighted_crt_surrogate_embedded_child_ns_physical`.

**Cross-reference.** `backend_v3/crt_engine.py`; `docs/audit_log.md`
entry of 10/10/2026 (Fase 3.2.c).

---

### 13.4 Weighted variance divisor — W − 1 vs W

**Context.** In sample weighting, the variance of a group admits two
standard definitions:

- Weighted sample variance: `sum(w_i * (x_i - m)^2) / (W - 1)`,
  where `W = sum(w_i)`. "Weights as frequencies" convention.
- Weighted population variance: `sum(w_i * (x_i - m)^2) / W`.
  "Weights as mass" convention.

The choice affects the QUEST QDA formula (Stage 2), because the
variances enter the coefficients of the quadratic equation.

**Alternatives considered.**

- (a) Divisor `W - 1` (weighted Bessel). The standard convention
  when weights are frequencies in complex survey analysis
  (Heeringa, West & Berglund 2010, §5.3). It is NOT weight-scale
  invariant: if the weights are multiplied by `k`, the denominator
  goes from `W - 1` to `k·W - 1`, which is not `k·(W - 1)`.
- (b) Divisor `W` (mass). It is weight-scale invariant: the ratio
  `(k · S) / (k · W)` = `S / W`. But it underestimates the variance
  in small samples (no Bessel bias correction).

**Decision.** Option (a) — divisor `W − 1`. It is the standard
convention for weights as frequencies and gives unbiased variance
estimates.

**Rationale.** The Bessel correction exists so that the sample
variance is an unbiased estimator of the population variance. The
same reasoning applies when weights are frequencies. The `W`
alternative is mathematically cleaner regarding scale invariance,
but introduces bias. We prefer unbiasedness over strict invariance.

**Consequences.**

- The QUEST QDA threshold is not weight-scale invariant. Documented
  as a mathematical finding in the audit_log entry of 10/10/2026
  (Phase 3.2.d) and in the `_qda_cutpoint` docstring.
- Covered by the test `test_weighted_quest_qda_variance_uses_w_minus_one`.
- This behaviour coexists with other already documented scale
  sensitivities: χ² scales linearly (§13.2), F is invariant
  (SSB/SSW ratio). The analyst is responsible for choosing the
  weight scale; TreeGov reports but does not decide silently.

**Cross-reference.** `backend_v3/quest_engine.py::_qda_cutpoint`;
`docs/design_decisions.md` §13.2; `docs/audit_log.md` entry of
10/10/2026 (Phase 3.2.d).

---

### 13.5 TreeNode.w_events — informative field with empty default

**Context.** Sample weighting (Phase 3.2) introduces the weighted
mass per class in each tree node. A decision is needed on how to
expose that mass in `TreeNode` without breaking the ~30 tests that
build `TreeNode` by hand (pruning, reporting, validation,
tree_view, etc.).

**Alternatives considered.**

- (a) Add `w_events: tuple[float, ...]` as a mandatory field.
  Rejected: breaks manual `TreeNode` construction in all existing
  tests and forces updating ~30 fixtures.
- (b) Add `w_events: tuple[float, ...] = ()` with an empty default.
  Adopted. Tests that build `TreeNode` by hand keep working
  unchanged. Nodes produced by `TreeBuilder` always populate it.
  `TreeModel.__post_init__` validates consistency only when the
  field is non-empty.
- (c) Derive `w_events` from `n_events` when not specified.
  Rejected: there is not enough information to distinguish "node
  without weights" from "node with all-ones weights" without
  consulting the builder's mode, which is not available in the
  `TreeModel`.

**Decision.** Option (b).

**Rationale.** The golden rule of Phase 3.2 is "no weights, exact
parity". Adding a mandatory field would force touching every test
and would increase the risk of introducing subtle changes in the
unweighted path. The empty default is Python's standard mechanism
for backward-compatible extensions.

**Consequences.**

- `TreeNode.w_events` is `()` in hand-built nodes without declared
  weights; it is a populated tuple in nodes produced by
  `TreeBuilder`.
- Length validation (`== K`) and non-negativity apply only to nodes
  with non-empty `w_events`.
- `w_events` is purely informative: it does not alter routing, does
  not alter pruning (`pruning.py` does not read it), does not alter
  downstream metrics.
- Documented in `docs/audit_log.md` entry of 10/10/2026 (Phase
  3.2.e).

**Cross-reference.** `backend_v3/tree_builder.py::TreeNode`;
`docs/design_decisions.md` §5.2 (pd_final tuple); `docs/audit_log.md`
entry of 10/10/2026 (Phase 3.2.e).

**Update (18/10/2026, Fase 3.7.c).** `min_child_weight`, introducido en
la Fase 3.2.e como parámetro interno de `TreeBuilder`, se expone ahora
en la firma pública de `Session.train` y en el asistente gráfico
(paso 4, "Gobierno y parámetros"). Sigue siendo opcional y su default
(`None`) preserva la paridad bit a bit con el comportamiento pre-3.2:
solo tiene efecto numérico cuando la sesión es ponderada
(`weight_col` declarado en `fix_spec`). En el wizard, el valor 0.0
equivale a "desactivado" (el acceso `GovernancePage.min_child_weight()`
devuelve `None` en ese caso), y la descripción emergente explica que
la opción solo aplica con una columna de pesos declarada en el paso 2.

---

### 13.6 Session-level weighting decisions

#### 13.6.1 Check B2 (≥2 rows per class per side) is conditional on weights

**Context.** The original Phase 3.2 design introduced a "B2" check:
after partitioning, verify that each observed class has at least 2
physical rows in train and in test. The intent was to defend against
extreme weights that concentrate all the mass in a few rows and
leave a class with 0 rows in some partition. Design v2 §1bis.2
stated that B2 applied "always, with and without weights".

**Alternatives considered.**

- (a) Unconditional B2. Breaks `test_largest_remainder` (fixture
  with a class of only 3 rows, 1 in test) and violates the C1
  invariant of Phase 3.2 ("no weights, behaviour identical to
  pre-3.2").
- (b) B2 only when `weights is not None`. Adopted. The weight-free
  behaviour is preserved intact; the weighted mode gains the
  specific defense.
- (c) B2 as a warning instead of an error. Rejected: a warning goes
  unnoticed in noisy logs; explicit failure is preferable in
  weighted mode.

**Decision.** Option (b).

**Rationale.** C1 is the priority invariant. B2 is a defense specific
to the weighted mode, not a general behaviour. With Hamilton-Hare
over row counts, a class with `n_k >= 2` cannot end up with 0 rows
in any partition; B2 is only necessary when weights can make a
class's mass collapse into very few rows.

**Consequences.**

- `test_largest_remainder` (historical fixture with a small class)
  keeps passing unchanged.
- Degenerate fixtures in existing tests do not need to be enlarged.
- Test enshrining the invariant:
  `test_weighted_splitting_check_b2_not_applied_without_weights`.

**Cross-reference.** `backend_v3/splitting.py::stratified_split`;
`docs/audit_log.md` entry of 10/10/2026 (Phase 3.2.f).

#### 13.6.2 Stratification with weights: row counts, not weighted quotas

**Context.** Design v2 §1bis.2 stated "stratify by accumulated weight
of each class (Hamilton-Hare over W_k instead of n_k)". The literal
implementation of that sentence leads to a bug: the quota
`Q_k = W_k * train_frac` is WEIGHT, not rows, and translating it
directly into rows produces `floor(Q_k) > n_k` when weights are
extreme.

**Alternatives considered.**

- (a) Translate the weighted quota into rows with
  `n_k_target = round(n_k * train_frac)`. It is the correct
  translation of "stratify by weight" into "stratify in rows":
  weight does not change the proportion of rows going to train;
  weights travel with each row and affect the model, not the
  partition.
- (b) Normalize weights to sum = n before stratification. Rejected:
  introduces a silent engine decision the analyst did not ask for.
- (c) Stratify over the weight vector as if they were frequencies
  (without translating to rows). This is the implementation that
  failed; see context.

**Decision.** Option (a) — classic Hamilton-Hare over `n_k * train_frac`.

**Rationale.** Stratification exists so that train and test have
class proportions similar to the population. With row counts, that
proportion is preserved exactly. The weighted mass is not a property
of the partition: it is a property of the rows composing each
partition, and it travels with them. Introducing weight into the
partition formula doubles its effect (once in stratification, once
in training) and produces degenerate failures.

**Consequences.**

- The split (idx_train, idx_test) is numerically identical with
  weights and without weights, given the same seed.
- Weights are separated as sub-vectors after the split
  (`_w_train`, `_w_test`, `_w_oot`) and travel with each row to the
  `TreeBuilder`.
- Test enshrining the invariant:
  `test_weighted_splitting_split_unchanged_by_weights`.
- Corrects the statement in design v2 §1bis.2; the split does not
  depend on the weights.

**Cross-reference.** `backend_v3/splitting.py::stratified_split`;
`docs/audit_log.md` entry of 10/10/2026 (Phase 3.2.f).

---

### 13.7 Deferred: KS / AUC / Gini of the gains table are not weighted

**Context.** `build_gains_table` in `backend_v3/reporting.py` returns
`ks`, `auc` and `gini` computed over per-row PD of the routable
rows. In 3.2.g, weighted `w_*` columns were added to the table
rows, but the three aggregate statistics remained unweighted. The
reason is that `_discrimination_metrics` is a local reimplementation
of formulas already present (and already weighted) in
`backend_v3/validation.py`.

**Alternatives considered.**

- (a) Weight `_discrimination_metrics` in 3.2.g. Rejected: would
  duplicate the weighted logic of `validation.compute_oos_metrics`
  in a different module, with divergence risk.
- (b) Replace `_discrimination_metrics` with a call to
  `validation.compute_oos_metrics`. Rejected in 3.2.g: would change
  the design of `reporting.py` (currently self-contained) and would
  affect a module not planned in the phase.
- (c) Defer the weighting of KS/AUC/Gini to a future sub-phase.
  Adopted.

**Decision.** Option (c). In 3.2.g the aggregate statistics of the
`GainsTableResult` are still computed unweighted. The `w_*` columns
of the table rows ARE weighted; the aggregate summary
(KS/AUC/Gini) is not.

**Consequences.**

- With `weights=None`: behaviour identical to pre-3.2. Parity is
  preserved.
- With non-trivial weights: the `w_bad_rate_cum`, `w_lift_cum`,
  etc. columns reflect the weighted mass, but the result's
  `ks`/`auc`/`gini` remain those of row counts.
- Documented as an explicit deferred decision: the future sub-phase
  that addresses full weighted reports (probably within Phase 3.5,
  multiclass + weighted reports) must decide whether to reuse
  `validation.compute_oos_metrics` or reimplement the weighting
  locally.

**Cross-reference.** `backend_v3/reporting.py::_discrimination_metrics`;
`docs/audit_log.md` entry of 10/10/2026 (Phase 3.2.g).

**Update (20/10/2026, saneamiento documental).** La decisión diferida D13 sigue pendiente de implementación en código para el path binario: con pesos no triviales, los campos `ks`, `auc` y `gini` de `GainsTableResult` continúan calculándose sin ponderar, mientras que las columnas `w_*` por fila sí reflejan la masa ponderada. Esa asimetría es la que el panel OOS/OOT y los Reports/HTML exponen como contradicción numérica para la misma partición. La nota de "Deferred" del 10/10/2026 se mantiene en lo esencial.

Lo que se aclara aquí es que la Fase 3.5.b (15/10/2026) **sí resolvió la asimetría para el path multiclase**: `build_gains_table` con K > 2 delega en `validation.compute_oos_metrics`, que sí pondera, cerrando el diferido para ese path. La asimetría restante es, por tanto, exclusiva del path binario (K = 2) y no se extiende al multiclase. La Fase 3.5.b no reabre D13: la acota. El diseño de D13 y su test de paridad deben formularse sobre el path binario, no sobre el multiclase.

**Referencia cruzada.** `docs/3.5_design_multiclass_weighted_reports.md` §1.2 ("D13 closes the deferred §13.7 for the multiclass path only"), `docs/audit_log.md` entrada del 15/10/2026 (3.5.b), y `docs/estado_proyecto.md` §10 ("Deudas post-rc1").

**Update (20/10/2026, cierre D13).** La deuda D13 queda resuelta. El path binario de `build_gains_table` ya no usa la implementación local `_discrimination_metrics`, sino que delega en `_pair_auc_ks` (de `validation.py`), que soporta ponderación de forma nativa. De este modo, las métricas de cabecera (KS, AUC, Gini) respetan los pesos de muestra en ambos paths (binario y multiclase), eliminando la contradicción numérica con el panel OOS/OOT. Se ha eliminado la duplicación de lógica de AUC/KS.

---

### 13.8 Hosmer-Lemeshow scales linearly with total weight mass

**Context.** The HL formula is
`H = Σ_g (O_g − N_g π_g)² / [N_g π_g (1 − π_g)]`. With weights, the
three per-group aggregates (`O_g`, `N_g`, `π_g`) become weighted
sums. Under a uniform rescaling of the weights (multiplying all by
k), both the numerator and the denominator scale linearly with k,
so H scales linearly with k. It is the same behaviour as the
weighted Pearson χ² documented in §13.2.

**Alternatives considered.**

- (a) Normalize weights so that Σw = n before HL. Rejected for
  consistency with §13.2: the general decision of Phase 3.2 is not
  to normalize silently.
- (b) Document the scaling and leave the decision to the analyst.
  Adopted.

**Decision.** Option (b). HL is not scale-invariant; it scales
linearly with the total weight mass. Test
`test_weighted_validation_scale_invariance` (3.2.g) enshrines the
scaling, not the invariance.

**Rationale.** It is mathematically inevitable behaviour when weights
enter as mass (weighted sums) and not as counts. The alternative
(normalizing) would hide an analyst decision.

**Consequences.**

- With uniform weights (all 1) and without weights: identical HL
  (C1 parity).
- With non-trivial weights: HL can grow large if Σw is large. The
  test's p-value drops artificially. The analyst must know that HL
  weighs mass, not rows.
- Also documented in `docs/methodology.md` §8.9bis.

**Cross-reference.** `backend_v3/validation.py::compute_oos_metrics`;
`docs/design_decisions.md` §13.2 (χ² scaling); `docs/audit_log.md`
entry of 10/10/2026 (Phase 3.2.g).

---

### 13.9 evaluate_oot parameter is `weight_oot`, not `use_train_weights`

**Context.** Design v2 §5.3 proposed the name `use_train_weights`
for the `Session.evaluate_oot` parameter that controls the weighting
mode of the OOT cohort. During the implementation of 3.2.h it was
detected that the name is ambiguous: it suggests "apply the train
weights to the OOT", which makes no operational sense because train
and OOT have different sizes and different rows.

**Alternatives considered.**

- (a) Keep `use_train_weights`. Rejected: ambiguous.
- (b) Rename to `weight_oot: bool = True`. Adopted. Semantics:
  True = the OOT uses its own weights; False = the OOT uses uniform
  weights.

**Decision.** Option (b).

**Rationale.** The name describes the real operational question
("does the OOT weight with its own weights?"), not an impossible
propagation mechanism.

**Consequences.**

- `Session.evaluate_oot(*, n_groups=10, weight_oot=True)`.
- The `_commit` event records `weight_oot=false` when applicable.
- Also documented in the method's docstring.

**Cross-reference.** `backend_v3/session_state.py::evaluate_oot`;
`docs/audit_log.md` entry of 10/10/2026 (Phase 3.2.h).

---

### 13.10 PSI / CSI weighting: each cohort carries its own weights

**Context.** OOT monitoring (`stability.py`) compares the
distribution of tree leaves and of each covariate between train
(reference) and the OOT cohort. Under sample weighting, the
question is which weights to use in each cohort.

**Alternatives considered.**

- (a) Use the train weights for both cohorts. Measures only model
  drift, ignoring the OOT population change. Available via
  `weight_oot=False`.
- (b) Use each cohort's own weights: train with train weights, OOT
  with OOT weights. Measures both changes: the population one and
  the model one. Adopted as default.

**Decision.** Option (b). Default `weight_oot=True`.

**Rationale.** Design v2 §5.3 B4 option 1 approved this convention.
The intent is for PSI/CSI to capture the full drift, not only the
part concerning the model. Option (a) remains available for the
analyst who wants to isolate model drift.

**Consequences.**

- If train and OOT have the same population composition, the
  weights match and PSI reflects only the change in the model's
  distribution.
- If they differ (real population drift), PSI captures both
  changes.
- `weight_oot=False` forces uniform weights in OOT (equivalent to
  ignoring the OOT cohort's bias).
- Test `test_weighted_stability_parity_uniform_weights` enshrines
  parity with uniform weights.

**Cross-reference.** `backend_v3/stability.py::StabilityMonitor.report`;
`docs/design_decisions.md` §13.9; `docs/audit_log.md` entry of
10/10/2026 (Phase 3.2.h).

---

## §14. Population category decisions (Phase 3.3)

### 14.1 The population filter is opt-in, mirroring sample weighting

**Context.** Phase 3.3 introduces a population-category filter: an
optional auxiliary CSV column whose values determine which rows
participate in training and evaluation. The question is whether the
filter is mandatory (the analyst must always declare a population
column) or opt-in (the analyst declares it only if the dataset has
one).

**Decision.** Opt-in. With `population_col=None`, the session behaves
identically to the pre-3.3 pipeline. Invariant C1 is preserved.

**Rationale.** Mirrors the sample-weighting decision of Phase 3.2:
both features are auxiliary metadata that only apply when the analyst's
data has the corresponding column. Forcing the declaration would break
existing datasets and tests for no benefit.

**Consequences.** Every consumer of the population filter must handle
`population_col is None` explicitly. The `Session` caches
`_pop_col`/`_pop_ok_values` are `None` in the opt-out case. The
`fix_spec` signature gains two keyword-only parameters with defaults, so
existing callers continue to work unchanged.

### 14.2 Whitelist semantics: everything not declared OK is an exclusion

**Context.** A population column can contain many values (`OK`,
`INDET`, `INSUFFICIENT`, `NO_PERF`, plus values the analyst has never
seen). The question is how to interpret values not in the declared
whitelist.

**Alternatives considered.**

- (a) Blacklist: exclude the declared values, include everything else.
  Rejected: silently includes new values introduced by a data refresh,
  which is the exact opposite of fail-fast MRM.
- (b) Whitelist: include only the declared values, exclude everything
  else. Chosen.

**Decision.** Whitelist. Any value not in `population_ok_values` is an
exclusion reason, and its value appears verbatim in the
`population_breakdown`.

**Rationale.** Two intentional consequences: (1) a new value in the CSV
is never silently included; the analyst sees it in the breakdown and
decides; (2) a typo in the whitelist is visible: if the analyst
declares `("OKk",)` instead of `("OK",)`, every row is excluded and
`fix_spec` fails on the `K_ok >= 2` check. This is the fail-fast
principle of `docs/design_decisions.md` §0.3 applied to the population.

**Consequences.** The breakdown is a complete partition of the excluded
set, ordered deterministically by descending count and then ascending
value. No row is counted twice, no row is missed.

### 14.3 `train_idx` / `test_idx` remain relative to the original `_df`

**Context.** When the population filter is active, only a subset of the
CSV participates in the partition. The question is whether
`train_idx`/`test_idx` are positions relative to the original `_df` or
to the filtered view.

**Decision.** Relative to the original `_df`. The filter is applied
upstream of `stratified_split`; the split returns positions relative to
the filtered view, and they are mapped back via
`ok_indices[idx_rel]`.

**Rationale.** Auditability: any external reference to "row 42 of the
CSV" remains valid across the session lifecycle. A row excluded by the
population filter is still uniquely identified by its CSV index. If the
indices were relative to a filtered view, an auditor reconstructing
the pipeline from the audit trail would need the exact filtering rule
to interpret them.

**Documented semantic change.** Before 3.3, `train_idx ∪ test_idx`
always covered all rows of the CSV. After 3.3, it covers only the OK
rows when the filter is declared. This is a documented breaking change
on the meaning of the union, not on the type.

**Consequences.** Tests that assert
`len(train_idx) + len(test_idx) == N` must adapt to
`len(train_idx) + len(test_idx) + n_excluded_population == N` when the
filter is declared, or add `population_col=None` to the fixture.

### 14.4 The OOT flat DTO renames `n_excluded` to `n_excluded_routing`

**Context.** Before 3.3, the OOT flat DTO exposed a key `n_excluded`
that meant "rows that could not be routed through the tree". With 3.3,
a second, distinct exclusion exists: rows excluded by the population
filter. The two must not be confused.

**Decision.** Rename the existing flat key to `n_excluded_routing`. Add
`n_excluded_population` and `population_breakdown`. The inner
`OOTReport` dataclass keeps its field name `n_excluded`; only the flat
DTO representation changes.

**Rationale.** The flat DTO is what the frontend and any external
consumer sees. An ambiguous key would be silently misinterpreted. The
rename forces the consumer to choose. The inner dataclass stays stable
to avoid breaking the Python-level API.

**Consequences.** Documented breaking change on the flat DTO only,
mirroring how Phase 3.1 broke the flat DTO by changing `pd_final`
shape. Tests that read `dto["oot"]["n_excluded"]` are updated to read
`n_excluded_routing`.

### 14.5 Mirror rule extended to a triad: target / weight / population

**Context.** Before 3.3, the wizard had a binary mirror rule: the target
column is not available as a predictor. Phase 3.2 added a second
auxiliary column (`weight_col`) with the same rule. Phase 3.3 adds a
third (`population_col`).

**Decision.** Generalize the rule to a triad: target, weight column,
and population column are all excluded from the predictor list. Any two
of them cannot be the same column, and none can be a declared
predictor.

**Rationale.** Each auxiliary column plays a specific role that is
orthogonal to prediction. Using any of them as a predictor would leak
information into the tree (the weight, the exclusion rule, or the
target itself).

**Consequences.** `PredictorsPage._on_target_change` and
`_on_weight_change` and `_on_population_change` must each exclude the
other two. The `fix_spec` validation in `Session` rejects any
combination where `population_col` equals `target` or is a declared
predictor.

---

## §15. UI Presentation Decisions (Phase 3.10.a)

### 15.1 3-level Palette Hierarchy in Dark Theme (H8)
**Contexto:** El tema oscuro original tenía solo dos niveles (BG y SURFACE), lo que resultaba en una falta de jerarquía visual (los paneles no se distinguían del fondo).
**Decisión:** Se introdujo un tercer nivel (`SURFACE_ELEVATED`) inspirado en VS Code Dark+. Las reglas QSS aplican este nivel a los paneles laterales, menús flotantes y tooltips.
**Consecuencia:** Mayor claridad visual sin salir de la paleta oscura. Los tests de contraste se mantienen.

### 15.2 Enriched Tree Nodes with HTML (H4)
**Contexto:** Los nodos del árbol eran cajas de texto plano. El prototipo Antigravity sugería un diseño más denso en información.
**Decisión:** Se migró `NodeItem` de `setPlainText` a `setHtml`. El HTML permite renderizar cabeceras de color, mini-barras de proporción y métricas adicionales (Gini, p-valor) dentro del nodo sin añadir lógica analítica en el frontend (los datos siguen viniendo precalculados del backend en el `TreeNode`).
**Consecuencia:** Los nodos miden 180x100 (antes 150x64). El auto-fit del zoom se ajustó para respetar el `ZOOM_MIN` con la nueva geometría.

---

## §16. CHAID continuous predictors — binning (Phase 3.10.b)

### 16.1 Bins as ORDINAL
Los predictores continuos binned se tratan internamente como variables ORDINAL. Esto permite la fusión de categorías adyacentes (convención de Kass 1980) y evita que el motor trate los intervalos numéricos como categorías sin orden.

### 16.2 Binning without weights
El cálculo de los cortes (deciles) usa `np.quantile` sin ponderar, incluso si la sesión es ponderada. Las métricas de asociación (χ²/F) y las matrices de contingencia sí usan los pesos. Se documenta como deuda técnica: en futuras iteraciones, si el sesgo muestral es extremo, se podría implementar un binning ponderado.

### 16.3 Routing: bins to consolidated branches
El `TreeBuilder` no crea un nodo hijo por cada bin individual (lo que resultaría en 11 hijos fijos). En su lugar, mapea cada bin a la rama consolidada que el motor CHAID determinó tras el proceso de fusión. Esto garantiza que el árbol construido refleje la estructura final y mantenga la integridad de `child_ns`.

---

## §17. Layout and Theme Decisions (Phase 3.11.a)

### 17.1 Google Colab Theme
**Contexto:** El tema oscuro previo (VS Code Dark+ con jerarquía de 3 niveles, §15.1) y el claro no compartían una paleta coherente, y los diálogos nativos (wizard, QMessageBox) ignoraban parcialmente el QSS bajo el estilo nativo de Windows.
**Decisión:** Se eligió la paleta de Google Colab (Dark/Light) por su familiaridad para los analistas (similar a VS Code/Colab) y se forzó el estilo `Fusion` (`app.py`) para que los QDialog respeten el QSS. Las paletas viven en `frontend_v3/theme.py` (`PALETTES`) y se aplican por sustitución de tokens `$TOKEN` sobre `resources/styles.qss`, con fail-fast si queda algún token sin resolver.
**Consecuencia:** Un único template QSS sirve a ambos temas; los `QGraphicsItem` (que ignoran el QSS) se recolorean explícitamente desde la paleta activa en cada render.

### 17.2 Excel-like Tabs
**Contexto:** El área central usaba un `QSplitter` vertical con el canvas del árbol arriba y las pestañas (Ganancias/Riesgos/Reglas/Resumen) ancladas en una franja inferior de 100-200 px, demasiado estrecha para trabajar los reportes.
**Decisión:** Se sustituyó el `QSplitter` vertical por un `QTabWidget` principal. Motivo: maximizar el espacio del árbol y evitar que el usuario tenga que redimensionar manualmente los paneles. Cada pestaña (Árbol, Ganancias, Riesgos, Reglas, Resumen) ocupa TODO el área central, como una hoja de Excel; la pestaña 0 hospeda el canvas real del árbol.
**Consecuencia:** Los reportes y métricas ganan toda la altura de la ventana; el canvas deja de competir por píxeles con la barra de pestañas. El cambio de pestaña programático (`setCurrentWidget`) sigue llevando al analista a "Riesgos" tras evaluar OOS/OOT.

### 17.3 Bounded Properties Panel
**Contexto:** El panel derecho de propiedades (HUD) podía expandirse sin límite arrastrando el handle del splitter, llegando a sobredimensionarse frente al área de trabajo.
**Decisión:** El panel derecho se acotó a un máximo de 400px (mínimo 200px) y se conectó al menú Ver para poder ocultarlo (`_act_toggle_hud` → `setVisible`), priorizando el espacio del canvas. Tamaños iniciales del splitter principal: 250/800/300 (izquierda/centro/derecha).
**Consecuencia:** El canvas central siempre conserva la mayor parte del ancho de la ventana; el HUD sigue accesible pero no puede dominar el layout.

---

## §18. GUI Presentation Decisions (Phase 3.11.a.1)

### 18.1 QPainter nodes (no HTML)
**Contexto:** Los nodos HTML de la 3.11.a (`QGraphicsTextItem.setHtml()`) dependían del auto-ajuste del motor de rich text: la caja se medía DESPUÉS de renderizar el contenido, lo que dejaba huecos muertos dentro de la tarjeta, rompía la geometría fija del layout y obligaba a sondar `QTextDocument` para conocer el tamaño real. Además, cada cambio de zoom re-renderizaba HTML en todos los nodos.
**Decisión:** `NodeItem` se reescribió pintándose ENTERAMENTE con `QPainter` (sin HTML), con geometría fija `NODE_W × NODE_H` (220×126 px): cabecera de 26 px (banda semáforo/`ACCENT`, texto blanco bold elidido), filas por clase, fila Total (N), barra apilada de 10 px y footer de 20 px, todas ancladas a coordenadas exactas dentro del bounding rect. El cuerpo es blanco puro en ambos temas (metáfora de "hoja de auditoría": el nodo es un documento, no un widget tematizado).
**Consecuencia:** El layout (`_layout_tree`) usa las constantes del módulo directamente — cero medición de contenido, cero espacio vacío; el render es más barato (primitivas de pintura en lugar de documentos HTML) y cada banda tiene posición exacta y auditable. Verificado con tests pixel-level y de geometría en `tests/test_tree_view.py`.

### 18.2 QPalette forzada en ventanas nativas
**Contexto:** Bajo el estilo nativo de Windows, el chrome de `QWizard`/`QDialog` (cabecera, marcos de botones, texto deshabilitado) heredaba el modo claro/oscuro DEL SISTEMA OPERATIVO, no el tema de la aplicación: el wizard mostraba cabecera oscura en tema claro y texto ilegible en tema oscuro.
**Decisión:** Además del QSS por tokens (§17.1), se fuerza una `QPalette` construida desde la paleta activa (`theme.apply_palette()`, roles Window/WindowText/Base/AlternateBase/Text/Button/ButtonText/Highlight/HighlightedText + grupo Disabled), aplicada en el arranque y en cada cambio de tema. El wizard se ancla además al estilo `Fusion` (`QStyleFactory.create("Fusion")` con referencia viva) y a `QWizard.WizardStyle.ClassicStyle`, porque `AeroStyle` delega la cabecera y la botonera al tema del SO.
**Consecuencia:** Diálogos y asistente siguen el tema de la app en ambos modos, independientemente del modo de Windows. Misma política fail-fast que `render_stylesheet`: tema desconocido → `ValueError`.

### 18.3 Copia TSV al portapapeles en tablas de datos
**Contexto:** Las tablas de la GUI (tabla de ganancias, secuencia de poda) mostraban datos de auditoría que el analista necesitaba trasladar a Excel/Word; no existía vía de exportación rápida distinta del reporte HTML.
**Decisión:** Toda tabla de datos soporta Ctrl+C vía `QShortcut(QKeySequence.StandardKey.Copy, tabla, context=WidgetWithChildrenShortcut)`, copiando la selección (o la tabla completa si no hay selección) como TSV: cabeceras en la primera línea, celdas separadas por `\t`, filas por `\n` (REGLA CRÍTICA 4.1.1 de `docs/3.11_gui_design_system.md`). El contexto acotado es obligatorio para no secuestrar Ctrl+C de otros widgets de la ventana.
**Consecuencia:** Pegado directo en Excel/Word sin exportar archivo. Implementación de referencia genérica en `ReportsPanel._copy_selection_to_clipboard` (acepta cualquier `QTableWidget`; desde el 25/10/2026 es `@staticmethod` para compartirla sin acoplar instancias, y su fallback "sin selección → toda la tabla" itera las celdas directamente porque `selectAll()` es no-op en `SelectionMode.SingleSelection`). Cobertura actual: tabla de ganancias ✅ (con test), `PruneDialog` ✅ (25/10/2026, con test), matriz 2×2 exenta (`NoSelection`).

### 18.4 Layout clásico con pestañas inferiores (sobre el "Excel puro")
**Contexto:** La 3.11.a (§17.2) llevó las pestañas a página completa con la barra ARRIBA (posición por defecto de `QTabWidget`). La reescritura del diseño 3.11 al estándar clásico de estaciones de árboles (circa 2001) exigía la ergonomía operativa completa: barra de menús clásica, panel izquierdo de tres bloques y la barra de pestañas anclada ABAJO.
**Decisión:** Se adoptó el layout clásico: barra de 8 menús (File, Edit, View, Format, Analysis, Tree, Window, Help — los cuatro últimos con placeholders deshabilitados asignados a 3.11.c/d), toolbar compacta `IconOnly` 16×16 con tooltips obligatorios, panel izquierdo `QSplitter` vertical con 3 `QGroupBox` apilados (Project Explorer / Tree Map / Data Viewer) y `QTabWidget` principal con `TabPosition.South` (pestañas inferiores, metáfora de hojas de Excel conservada pero ancladas abajo).
**Consecuencia:** La disposición coincide con la referencia visual del estándar clásico (`docs/3.11_classic_tree_ui_reference.md`) y con el diseño 3.11 reescrito (§2); las pestañas siguen ocupando toda el área central (la ganancia de espacio de §17.2 se conserva) y la barra inferior deja la franja superior para menús y toolbar, como en la estación clásica.

### 18.5 Cabecera de nodo: "Node <id>" / "Nodo <id>" vía tr()
**Contexto:** El brief visual pedía el literal fijo `"Nodo {id} — "` en la cabecera del nodo, lo que habría bloqueado la retraducción en caliente (el prefijo quedaría siempre en español).
**Decisión:** La cabecera se compone vía `tr("tree_prop_node")` ("Node"/"Nodo"): en un nodo terminal es estrictamente `Node <id>` / `Nodo <id>`; en un nodo interno se añade ` — <predictor>`. Terminología obligatoria del Estándar Clásico de Estaciones de Árboles (circa 2001): "Nodo" / "Nodo terminal"; queda prohibido "Hoja/Leaf" en los textos visibles de la GUI.
**Consecuencia:** La cabecera se retraduce en caliente con el resto de la escena (mismo `refresh()`); en ES produce exactamente el literal del brief.

### 18.6 Footer de nodo terminal: solo Gini (sin KS)
**Contexto:** El brief visual pedía "Gini + KS" en el footer de los nodos terminales, pero `TreeNode` no expone KS y calcularlo en el frontend violaría la sala limpia (capa analítica pura en `backend_v3/`).
**Decisión:** El footer de un nodo terminal muestra solo el Gini del nodo (derivado de `pd_final`, presentación sin pandas); los nodos internos muestran p-valor ajustado + estadístico del split (precomputados por el backend). Añadir KS requeriría un campo nuevo en `TreeNode` (cambio de contrato de backend; no hay fase que lo exija).
**Consecuencia:** Cero cálculo analítico en `frontend_v3/tree_view.py`; el footer es auditable campo a campo contra el backend.

### 18.7 Empty dict vs RuntimeError en get_data_preview (Phase 3.11.b.1)
**Contexto:** La familia de lecturas puras `describe_*` de `Session` (`describe_dataset`, `describe_target`, `describe_weight_column`, `describe_population_column`) lanza `RuntimeError` cuando no hay dataset cargado (`session_state.py`: guardas al inicio de cada método). Para el Data Viewer (decisión D3 del diseño auditado `docs/3.11.b_design_treemap_dataviewer.md`, corrección O3), el frontend necesita pintar un estado vacío simple (tabla sin datos) sin capturar excepciones en el flujo normal de arranque de la ventana.
**Decisión:** `Session.get_data_preview(n_rows=50)` devuelve el dict vacío `{"columns": [], "rows": [], "n_total": 0, "truncated": False}` cuando `self._df is None`, en lugar de lanzar `RuntimeError`. Además, toda celda se serializa a tipo nativo de Python (`int`/`float`/`str`/`bool`) y los valores ausentes del CSV (`pd.isna`) como `None`: cero escalares numpy/pandas en el retorno, dict JSON-serializable (requisito O3 de la auditoría del diseño).
**Consecuencia:** El frontend (3.11.b.2) distingue "sin dataset" con una sola comprobación (`n_total == 0`), sin `try/except`; el contrato es testeable sin Qt y queda listo para serialización JSON en la futura capa MCP (Fase 5). La divergencia queda acotada a este método: la familia `describe_*` mantiene su semántica fail-fast sin cambios.

### 18.8 Matriz de costos en SessionState sin fingerprint (Phase 3.11.c.3)
**Contexto:** La Fase 3.11.c introduce una matriz de costos de clasificación errónea N×N (asimétrica; filas = clase real, columnas = clase predicha) editada en el wizard (pestaña "Costs" del `AdvancedOptionsDialog`) y almacenada en `SessionState.cost_matrix` como tupla de tuplas inmutable. La regla general de gobernanza dice "un modelo con parámetros distintos es un modelo distinto" (params_fingerprint único), lo que sugeriría incluir la matriz en el fingerprint.
**Decisión:** La matriz se almacena en `SessionState` para trazabilidad y se expone en los reportes, pero NO entra en el `params_fingerprint` del TreeBuilder en esta fase, porque el motor de crecimiento actual no la utiliza: no altera la topología del árbol ni las PD por hoja, así que dos modelos con costos distintos son numéricamente idénticos bit a bit. Incluirla en el fingerprint sería una diferencia ficticia (mismo modelo, huella distinta). La matriz se incluirá en el fingerprint cuando el TreeBuilder implemente poda o crecimiento basado en costos (Fase 3.11.d o 4.0). Además, la tupla vacía `()` equivale a "sin costos" y no se valida (el endurecimiento de `fix_spec` —cuadrada N = nº de clases, diagonal fija a 0, valores finitos ≥ 0— solo aplica a matrices no vacías).
**Consecuencia:** El contrato de `fix_spec` gana el parámetro keyword-only `cost_matrix=None` (ver `docs/api.md`); la topología y las métricas del modelo son independientes de la matriz en esta fase; los umbrales de clasificación óptimos basados en costos quedan como uso futuro documentado (diseño `docs/3.11.c_design_univariate_cost_matrix.md` §3.2).

### 18.9 Intervención manual: nuevo TreeModel con re-indexado BFS (Phase 3.11.d)

**Contexto:** La Fase 3.11.d introduce la intervención manual del analista sobre el árbol entrenado (menú contextual del canvas; `prune_branch` implementado, Grow/Select/Define diferidos). `TreeModel` es frozen y su `__post_init__` exige alcanzabilidad total desde la raíz, lo que prohíbe tanto mutar el modelo como construir intermedios con nodos huérfanos (la estrategia de "modelo temporal" del diseño original no era construible; zona gris resuelta en `audit_log.md`, entrada del 25/10/2026).

**Decisión:** Toda intervención manual genera un `TreeModel` NUEVO (el original nunca se muta): se modifica la lista de nodos en memoria y se re-indexa en BFS completo (`Session._reindex_tree`, lógica simplificada de `pruning.py::_rebuild` sin depender del `Pruner`), preservando la invariante `node_id == index` y garantizando que no quedan nodos huérfanos. El fingerprint hereda el del modelo original con un sufijo de intervención manual incremental (`-iN`, N = contador de overrides de la sesión; renombrado de `-pN` en el saneamiento post-auditoría del 25/10/2026 para eliminar la colisión con el sufijo de poda `-p{alpha}` de `pruning.py` — ver `docs/audit_log.md`, mini-cierre del 25/10/2026, ZG-1). Cada acción se registra en el log inmutable `SessionState.manual_overrides` —tupla `(timestamp, node_id, action, params_str, fp_before, fp_after)`—, consultable desde el botón "Ver Auditoría" del HUD (`ManualOverrideDialog`). En modo BANKING la GUI exige confirmación explícita (`QMessageBox`) antes de llamar a `Session.intervene_node`; en modo RESEARCH se aplica directamente (y queda igualmente registrada).

**Consecuencia:** La paridad K=2 de los modelos entrenados normalmente no se ve afectada (la intervención es una acción posterior al entrenamiento); el fingerprint sufijado deja traza inequívoca de que el modelo fue intervenido manualmente; el contrato público gana `Session.intervene_node(node_id, action, payload=None)` (ver `docs/api.md`). Las acciones Grow Tree / Select Predictor / Define Split quedan diferidas a una fase posterior (requieren crecimiento interactivo nodo a nodo del `TreeBuilder`).

### 18.10 Terminología dinámica por modo de gobernanza (Phase 3.6.e)

**Contexto:** El backend es agnóstico del dominio, pero la GUI hardcodeaba vocabulario bancario ("PD", "Bad rate", "Malo/Bueno") incluso en modo RESEARCH, donde el analista no trabaja con riesgo de crédito. La Fase 3.6.e separa la semántica de la presentación sin tocar los DTOs del backend (que siguen emitiendo `pd`, `bad_rate`, `n_bad`, …).

**Decisión:** La terminología visible queda atada al `GovernanceMode` con el que se entrenó el modelo (congelado en el `params_fingerprint`); NO hay toggle en caliente (el modo tiene efectos numéricos reales —Jeffreys + PD floor— y un toggle cosmético presentaría una PD con floor BCBS CRE 32.4 como "probabilidad" neutra: riesgo de interpretación regulatoria incorrecta). El resolvedor `tr_term(concept, mode)` (`frontend_v3/i18n.py`) mapea conceptos a claves `term_banking_*` / `term_research_*` con paridad EN/ES; los paneles (`ReportsPanel`, `MetricsPanel`, `TreePanel`) exponen `set_governance_mode(mode)`, cableado en `MainWindow._on_wizard_finished`. En modo BANKING las etiquetas visibles se conservan bit a bit idénticas (los resolvedores devuelven `tr(key)` clásico; la invariante §5 del diseño); el mapeo neutro solo aplica en RESEARCH. El backend no cambia (cero impacto numérico; la paridad K=2 y la suite existente quedan intactas).

**Consecuencia:** Un mismo número renderiza con dos cadenas (una por modo) a partir del mismo DTO; jamás se computa dos veces ni con fórmulas distintas. La cobertura RESEARCH de la Fase 3.6.e abarca: cabeceras de la gains table y del export HTML, resumen y matriz del export HTML, matriz de clasificación en pantalla y tooltips de los nodos. Deuda registrada en `docs/roadmap.md` (Deferred): término neutro propio para `reports_matrix_bad_capture_rate` y dataset real Wholesale Customers (validación multi-dominio extensiva, ZG-3 del diseño). Diseño aprobado: `docs/3.6.e_design_non_banking.md`; cierre: `docs/audit_log.md` entrada del 25/10/2026.

### 18.11 UI Granularity and Bidirectional Selection (Hotfix 25/10/2026)

**Contexto:** El Menú Ver ofrecía un único toggle global para todo el panel izquierdo (`_act_toggle_left` → `_left_panel.setVisible`): ocultar un bloque implicaba ocultarlos todos. Además, el Tree Map (decisión D2 del diseño 3.11.b) era estrictamente pasivo: el clic sobre un rectángulo hacía `centerOn` en el canvas principal sin tocar la selección, lo que obligaba al analista a re-localizar el nodo en el canvas para ver su detalle en el HUD.

**Decisión:** (a) El Menú Ver gana un submenú granular ("Toggle Left Panel") con tres acciones checkable —Project Explorer, Tree Map, Data Viewer— que ocultan/muestran los `QGroupBox` individuales del panel izquierdo (`_left_gb_explorer` / `_left_gb_treemap` / `_left_gb_dataviewer`); la acción global se conserva como atributo (compatibilidad con los smoke tests) pero sale del menú. (b) El Tree Map propaga la selección al canvas principal: el clic sobre un rectángulo hace `centerOn` y además `select_node(node_id)`, actualizando el HUD (mapa bidireccional); la dirección inversa (canvas → mapa) sigue siendo el resaltado pasivo de D2.

**Consecuencia:** El analista puede ocultar bloques concretos del panel izquierdo sin perder los demás, y navegar/seleccionar directamente desde el minimapa. El invariante D2 se relaja solo en la dirección mapa → canvas (selección); el mapa sigue sin selección ni foco propios. Corrección asociada del mismo hotfix: el hit-test del minimapa barre todos los ítems del punto (la etiqueta del `node_id` queda visualmente sobre el rectángulo y no debe tragarse el clic). Cierre: `docs/audit_log.md` entrada del 25/10/2026.

---

## Maintenance

This document is authoritative for any decision that affects:

- **Numerical results** of a trained model (any change here requires a
  new entry or an update to an existing one).
- **API contract** (function signatures, dataclass fields, defaults).
- **Architectural boundaries** (clean room, fingerprint contents,
  governance modes).
- **Domain scope** (which target types, class counts, and user
  profiles are supported).

Whenever a decision is revisited, the corresponding entry here must
be updated **in the same commit** that touches the code, together with
a note in `docs/audit_log.md`.

**Cross-references:**
- Mathematical formulas and citations: `docs/methodology.md`.
- Public API surface: `docs/api.md`.
- Chronological log: `docs/audit_log.md`.
- Phase plan: `docs/roadmap.md`.
- Governance rules for AI agents: `.treegovrules` and `AGENTS.md`.

**Version.** This document was created on 04/10/2026 as part of Phase
3.0, closing the "grey zone" of undocumented design decisions
accumulated during Phases 0 through 2.4. (Updated on 20/10/2026 to add
§10.4 — Phase 3.8; on 24/10/2026 to add §17 — Phase 3.11.a — and §18 —
Phase 3.11.a.1; on 25/10/2026 to add §0.5 — Clean-Room Development and
Academic Provenance — and §18.5–§18.6 — mini-cierre de zonas grises de
presentación; on 25/10/2026 to add §18.7 — Phase 3.11.b.1, empty dict
vs RuntimeError in `get_data_preview`; on 25/10/2026 to add §18.8 —
Phase 3.11.c.3, cost matrix in `SessionState` without fingerprint;
on 25/10/2026 to add §18.9 — Phase 3.11.d, manual intervention
rebuilds the TreeModel with BFS reindex and logs overrides in
`SessionState.manual_overrides`; on 25/10/2026 to add §18.10 — Phase
3.6.e, dynamic terminology bound to the governance mode frozen in the
fingerprint, BANKING labels bit-identical, on 25/10/2026 to add §18.11
— Hotfix Visual post-3.6.e (granular View menu toggles per left-panel
block; bidirectional Tree Map selection map->canvas; scoped relaxation
of D2).)

---