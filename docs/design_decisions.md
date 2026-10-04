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
| **Neutral vocabulary** (no "PD", "default", "bad/good") | ❌ | Phase 3.6.b |
| **Non-credit examples and datasets** | ❌ | Phase 3.6 |
| **Domain-agnostic documentation** | ❌ | This section is the first step |

**Verdict.** A biologist or social scientist **cannot use TreeGov with
real data today**. Reason: (a) multiclass is blocked by the builder,
(b) vocabulary is credit-specific, (c) no regression support, (d) no
non-credit example datasets. Fixing this requires Phase 3.1
(multiclass) and Phase 3.6.b (neutral vocabulary + examples).

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

### 0.4 Vocabulary policy

**Decision.** Internal identifiers (class fields, function names,
parameter names) keep the credit-specific terminology for historical
and backward-compatibility reasons. External surfaces (GUI labels, doc
strings, report headers, user-facing messages) will use **neutral
vocabulary** when the user selects a non-credit domain. This policy is
implemented progressively; Phase 3.6.b is the first concrete step.

**Rationale.** Renaming internal fields (e.g., `pd_final` → `score`)
would break the public API (`docs/api.md`), invalidate cached
fingerprints, and touch every test. The cost/benefit is negative. But
presenting a biologist with a GUI label that says "PD (final)" is also
unacceptable. Hence the split: internal stays, external translates.

**Neutral-vocabulary map (draft, to be finalised in 3.6.b):**

| Internal (credit) | External (neutral) |
|---|---|
| `pd_final` | Probability |
| `bad_rate` | Event rate |
| `n_bad` | Events |
| `n_good` | Non-events |
| "gains table" | Lift table |
| "default" (example target) | Outcome |
| "PD" (display) | Probability |

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

### 5.2 `TreeNode.pd_final` is scalar

**Context.** `pd_final` is the operational probability for a leaf. It
is typed `float`, not `tuple[float, ...]` or `np.ndarray`.

**Decision.** Scalar. This restricts TreeGov to binary targets.

**Rationale (historical).** Phase 0/1 was designed for binary credit
risk modelling. Binary targets dominate the credit-scoring use case.
Multiclass was deferred — the engines support it (CHAID uses χ² with
K classes; C&RT uses Gini impurity with K classes) but the container
(TreeBuilder, TreeNode) does not.

**Consequences.** This is the **single biggest obstacle** to
multiclass support and, by extension, to non-credit use. Planned fix:
Phase 3.1 converts `pd_final` to `tuple[float, ...]` and adapts the
downstream consumers (`validation`, `reporting`, `stability`).
Documented as a known limitation in `roadmap.md`.

### 5.3 `target_type` restricted to BINARY in `build()`

**Context.** `TargetType` (see `types.py`) has three values: BINARY,
CATEGORICAL, CONTINUOUS. The engines handle all three. But
`TreeBuilder.build()` raises a `ValueError` if `set(y) != {0, 1}`.

**Decision.** Restrict to BINARY at the builder level, even though
lower layers support more.

**Rationale.** `TreeBuilder` produces a `TreeModel` whose `TreeNode`s
hold scalar PDs (see §5.2). For multiclass or continuous targets, the
scalar PD would be meaningless. Blocking at the builder is honest:
better a clear error than a silently wrong model.

**Consequences.** The engines' broader capabilities are unreachable
through the standard flow. Planned fix: Phase 3.1 opens BINARY and
CATEGORICAL; continuous regression (target_type=CONTINUOUS) is deferred
to Phase 3.4 or later, pending a decision on which metric to attach to
a leaf's "prediction" (mean? median? quantile?).

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
accumulated during Phases 0 through 2.4.

---