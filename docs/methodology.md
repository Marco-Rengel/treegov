# TreeGov — Mathematical Methodology

Formal documentation of the algorithms implemented in TreeGov, with their mathematical foundations and bibliographic citations.

---

## 1. Classic CHAID and Exhaustive CHAID

CHAID (Chi-square Automatic Interaction Detection) recursively partitions the population by evaluating the statistical association between each predictor and the target variable.

### 1.1. Pearson's chi-square

For an observed contingency table of I×J cells:

χ² = Σᵢⱼ (O_ij − E_ij)² / E_ij

where:
- O_ij: observed frequency in cell (i, j).
- E_ij = R_i · C_j / N: expected frequency under independence.
- R_i: marginal total of row i.
- C_j: marginal total of column j.
- N: total number of observations.

Degrees of freedom: df = (I − 1)(J − 1).

No Yates continuity correction (original CHAID convention).

**Citation**: Pearson, K. (1900). Philosophical Magazine, Ser. 5, 50(302), 157-175.

### 1.2. One-way ANOVA (Fisher's F)

For k groups with n_i observations each:

SS_B = Σᵢ nᵢ (ȳᵢ − ȳ)²     (between groups)
SS_W = Σᵢ Σⱼ (y_ij − ȳᵢ)²   (within groups)
df1 = k − 1 ; df2 = N − k
F = (SS_B / df1) / (SS_W / df2)

p-value = P(F_{df1,df2} ≥ F) via the survival function.

**Citation**: Fisher, R.A. (1925). Statistical Methods for Research Workers.

### 1.3. Iterative category merging

For each eligible pair of categories:

1. Build the 2×K sub-table of the pair.
2. Compute χ² (categorical target) or F (continuous target).
3. Merge the pair with the highest p-value if p > α_merge.
4. Repeat until no pair is mergeable.

On ordinal predictors, only adjacent pairs are considered.

### 1.4. Kass (1980) Bonferroni multipliers

For a variable with c original categories that ends up in r groups after merging:

- **Ordinal predictor**: M(c, r) = C(c − 1, r − 1) = (c−1)! / [(r−1)! (c−r)!]
- **Nominal predictor**: M(c, r) = S(c, r), Stirling number of the second kind

adjusted_p_value = min(1, p_value × M)

**Citation**: Kass, G.V. (1980). Applied Statistics, 29(2), 119-127.

### 1.5. Exhaustive CHAID

Variant that does not stop at the first local optimum. It merges pairs iteratively until only 2 groups remain, recording the complete step history. It selects the step with the lowest adjusted p-value (including step 0, the unmerged state).

**Citation**: Biggs, D., de Ville, B. & Suen, E. (1991). Journal of Applied Statistics, 18(1), 49-62.

### 1.6. Cochran's rule (1954)

The asymptotic approximation of χ² loses validity when:
- Any expected frequency E_ij < 1, or
- More than 20% of the cells have E_ij < 5.

TreeGov applies preventive force-merging of the category with the lowest total until the rule is satisfied. If irreducible (r = 2), it reports cochran_ok = False with WARNING.

**Citation**: Cochran, W.G. (1954). Biometrics, 10(4), 417-451.

### 1.7 Cochran's rule — forced merges count in `c → r`

When Cochran's rule (§1.6) forces a merge to restore the validity of the
χ² approximation, that merge **counts toward the total number of merges**
used in the Kass (1980) Bonferroni multiplier `M(c, r)` computed at the
end of the process.

**Formula.**

    M(c, r) is computed with the FINAL r, which includes forced merges.

**Rationale.** The Bonferroni multiplier corrects for the number of ways
`c` original categories could have ended up in `r` final groups. A
forced merge is still a merge — the final `r` reflects the total number
of groups, regardless of why each merge happened. Excluding forced
merges from `c → r` would undercorrect the family-wise error rate.

**Consequences.** The reported `p_value_adjusted` correctly reflects
the full search space, including the forced merges.

> See `docs/design_decisions.md` §2.2 for the full decision rationale.

### 1.8 Pair p-value computed on the 2×K pair sub-table

During iterative merging, the merge decision for a pair of groups
`(i, j)` uses the p-value of the **2×K sub-table formed by those two
groups only**, ignoring the other groups in the current partition.

**Formula.** For groups `i` and `j` with class counts
`(c_i,1, …, c_i,K)` and `(c_j,1, …, c_j,K)`:

    O   = [[c_i,1, ..., c_i,K], [c_j,1, ..., c_j,K]]   (2 × K)
    χ²_pair = Σ_ab (O_ab − E_ab)² / E_ab,   df = K − 1
    E_ab = (row_a · col_b) / N_pair

At each step, the pair with the **largest** p-value (least significant
association) is merged if that p-value exceeds `alpha_merge` (classic
CHAID) or unconditionally until `r = 2` (Exhaustive CHAID).

**Rationale.** This is the Kass (1980) convention, replicated by
classic CHAID implementations. It isolates the association between the
two candidate groups, free from interference by the rest of the table.
Alternative conventions (e.g., collapsing other groups) would require
arbitrary decisions about how to aggregate them.

> See `docs/design_decisions.md` §2.1 for the full decision rationale.

### 1.9 Exhaustive CHAID includes step 0 in the selection

Exhaustive CHAID (Biggs, de Ville & Suen 1991) merges pairs until only
two groups remain, recording the complete step history. The **unmerged
state** (step 0, `r = c`) participates in the final selection, with
multiplier `M = 1`.

**Formula.**

    Choose the step t* that minimizes adjusted_p_value(t), where
    adjusted_p_value(t) = min(1, global_p_value(t) · M(c, r_t))

    The candidate set includes t = 0, the unmerged state
    (r_0 = c, M(c, c) = 1, p_adj(0) = p_global(0)).

**Rationale.** If the unmerged partition has the smallest adjusted
p-value, it means the predictor is already maximally associated with
the target without any merging. Excluding step 0 would force at least
one merge, distorting the result. This is the correct reading of Biggs,
de Ville & Suen (1991).

**Consequences.** A predictor can win with `n_merges = 0`, in which
case `bonferroni_multiplier = 1` and `p_value_adjusted = p_value`. The
`MergeDiagnostics.exhaustive_steps` tuple records every state, including
step 0.

> See `docs/design_decisions.md` §2.3 for the full decision rationale.

### 1.9bis Pearson χ² on weighted tables — linear in weight mass

With per-sample weights, contingency-table cells hold **sums of weights**
instead of row counts. Pearson's formula is identical:

    E_ij = R_i · C_j / W          (W = total weighted mass)
    χ²   = Σ_ij (O_ij − E_ij)² / E_ij
    df   = (I − 1) · (J − 1)

Under a uniform rescaling of the weights (multiply all by k), the cells,
the marginals and W all scale by k. Each quotient term scales by k.
Therefore **χ² scales linearly with the total weight mass**.

Contrast with F (weighted ANOVA, see §3.7bis): F is a quotient SSB / SSW
and is therefore **scale-invariant** in the weights.

Practical consequence: in CHAID with a binary target, the p-value depends
on the scale chosen by the analyst. An analyst loading weights that sum to
n gets the same behavior as with counts; one loading weights that sum to a
million gets a much larger χ² (smaller p-value) for the same distribution.
TreeGov does **not** normalize: the decision stays with the analyst.

**Citation:** Pearson (1900); Heeringa, West & Berglund (2010), §5.4.
**MRM scope clarification:** TreeGov applies direct weight-mass weighted tables
and moments **without** complex-survey design corrections (no Rao-Scott
adjustment and no design-effect DEFF rescaling).

> See `docs/design_decisions.md` §13.2 for the full decision rationale.

### 1.10 Continuous predictors in CHAID and Exhaustive CHAID (Phase 3.10.b, Block 2E)

`ChaidEngine` supports `PredictorType.CONTINUOUS` predictors via automatic
discretization (`_reduce_continuous_predictor`), transforming each continuous
predictor into ordered numeric intervals before applying Kass merging:

1. **Internal quantile cuts (11 bins, not deciles).** Ten internal cut points
   are computed on the node's finite values at quantiles `1/11, 2/11, …, 10/11`:
   `edges = np.unique(np.quantile(xv, np.linspace(0.0, 1.0, 12)[1:-1]))`.
   Deduplication yields at most 11 non-overlapping bins (`bin_0 .. bin_m`).
   Quantiles are computed **without sample weights** (documented choice in
   `docs/design_decisions.md` §16.2; sample weights still govern the
   subsequent χ² or ANOVA F statistics).
2. **Half-open encoding.** Values are assigned via
   `np.digitize(xv, edges, right=True)`, so each bin covers `(a, b]`, with
   `bin_0 = (−∞, edges[0]]` and `bin_m = (edges[-1], +∞)`.
3. **Ordinal Kass merging and empty-bin pre-merge.** Any empty bin produced by
   ties is pre-merged with the adjacent upper bin (`_premerge_empty_bins`). If
   fewer than 2 bins remain (e.g., constant predictor), `evaluate` returns
   `None` cleanly in both classic and Exhaustive modes. Remaining bins are
   treated as **`ORDINAL`** under Kass (1980) (adjacent merges only,
   multiplier `C(c − 1, r − 1)`).
4. **Storage and fingerprint scope.** The strictly increasing cut points are
   stored in `SplitConfig.bin_edges` on the resulting node split and used by
   `TreeBuilder._partition`, `validation.predict_leaf_assignment` and the
   SQL/Python/Markdown exporters (routing by consolidated `SplitConfig.branches`).
   `bin_edges` belongs to each node's immutable `SplitConfig` and is **not** a
   global hyperparameter inside `TreeModel.params_fingerprint`.
5. **Numerical stability and Cochran eligibility (Block 2E).** `ChaidEngine`
   rejects `±inf` in continuous predictors and continuous targets, centers
   continuous targets (`y_c = y − ȳ`, Chan, Golub & LeVeque 1983) prior to
   accumulating sufficient statistics, and in **Exhaustive CHAID** restricts
   final selection to **Cochran-valid** steps (`step_cochran_ok`) whenever at
   least one valid state exists (while preserving the complete merge trajectory
   in `MergeDiagnostics.exhaustive_steps`).

> See `docs/3.10.b_design_chaid_binning.md` §4.2 and `docs/design_decisions.md`
> §16 and §31.

---

## 2. C&RT (Classification and Regression Trees)

Strictly binary tree driven by impurity reduction.

### 2.1. Gini impurity

For a node t with K classes and proportions p_k = n_k / n:

I_Gini(t) = 1 − Σₖ p_k²

### 2.2. Variance impurity

For regression:

I_Var(t) = (1/n) Σᵢ (yᵢ − μ)² = E[y²] − E[y]²

### 2.3. Impurity reduction

For a split s that divides node t into children L (left) and R (right):

ΔI(s, t) = I(t) − (n_L / N) · I(L) − (n_R / N) · I(R)

The optimal split is the one that maximizes ΔI.

### 2.4. Threshold search (continuous)

For a continuous variable, values are sorted and midpoints between distinct consecutive values are evaluated:

t_i = (x_(i) + x_(i+1)) / 2

The chosen threshold is the one that maximizes ΔI.

### 2.5. Subsets (nominal)

For nominal variables with K ≤ 10 categories: exhaustive search over the 2^(K−1) − 1 non-trivial binary partitions.

For K > 10: heuristic by majority-class rate (supervised ordering).

### 2.6. Surrogate splits

Replications of the primary left/right assignment over secondary predictors, used to route missing values. They are ordered by agreement with the primary split and only those outperforming the majority rule are kept.

**Operational scope in v1.** `CrtEngine.surrogate_splits()` (and its `find_surrogates` computation) is exposed as an **engine-level analytical API** on `CrtEngine`; it is **not** automatically activated during `TreeBuilder` / `Session` tree routing, where missing predictor values are imputed upstream via `TrainOnlyImputer` (§5).

**Citation**: Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984). Classification and Regression Trees. Wadsworth.

### 2.7 `min_child_size` as an absolute floor per branch

When an engine proposes a split, the resulting child branches are
computed. If **any** child branch has fewer than `min_child_size` rows,
the split is **rejected in its entirety** and the node becomes a leaf.

**Formula.** For a candidate split with child branch sizes
`(n_1, n_2, …, n_k)`:

    Accept the split iff   min(n_1, …, n_k) ≥ min_child_size
    Otherwise, the node is a leaf with leaf_reason = "rama_insuficiente".

There is **no fallback merging** of small branches with their siblings.

**Rationale.** Merging small branches would produce a partition that
the engine did not propose, silently corrupting the audit trail: the
tree would report a split, but the split as implemented would not
match the split as computed. The absolute floor is honest: what is
computed is what is built.

**Consequences.** Some potential splits are simply not taken, making
trees more conservative at their lower levels. This is a deliberate
design choice.

> See `docs/design_decisions.md` §5.1 for the full decision rationale.

### 2.8 Surrogate agreement — the quadrant identity

A surrogate split on predictor `B` replicates the primary split on
predictor `A`. The agreement is the fraction of rows where the two
assignments match, computed over the rows where both predictors are
non-null.

**Formula.** Let `P_L` / `P_R` be the primary's left/right assignment
and `C_L` / `C_R` the candidate's. Define:

    q_ll = |P_L ∩ C_L|
    q_lr = |P_L ∩ C_R|
    q_rl = |P_R ∩ C_L|
    q_rr = |P_R ∩ C_R|

The four quadrants must satisfy the identity

    q_ll + q_lr + q_rl + q_rr = n_used

where `n_used` is the number of rows with both predictors non-null.
The agreement (best orientation) is

    agreement = max(q_ll + q_rr,  q_lr + q_rl) / n_used

The `same` term counts rows where primary and candidate agree; the
`flip` term counts rows where they disagree under the primary's
orientation (candidate's left corresponds to primary's right, or
vice versa).

**Rationale.** A critical bug in Phase 1.2 confused `q_lr` and `q_rl`,
inflating agreement on asymmetric 2×2 tables. The fix rewrote the
computation with explicit quadrants and enforced the identity as a
post-condition of the code.

**Consequences.** Test fixtures include asymmetric 2×2 tables that
would fail if the quadrants were confused again.

> See `docs/design_decisions.md` §3.2 for the full decision rationale.

### 2.9 Surrogate retention — agreement > majority-to-beat

Not every candidate split is kept as a surrogate. A candidate is
retained if and only if its agreement strictly exceeds the **trivial
majority rule** of the primary split.

**Formula.** Let

    majority_to_beat = max(n_L, n_R) / n_used

where `n_L`, `n_R` are the primary's left/right branch sizes over the
`n_used` rows where both predictors are non-null. A candidate with
agreement `a` is retained iff

    a > majority_to_beat

**Rationale.** The majority rule (always route to the larger side) is
the trivial baseline. A surrogate is only useful if it beats that
baseline; otherwise it carries no information beyond the majority
itself. This is Breiman et al. (1984), §5.3.

**Consequences.** On highly asymmetric primaries (e.g., 90/10 split),
the threshold is 0.9 — a strict bar. On balanced primaries, it is close
to 0.5. The rule is deterministic and mirrors Breiman's original
specification.

**Citation:** Breiman, L., Friedman, J. H., Olshen, R. A. & Stone, C.
J. (1984). *Classification and Regression Trees*. Wadsworth, §5.3.

> See `docs/design_decisions.md` §3.3 for the full decision rationale.

### 2.10 Weighted C&RT and numerical stability (Phase 3.2, Block 2E)

`CrtEngine` accepts strictly positive per-row sample weights (`weights`), and
`TreeBuilder` enforces an optional cumulative weighted-mass floor per branch
(`min_child_weight`, checked alongside physical row counts `min_child_size`):

- **Weighted Gini impurity.** Class probabilities in parent, left and right
  nodes are normalized by their respective weighted masses before squaring
  (`p_k = W_k / W`), using the cancellation-free identity
  `I_G = q · (2 − q) − Σ_{k ≠ m} p_k²` where `m = argmax_k p_k` and
  `q = Σ_{k ≠ m} p_k`. This prevents floating-point overflow/underflow under
  extreme weight magnitudes (`~1e160` or `~1e-160`).
- **Reverse cumulative sums and direct complements.** Continuous sweeps and
  rate-sorted nominal sweeps compute right-child cumulative sums from the right
  (`cumsum(arr[::-1])[::-1]`), and exhaustive nominal search computes the left
  branch directly (`(~masks) @ counts`), avoiding catastrophic subtraction
  cancellation under extreme weight ratios (`≥ 1e16`).
- **Centered regression variance.** For `TargetType.CONTINUOUS`, target values
  are centered (`y_c = y − μ_w`) before accumulating weighted sufficient
  statistics (Chan, Golub & LeVeque 1983), eliminating cancellation when
  `|μ| ≫ σ`.
- **Finiteness guards.** Degenerate zero-mass sides are scored `−∞` and
  `surrogate_splits()` rejects `±inf` in numeric predictors.

**Citation:** Breiman et al. (1984); Chan, Golub & LeVeque (1983); Heeringa,
West & Berglund (2010), §5.3 (direct weight-mass weighted moments without
complex-survey design corrections: no Rao-Scott adjustment and no DEFF
rescaling). See `docs/design_decisions.md` §13.3 and §31.

---

## 3. QUEST (Quick, Unbiased, Efficient Statistical Tree)

Binary engine with unbiased variable selection and univariate QDA split.

### 3.1. Stage 1 — Variable selection

For each predictor j:

- Continuous/ordinal: pⱼ = p-value of the ANOVA F-test between classes.
- Nominal: pⱼ = p-value of Pearson's χ².

Bonferroni threshold: α / (2J), where J = number of predictors.

If no test beats the threshold, Brown-Forsythe (Levene with median) is run on the continuous/ordinal variables to detect discrimination by variance.

**Citation:** Loh, W.-Y. & Shih, Y.-S. (1997); Brown, M.B. & Forsythe, A.B. (1974); Levene, H. (1960); Fisher, R.A. (1925); Pearson, K. (1900).

### 3.2. Stage 2 — Univariate QDA split

Estimated per class k ∈ {0, 1}: n_k, m_k (mean), s_k² (sample variance), π_k = n_k / N.

The QDA decision boundary is the root of:

ℓ₁(x) − ℓ₀(x) = 0

where ℓ_k(x) = −½ ln(2π) − ½ ln(s_k²) − (x − m_k)² / (2 s_k²) + ln(π_k)

This yields a quadratic equation A x² + B x + C = 0 with:

A = 1/s₀² − 1/s₁²
B = 2 (m₁/s₁² − m₀/s₀²)
C = m₀²/s₀² − m₁²/s₁² + 2 ln(π₁/π₀) − ln(s₁²/s₀²)

The root within the range [min(m₀, m₁), max(m₀, m₁)] is accepted. If no valid root exists, fallback to the weighted midpoint x̄ = (n₀ m₀ + n₁ m₁) / N.

**Citation**: Loh, W.-Y. & Shih, Y.-S. (1997). Statistica Sinica, 7(4), 815-840.

### 3.3 Bonferroni family — TreeGov uses `M = 2J`, canonical uses `M = J`

QUEST selects a variable by comparing each predictor's p-value against
a Bonferroni-corrected threshold. The canonical Loh & Shih (1997)
formulation uses `α / J`, where `J` is the number of predictors.

TreeGov uses `α / (2J)`, because QUEST runs **two families** of tests:
1. **Family 1** — tests on means/association (F for continuous, χ² for
   nominal).
2. **Family 2** — robust tie-breaker tests on variances
   (Brown-Forsythe), executed only when Family 1 produces no winner.

**Formula (TreeGov default).**

    α_effective = α / (2J)
    where J = len(spec) = number of predictors declared by the caller.

The conservative reading: the correction covers the family of tests
that were **attempted**, not only those that produced a result.
Predictors dropped for insufficient data still count toward `J`.

**Rationale.** Correcting only by `J` would ignore the second family of
tests, undercorrecting the family-wise error rate. The factor 2 makes
the test deliberately more conservative than canonical Loh & Shih.

**Configuration.** This behaviour will be exposed as a parameter
`bonferroni_family: int = 2` (canonical: `1`) in Phase 3.0.g. The
default will remain `2` so that existing models remain reproducible.

**Citation:** Loh, W.-Y. & Shih, Y.-S. (1997). *Statistica Sinica*
7(4), 815-840.

> See `docs/design_decisions.md` §4.1 for the full decision rationale.

### 3.4 Nominal high-cardinality split — rate-based heuristic

For a nominal predictor with `K > 10` categories, exhaustively
enumerating the `2^(K−1) − 1` binary partitions is infeasible. TreeGov
uses a **rate-based heuristic** instead of the canonical dummies + LDA
procedure.

**Formula.**

1. Compute the class-1 rate per category:
   `rate_g = count(g, class 1) / count(g)`.
2. Sort categories by rate **descending** (stable).
3. Sweep all `K − 1` split points along the sorted order.
4. Choose the split that maximizes the Gini gain `ΔI`.

**Rationale.** (a) Consistency with C&RT, which already uses the same
rate-based heuristic at `K > 10`. (b) Avoids adding a new statistical
dependency (LDA) that would require its own methodology section and
audit. The heuristic is documented as a deliberate deviation from
canonical Loh & Shih.

**Configuration.** Exposed as `nominal_high_card: str = "rate"` in Phase 3.0.g.
The canonical option `"dummies_lda"` is reserved in the `QuestEngine`
constructor signature for future work and raises `NotImplementedError` in v1
(only `"rate"` is implemented).

**Citation:** Breiman, L. et al. (1984), §4 — the rate-based cut is
discussed in the C&RT chapter as the standard high-cardinality
heuristic.

> See `docs/design_decisions.md` §4.2 for the full decision rationale.

### 3.5 QDA cutpoint restricted to the inter-means interval

The QDA cutpoint for a continuous or ordinal predictor is the root of
a quadratic equation (see §3.2). When both roots exist, TreeGov
restricts acceptance to those in the interval between the two class
means.

**Formula.** With class means `m_0`, `m_1`, roots `r_1`, `r_2`:

    Accept r_i iff   min(m_0, m_1) ≤ r_i ≤ max(m_0, m_1)

If no root lies in the interval, the algorithm falls back to the
weighted midpoint `x̄ = (n_0·m_0 + n_1·m_1) / N`.

**Rationale.** A root outside the inter-means interval produces a
cutpoint that contradicts the natural ordering of the data — in
practice, it would generate extreme splits like "90% of the data goes
to the left branch". The restriction is a defensive, operational
choice, not an optimal one; it sacrifices some canonical solutions to
avoid pathological cuts.

**Configuration.** Exposed as `qda_root_restriction: bool = True`
(canonical: `False`) in Phase 3.0.g.

**Citation:** Loh, W.-Y. & Shih, Y.-S. (1997). *Statistica Sinica*
7(4), 815-840.

> See `docs/design_decisions.md` §4.3 for the full decision rationale.

### 3.6 Empirical priors in the QDA cut

The QDA decision boundary depends on prior probabilities per class. Two
choices:
- **Uniform:** `π_k = 1 / K`.
- **Empirical:** `π_k = n_k / N`.

TreeGov uses **empirical priors**.

**Formula.**

    π_0 = n_0 / N,   π_1 = n_1 / N
    log-odds term in C coefficient:  2 · ln(π_1 / π_0)

**Rationale.** In credit scoring, the class proportions carry real
business information (the event rate is a business quantity). Using
uniform priors would ignore this. The same reasoning applies outside
credit: sample proportions are informative unless there is an explicit
reason to believe otherwise. This is the natural reading of Loh &
Shih (1997), which assumes the sample reflects the population.

**Consequences.** The QDA boundary shifts toward the majority class,
consistent with the empirical prior. Documented in `quest_engine.py`.

**Citation:** Loh, W.-Y. & Shih, Y.-S. (1997). *Statistica Sinica*
7(4), 815-840.

> See `docs/design_decisions.md` §4.4 for the full decision rationale.

### 3.7bis Weighted QUEST — weighted ANOVA/Brown-Forsythe, Kish QDA variance and Citardauq roots (Phase 3.2, Block 2E)

Weighting affects both QUEST stages (`backend_v3/statistics.py` and
`backend_v3/quest_engine.py`):

**Stage 1 (variable selection).**
- **Weighted one-way ANOVA F (`statistics.f_oneway`):** uses weighted class
  means `m_k = Σ_i w_i x_i / W_k`, group weight sums `W_k`, grand weighted mean
  `m = Σ_k W_k m_k / W`, `SSB = Σ_k W_k (m_k − m)²`,
  `SSW = Σ_k Σ_{i ∈ k} w_i (x_i − m_k)²`, and physical degrees of freedom
  `df1 = K − 1`, `df2 = N − K`. Because `F = (SSB / df1) / (SSW / df2)` is a
  ratio, it is **strictly scale-invariant** under `w → c · w`.
- **Weighted Brown-Forsythe (`statistics.brown_forsythe`):** computes the
  **weighted median** `_weighted_median(x_k, w_k)` per class (with floating-point
  tie tolerance `rel_tol=1e-12, abs_tol=1e-15` matching `np.median` under equal
  weights), forms `z_ij = |x_ij − median_w(x_k)|`, and applies weighted ANOVA F
  to `z`. Scale-invariant in `w`.
- **Weighted Pearson χ²:** nominal predictors use the weighted contingency
  table scheme of §1.9bis.
- **Non-hijacking under degenerate separation (Block 2E):** if a degenerate
  predictor yields `F = ∞`, Stage 1 prioritizes finite significant predictors
  first and logs `"no representable"` + returns `None` only when no finite
  significant predictor exists.

**Stage 2 (univariate QDA cutpoint).**

    Weighted class means:      m_k = Σ_{i ∈ k} w_i x_i / W_k
    Kish reliability variance: v_k = Σ_{i ∈ k} w_i (x_i − m_k)² / (W_k − (Σ_{i ∈ k} w_i²) / W_k)
    Weighted empirical priors: π_k = W_k / W
    Weighted midpoint fallback: x̄ = (W_0 m_0 + W_1 m_1) / (W_0 + W_1)

**Kish reliability-weight divisor (Block 2E, replacing `W_k − 1`).** The
frequency-weight divisor `W_k − 1` breaks when weights are normalized
(`W_k ≤ 1` produces division by zero or negative variance) and is not
scale-invariant. TreeGov uses **Kish's unbiased reliability-weight variance**
divisor `W_k − (Σ w_i²) / W_k` (Kish 1965; Heeringa, West & Berglund 2010):

- **Strictly scale-invariant:** multiplying all weights by any `c > 0` scales
  both numerator and denominator by `c`, leaving `v_k` and the QDA threshold
  identical.
- **Safe for normalized weights (`Σ w_i = 1`):** strictly positive for any
  class with `n_k ≥ 2` positive weights (falling back safely to `x̄` if
  precision degenerates).
- **Exact parity under uniform weights:** when `w_i ≡ 1`,
  `W_k − (Σ w_i²) / W_k = n_k − n_k / n_k = n_k − 1`.

**Stable quadratic roots (Citardauq) and domain bounds.** The quadratic
`A x² + B x + C = 0` is solved via **Citardauq's numerically stable formula**
(Press et al. 2007, §5.6): `q = −0.5 · (B + sign(B) · √Δ)`, `r_1 = q / A`,
`r_2 = C / q`, preventing catastrophic cancellation when `v_0 ≈ v_1`. All
returned thresholds (QDA, linear LDA and fallback) are bounded to
`[min(x), max(x))` so neither child branch can be empty.

**Citation:** Loh & Shih (1997); Brown & Forsythe (1974); Levene (1960);
Kish (1965); Heeringa, West & Berglund (2010), §5.3–§5.4; Press et al. (2007),
§5.6.
**MRM scope clarification:** TreeGov applies direct weight-mass weighted tables
and moments **without** complex-survey design corrections (no Rao-Scott
adjustment and no design-effect DEFF rescaling).

> See `docs/design_decisions.md` §13.4 and §31 for the full decision rationale.

### 3.8 QUEST multiclass extensions (Phase 3.4)

QUEST (Loh & Shih 1997) is strictly binary in its canonical form:
Stage 1 selects a variable via a two-group ANOVA F or a c×2 Pearson χ²;
Stage 2 splits it via a univariate QDA boundary. Phase 3.4.b opens the
engine to targets with K ≥ 3 classes through two documented extensions.

**Stage 1 — K-group ANOVA F.**

    F = (SSB / (K - 1)) / (SSW / (N - K))

where SSB and SSW are the between- and within-group sums of squares
over the K target classes. For K = 2 this reduces exactly to the binary
form (§3.1). The nominal χ² is unchanged in form: it already operates
on a c×K contingency table.

**Stage 1 tie-breaker — K-group Brown-Forsythe.**

If no predictor's mean-statistic p-value beats the Bonferroni threshold,
the robust tie-breaker replaces the data with Levene's z-scores
`|x_i − median_group|` per class and applies the K-group ANOVA F on
those. For K = 2 this reduces exactly to the binary Brown-Forsythe.

**Stage 2 — Gini reduction sweep for K > 2.**

The canonical Stage 2 uses a QDA boundary between two Gaussian
class-conditional densities. This is intrinsically binary, so TreeGov
bifurcates by K:

- **K = 2**: the QDA path is preserved unchanged (parity invariant).
- **K > 2**: a Gini reduction sweep over the selected predictor:
  - Continuous / ordinal: sweep midpoints between consecutive distinct
    values and choose the cut maximising
    `ΔI = I(parent) − (n_L/N)·I(L) − (n_R/N)·I(R)`, where `I` is the
    Gini impurity `1 − Σ_k p_k²` over the K classes.
  - Nominal with k_cats ≤ 10: exhaustive over the `2^(k_cats−1) − 1`
    binary partitions of the categories (same kernel as C&RT, §2.5).
  - Nominal with k_cats > 10: rate-based heuristic on the modal class
    of the node (same convention as `crt_engine._rates_cls`).

The sweep reuses the same weighted-Gini kernel `_gini_dI` documented
in §2.1–§2.3.

**Fidelity note.** QUEST canonical (Loh & Shih 1997) is strictly binary.
The multiclass extension is a deliberate, documented deviation,
justified by (a) internal coherence with C&RT, and (b) preserving the
binary nature of each node's split, as required by the tree builder's
contract (binary split per node, K-length PD vector).

**Scope limits in v1.**
- `nominal_high_card="dummies_lda"` is reserved in the constructor signature
  and raises `NotImplementedError` in v1 (only `"rate"` is implemented).
- `TargetType.CONTINUOUS` is not supported by `QuestEngine` and is **blocked
  in `Session`**; continuous-target regression is reserved exclusively to the
  engine-level `CrtEngine` and `ChaidEngine` APIs.

**Fingerprint.** No new field is added. The multiclass behaviour is a
property of the model, not a configuration toggle: two QUEST models —
one built on K=2, the other on K=3, same CSV and hyperparameters — are
already distinguishable by their `class_labels` and `n_classes` entries
(Phase 3.1).

**Citation:** Loh, W.-Y. & Shih, Y.-S. (1997), *Statistica Sinica*
7(4), 815-840; Brown, M.B. & Forsythe, A.B. (1974) and Levene, H. (1960)
(Stage 1 K-group variance tie-breaker). The Gini sweep is the standard
binary-impurity reduction of Breiman, L., Friedman, J. H., Olshen, R. A. &
Stone, C. J. (1984), *Classification and Regression Trees*, chapters 2-4.

> See docs/design_decisions.md §4.5 for the full decision rationale.

---

## 4. SplitConfig — Common contract between engines

All engines (CHAID, C&RT, QUEST) return `SplitConfig` objects, an immutable (frozen) dataclass acting as auditable evidence of every candidate partition.

### 4.1. Fields

- predictor: name of the evaluated predictor.
- method: "CHAID", "CHAID_EXHAUSTIVE", "CRT", "QUEST".
- statistic: observed statistic value.
- statistic_name: "chi2", "f", "gini_gain" or "variance_gain".
- df: tuple of degrees of freedom.
- parent_n: parent node size.
- child_ns: child node sizes.
- p_value: raw p-value (None in C&RT).
- p_value_adjusted: Bonferroni-adjusted p-value.
- bonferroni_multiplier: applied Kass M.
- n_merges: number of merges applied.
- threshold: numeric threshold (continuous only).
- branches: category groups per branch (categorical and binned CHAID splits).
- impurity_gain: impurity gain (C&RT only).
- bin_edges: tuple of strictly increasing finite numeric cut points for binned
  continuous predictors in CHAID / CHAID_EXHAUSTIVE (empty tuple otherwise).
  Note: `bin_edges` is part of each node's immutable `SplitConfig` (for
  routing and export) and is **not** included as a global parameter in
  `TreeModel.params_fingerprint`.

### 4.2. Validated invariants

In the constructor (__post_init__) the following is verified:
- method ∈ {"CHAID", "CHAID_EXHAUSTIVE", "CRT", "QUEST"}.
- method ↔ statistic_name ↔ required-field coherence.
- Exactly one of threshold / branches is defined.
- branches forms a real partition (non-empty groups, disjoint categories).
- bin_edges, when non-empty, contains strictly increasing finite floats and
  requires method ∈ {"CHAID", "CHAID_EXHAUSTIVE"} with branches defined.
- len(child_ns) matches the number of branches.
- sum(child_ns) ≤ parent_n.
- p_value_adjusted ≥ p_value (Bonferroni never reduces).

---

## 5. Anti-leakage imputation (TrainOnlyImputer)

### 5.1. MRM rule

Imputation statistics (mean for continuous, mode for categorical) are computed EXCLUSIVELY on the training fold. The same value is applied to any other fold (test, OOS, OOT).

### 5.2. Rationale

Computing the mean over the full dataset introduces data leakage: the model "sees" information from the test set before being evaluated. Train-only imputation prevents this leak and is a regulatory requirement (SR 11-7).

### 5.3. Determinism in ties

If the mode is tied:
- Orderable labels → the smallest one.
- Non-comparable labels → first in order of appearance (sequential pass, not pandas' internal order).

### 5.4. Outlier policy (SR 11-7)

Under SR 11-7 model risk governance, TreeGov enforces an explicit three-part
policy on non-finite values and finite outliers:

1. **Fail-fast rejection of non-finite values (`±inf`).** `TrainOnlyImputer`
   rejects `±inf` in numeric columns during both `fit()` and `transform()`
   (preventing `mean = NaN` from `[+inf, -inf]`). All analytical engines
   (`CrtEngine`, `ChaidEngine`, `QuestEngine`), `TreeBuilder._partition`,
   `validation` and `StabilityMonitor` likewise reject `±inf` with
   `ValueError`.
2. **Structural robustness of rank/cut-based splits for finite outliers.**
   Because C&RT continuous splits depend only on rank order (midpoints between
   consecutive values) and CHAID continuous binning depends on empirical
   quantiles (`1/11 .. 10/11`), finite extreme values do not distort split
   geometry or leaf probabilities the way they distort linear/logistic
   regression coefficients.
3. **Analyst responsibility for domain capping / winsorizing (and QUEST
   exception).** TreeGov does **not** perform automatic silent winsorizing or
   outlier deletion, so the raw data distribution remains auditable. The
   modelling analyst is explicitly responsible for validating extreme finite
   observations and, when warranted by institutional risk policy, applying
   documented *winsorizing* or *capping* upstream. **Exception:** in **QUEST**,
   Stage 1 (ANOVA F) and Stage 2 (univariate QDA) estimate parametric class
   means and variances, which **are** sensitive to extreme finite outliers;
   analysts using QUEST on heavy-tailed predictors should inspect and cap
   outliers prior to training.

---

## 6. Jeffreys estimator and PD Floor

### 6.1. Empirical PD

PD_empirical(t) = k(t) / N(t)

where k(t) is the event count in node t and N(t) its population.

### 6.2. Jeffreys Bayesian estimator

Non-informative prior Beta(0.5, 0.5). Posterior mean:

PD_Jeffreys(t) = (k(t) + 0.5) / (N(t) + 1.0)

Property: as N(t) → ∞, PD_Jeffreys → PD_empirical.
Property: if k(t) = 0, PD_Jeffreys > 0 always.

### 6.3. Regulatory floor

No exposure may have a PD below the applicable regulatory floor. The
Basel Framework consolidated (CRE 32.4) sets the floor at **0.05%
(5 bps) for corporate, bank and retail exposures**; sovereign
exposures are exempt (or 0.03% depending on the jurisdiction). The
previous value (0.03% / 3 bps) was the Basel II floor and applied
before the 2017 reform.

PD_final(t) = max(PD_floor, PD_Jeffreys(t))    with PD_floor = 0.0005
                                               (default in Banking mode)

**Sovereign exception not modelled.** TreeGov's default `pd_floor`
is the CRE 32.4 value for non-sovereign exposures. Analysts with
sovereign exposure must pass `pd_floor=0.0003` explicitly.

**Citation**: Basel (BCBS CRE 32.4), EBA/GL/2017/16, IFRS 9.

### 6.4. Governance modes

TreeGov supports two modes (`backend_v3.types.GovernanceMode`):

- **Banking (default):** Jeffreys estimator + PD Floor (BCBS CRE 32.4, non-sovereign).
- **Research:** raw empirical PD (k/n) without Bayesian smoothing or
  floor, for non-banking domains (health, social sciences, marketing)
  where regulatory constraints do not apply.

Intermediate combinations (e.g. Jeffreys without a floor) are reachable
through the API; `TreeModel.params_fingerprint` labels the effective mode
("BANKING" | "RESEARCH" | "CUSTOM"), so two trees trained under
different governance never share the same fingerprint.

### 6.5 RESEARCH mode — raw PD without Jeffreys smoothing or floor

The `GovernanceMode.RESEARCH` mode produces raw empirical PDs without
Bayesian smoothing or regulatory floor:

    pd_final = pd_jeffreys = k(t) / N(t)

where `k(t)` is the event count in node `t`, and `N(t)` is its
population.

**Formula (RESEARCH).**

    pd_j = k / n           (raw, no shrinkage)
    pd_final = pd_j        (no floor)

**Rationale.** RESEARCH mode is designed for non-banking domains
(health, social sciences, marketing) where:
- The prior information embedded in Jeffreys is not obviously
  justified.
- The regulatory floor of 5 bps (BCBS CRE 32.4) does not apply.

Making the mode explicit — and labelling it in the fingerprint —
allows the same engine to serve two very different audiences without
silent modification of the mathematics.

**Consequences.**
- `pd_final` can be exactly `0.0` when `k = 0`, which is impossible
  under BANKING (Jeffreys ensures `pd_j > 0` for any `k ≥ 0`).
- Two trees with the same data but different modes produce different
  PDs and different fingerprints. This is intentional (see
  `docs/design_decisions.md` §0.3 and §10.2).
- The `_governance_label()` function returns `"RESEARCH"` when
  `apply_jeffreys = False` and `pd_floor = None`.

**Citation:** See `docs/methodology.md` §6.4 for the governance modes
and `docs/design_decisions.md` §0.3 for the design rationale.

> See `docs/design_decisions.md` §5.2 and §5.3 for the related
> `pd_final` scalar decision.

### 6.6 Multivariate Jeffreys estimator (Phase 3.1)

In Phase 3.1 the Jeffreys estimator was generalised to the multiclass
case (K ≥ 2). The class of interest always sits at index 0 of the
per-class probability vector (canonical reordering, see
`docs/3.1_design_multiclass.md` §3.3).

**Formula (multivariate Jeffreys).**

    pd_jeffreys[c] = (k_c + 0.5) / (n + K * 0.5)

where `k_c` is the count of class `c` in the node, `n` is the node
population, and `K` is the total number of classes.

**Properties.**

- **Sum invariant.** `sum(pd_jeffreys) = (sum(k_c) + K*0.5) / (n + K*0.5) = 1`
  exactly, since `sum(k_c) = n`.
- **Exact reduction to the binary case.** For K = 2:
  `pd_jeffreys[c] = (k_c + 0.5) / (n + 1.0)`. Zero numerical change
  with respect to the pre-3.1 binary estimator (§6.2).
- **Prior.** It is the posterior mean under a symmetric
  Dirichlet(0.5, 0.5, ..., 0.5) prior — the natural extension of the
  Jeffreys prior to categorical distributions.

**pd_floor in the multivariate case.** For K > 2 the floor is applied
component-wise and the vector is renormalised to preserve the invariant
`sum(pd_final) == 1`:

    pd_temp[c] = max(pd_floor, pd_jeffreys[c])
    pd_final[c] = pd_temp[c] / sum(pd_temp)

This is a **soft floor**: each component is guaranteed a minimum of
`pd_floor / sum(pd_temp)`, not exactly `pd_floor`.

**Note on K=2 reduction (updated in Phase 3.7.e).** For K = 2 the
implementation applies a **hard floor** (BCBS CRE 32.4), not the
soft-floor renormalization used for K > 2. When the
class-of-interest PD `pd_jeffreys[0]` falls below `pd_floor`, the
implementation sets `pd_final[0] = pd_floor` and
`pd_final[1] = 1 - pd_floor`. This guarantees that the
class-of-interest component satisfies the regulatory floor exactly.
For K > 2 the soft floor applies (see above): component-wise
`max(pd_floor, pd_jeffreys[c])` followed by renormalization to
`sum == 1`. The K=2 hard bound is enforced by
`tests/test_tree_builder.py::test_pd_floor_hard_bound_binary` and
`tests/test_tree_builder.py::test_pd_floor_hard_bound_binary_default`.
For K > 2, the soft floor can leave `pd_final[c]` slightly below
`pd_floor` after renormalization; this is by design and documented.

**Citation:** Jeffreys, H. (1946). An invariant form for the prior
probability in estimation problems. *Proceedings of the Royal Society
of London A*, 186(1007), 453-461.

**Cross-reference:** `docs/3.1_design_multiclass.md` §3.2 and §3.3 for
the phase design; `docs/design_decisions.md` §5.2 for the tuple-fields
decision.

### 6.7 Weighted Jeffreys estimator and strict governance classification (Phase 3.2, Block 2B)

When sample weights are provided (`TreeBuilder(..., weights=...)`), the
multivariate Jeffreys estimator replaces raw counts `k_c` and `n` with the
node's per-class weighted masses `W_c = Σ_{i: y_i = c} w_i` and total mass
`W = Σ_c W_c` (`backend_v3/tree_builder.py`):

    pd_jeffreys[c] = (W_c + 0.5) / (W + 0.5 · K)

With `weights=None`, `W_c = k_c` and `W = n` (exact bit-for-bit parity).

**Weight-scale sensitivity.** Because the symmetric Dirichlet(0.5, …, 0.5)
pseudocount `0.5` is fixed on the count scale, weighted Jeffreys is **not**
scale-invariant in `w`:
- **Normalized weights (`Σ w_i = 1`, or `W ≪ 0.5 · K`):** the pseudocount
  dominates and shrinks `pd_jeffreys[c]` strongly toward the uniform prior
  `1 / K`.
- **Large weights (`W ≫ n`):** the prior is attenuated and `pd_jeffreys[c]`
  converges toward the unsmoothed weighted empirical rate `W_c / W`.

Analysts using weighted `BANKING` models should scale weights deliberately
(e.g., mean weight `1.0` so `W ≈ n`) when the intended Jeffreys shrinkage
corresponds to effective sample size.

**Strict governance classification (`classify_governance_mode`, Block 2B).**
Effective governance is classified by a single source of truth
(`backend_v3.tree_builder.classify_governance_mode`, with
`BASEL_PD_FLOOR_MIN = 0.0005` and domain `pd_floor ∈ [0.0, 0.5)`):

- **`BANKING`:** strictly requires `apply_jeffreys=True` **and**
  `pd_floor >= 0.0005` (BCBS CRE 32.4).
- **`RESEARCH`:** strictly requires `apply_jeffreys=False` **and**
  `pd_floor is None`.
- **`CUSTOM`:** any intermediate combination — including `pd_floor == 0.0` or
  legacy Basel II `0.0 < pd_floor < 0.0005` (such as `0.0003` for sovereign
  exposures).

> See `docs/design_decisions.md` §13.5 and §28.

---

## 7. Hamilton-Hare partition (Largest Remainder)

For a dataset with `N` observations, training fraction `train_frac ∈ (0, 1)`
and target training size `N_train = round(N × train_frac)`
(`backend_v3/splitting.py`):

Per stratum `j` (for every observed class in `y`):

1. Ideal quota: `Q_j = N_j × train_frac`.
2. Integer part: `n_j = floor(Q_j)`.
3. Remainder: `R = N_train − Σ_j n_j`.
4. Allocation of the `R` remaining observations: the classes with the largest
   residual fraction `f_j = Q_j − n_j` receive `+1` unit each (ties broken
   deterministically by class order).

**Missing-target guard (Block 2F).** Both `stratified_split` and
`stratified_kfold` reject any `NaN` / missing values in `y` with `ValueError`
before computing strata.

**Small-class caveat and `check B2` (weighted mode).** Under arbitrary
`train_frac` near `0` or `1`, a small stratum (even with `N_j ≥ 2`) can
receive `0` rows on one side of an unweighted holdout split (for example,
`N_j = 2` with `train_frac = 0.1` has `Q_j = 0.2`, `n_j = 0`). In **weighted
mode** (`weights is not None`), stratification still uses physical row counts
`N_j` (preserving exact index parity with unweighted mode), and **`check B2`**
enforces fail-fast that every observed class retains **at least 2 physical
rows in train AND at least 2 physical rows in test** (`ValueError` otherwise).

### 7.1 Cost-complexity pruning (Breiman 1984)

Post-pruning is implemented after tree growth. The weak-link pruning
algorithm computes, for each internal node `t` with a live subtree
`T_t`, the value:

    g(t) = (r(t) − R(T_t)) / (|T_t| − 1)

where:
- `r(t) = min(k_t, n_t − k_t)` — misclassifications of node `t` as a
  leaf, in **count form**.
- `R(T_t)` — sum of `r(leaf)` over the live leaves of the subtree.
- `|T_t|` — number of live leaves in the subtree.

**Phase 3.9 (Weighted Pruning).** When the tree was built with sample weights (`w_events` is populated in `TreeNode`), the cost-complexity pruning must use the weighted mass to remain mathematically coherent with the tree's growth. The weighted formulation is:

    r_w(t) = sum(w_events) - max(w_events)

For K=2, this is identical to `min(w_events[0], w_events[1])`. If `TreeNode.w_events` is empty (unweighted trees), the original count form `r(t)` applies, preserving bit-for-bit parity with previous versions.

**Convention: count form.** `r(t)` is expressed as a raw count, not the
probability-weighted `p(t) · r(t)` of Breiman's original exposition.
The two forms differ by a positive constant common to all nodes in the
same tree; the **sequence** of pruning steps (the order in which nodes
are pruned) is identical, only the units of α change (errors per node
instead of errors per unit probability).

**Tie handling.** All nodes with the minimal `g(t)` are pruned in the
same step. This is the standard Breiman convention for ties.

**Idempotence.** `prune(alpha)` always recomputes from the **original**
tree, never from an already-pruned tree. This ensures the pruning
sequence is a property of the original tree, independent of history.

**Reindexing.** After pruning, the surviving nodes are renumbered by
BFS from the root: `0..m−1`, contiguous. This preserves the
`TreeModel` invariant `node_id == index in nodes tuple`. Leaves created
by pruning receive `leaf_reason="podado"`.

**Citation:** Breiman, L., Friedman, J. H., Olshen, R. A. & Stone, C.
J. (1984). *Classification and Regression Trees*, Chapter 3. Wadsworth.

> See `docs/design_decisions.md` §8.1, §8.2, §8.3 and §8.4 for the full
> rationale of each decision.

### 7.2 Stratified k-fold cross-validation (Phase 2.1.b)

`backend_v3.splitting.stratified_kfold(y, k, seed)` returns `k` disjoint
`(train_idx, val_idx)` pairs. The stratification is the same Largest
Remainder idea as §7, applied **inside each class across the `k` folds**
(henceforth "Hamilton-Hare in k folds"):

1. Each class `c` with `n_c` rows is permuted deterministically with
   `np.random.default_rng(seed)`.
2. The permuted rows of class `c` are dealt round-robin into folds
   `0, 1, …, k−1`, so fold `f` receives `⌊n_c / k⌋` or `⌈n_c / k⌉`
   rows of that class. This deal is exactly the Hamilton-Hare allocation
   of §7: base quota `⌊n_c / k⌋` per fold plus the `R = n_c mod k`
   leftover rows assigned one each to folds `0..R−1` (the largest-remainder
   tie is broken by fold index, hence deterministic).
3. `val_idx` of fold `f` is the union of its class shares; `train_idx`
   is its complement over `0..N−1`.

Consequences, all required for a valid CV report:

- **Exact coverage and disjointness.** Every row appears in exactly one
  validation fold; `val_idx` ∪ `train_idx` = `0..N−1` per fold. No row is
  validated twice and none is left out.
- **Proportion preservation.** Each fold reproduces the global event rate
  to within one row per class, which is the Hamilton-Hare guarantee of
  §7 extended to `k` quotas instead of two.
- **Determinism.** Same `seed` ⇒ bit-identical folds. No fold depends on
  the order of the previous folds.
- **Validity floor.** `k ∈ [2, 20]` and every class must have at least
  `k` rows; otherwise `stratified_kfold` raises `ValueError` instead of
  silently producing an empty validation fold.

**Aggregation.** `Session.evaluate_oos` trains one temporary model per
fold on `train_idx`, scores `val_idx`, and reports
`metrics_per_fold` together with the arithmetic mean and the standard
deviation across folds (population form, `ddof=0`, matching
`np.std`):

    metrics_mean[m] = (1/k) · Σ_f metric_f(m)
    metrics_std[m]  = sqrt( (1/k) · Σ_f (metric_f(m) − metrics_mean[m])² )

The std is the dispersion the reviewer needs to judge stability; a good
mean with a large std is not evidence of a robust model. Only finite
numeric fields enter the aggregate; non-numeric or non-finite fields are
omitted from `metrics_mean` / `metrics_std` and remain visible per fold.

**Final model.** The deployed tree is **not** one of the fold models: after
CV, `Session` trains it on **100 %** of the rows (`_X_train` = all data,
`_X_test = None`). Fold models exist only to estimate the metric
distribution. The fingerprint records `validation_scheme="cv"` and `cv_k`,
so a CV-trained model is never confused with a holdout one.

**Citation:** Kohavi, R. (1995). A study of cross-validation and bootstrap
for accuracy estimation and model selection. *IJCAI*, 1137–1143 (stratified
k-fold). Hamilton-Hare per §7. See `docs/design_decisions.md` §6.1 and
`docs/api.md` (`Session.partition(scheme="cv")`, `Session.get_cv_report`).

---

## 8. Validation metrics

### 8.1. Canonical Gini

> **Note on Gini conventions.** TreeGov uses
> **Gini = 2·AUC − 1**, where AUC is computed by
> Wilcoxon-Mann-Whitney with mid-ranks. This is the standard convention
> in credit scoring and banking MRM.
>
> Not to be confused with:
> - The alternative convention **Gini = AUC − 0.5** (range 0 to 0.5),
>   used in some academic contexts.
> - The **economic Gini coefficient** (income inequality).
>
> Confusion between these three conventions is common in the industry;
> documenting the chosen one is an MRM traceability requirement.

Derived from the area under the ROC curve (AUC) via the Wilcoxon-Mann-Whitney U statistic:

AUC = U / (n_1 × n_0)
Gini = 2 × AUC − 1

where U = R_1 − n_1(n_1 + 1)/2, with R_1 the sum of ranks of the event observations (using mid-ranks for ties).

**Citation:** Hanley, J.A. & McNeil, B.J. (1982).

### 8.2. Kolmogorov-Smirnov

KS = max_s |F_bad(s) − F_good(s)|

Maximum vertical distance between the cumulative distribution functions of events and non-events. For multiclass targets (`K > 2`), TreeGov reports the minimum symmetrized pairwise KS across all class pairs as a conservative worst-case discrimination metric (see §8.11).

**Citation:** Massey, F.J. (1951).

### 8.3. Hosmer-Lemeshow (external OOS/OOT calibration)

H = Σ_g (O_g − N_g π̄_g)² / [N_g π̄_g (1 − π̄_g)]

TreeGov computes Hosmer-Lemeshow on **external validation samples (OOS/OOT)**
using **tie-preserving quantile grouping** (Block 2F): ordered score blocks
advance to the end of any tie block so the grouping — and therefore `H` and
`p` — is **strictly invariant to row permutations** of `X_test`. Because model
parameters are estimated on train rather than on the validation cohort, the
reference distribution under H₀ has **external degrees of freedom**:

    H ~ χ²(G_eff)       (df = G_eff, where G_eff is the number of non-empty
                         tie-preserving groups; Hosmer, Lemeshow & Sturdivant
                         2013, §5.2.2)

If `p > 0.05`, H₀ is not rejected (calibrated model). See §8.9 for extreme-
probability handling (`_HL_EPS = 1e-6`) and §8.9bis for weighted HL.

**Citation:** Hosmer, D.W. & Lemeshow, S. (1980) (original goodness-of-fit
formulation); Hosmer, D.W., Lemeshow, S. & Sturdivant, R.X. (2013), *Applied
Logistic Regression* (3rd ed.), §5.2.2, Wiley (`df = G_eff` in external OOS/OOT
validation).

### 8.4. Brier Score and BSS

BS = (1/N) Σᵢ (yᵢ − p̂ᵢ)²
BSS = 1 − BS / BS_ref

where BS_ref = ȳ(1 − ȳ) is the Brier Score of the null model.

**Citation:** Brier, G.W. (1950).

### 8.5. PSI, CSI and Gini Drop (Phase 1.3 monitoring, `backend_v3/stability.py`)

**Population Stability Index (PSI)** over the tree-leaf distribution and
**Characteristic Stability Index (CSI)** per covariate, always against the
**training partition** (the development population, by definition).

```
PSI = Σ_k (P_actual,k − P_expected,k) · ln(P_actual,k / P_expected,k)
    = KL(actual || expected) + KL(expected || actual)    (symmetric KL)
```

TreeGov policy (updated in Block 2F):
- Configurable clip `eps` (default `ε = 1e-4`, validated finite in `(0, 0.5)`)
  per bin **before the log and without renormalization** by default
  (`renormalize=False`): this preserves the signal of empty OOT bins; the scale
  error is negligible against the 0.10 / 0.25 thresholds when bins are
  non-empty. `StabilityMonitor(..., eps=...)` forwards `self.eps` to both
  `leaf_psi` and `covariate_csi`.
- Leaf PSI: bins are the leaves. OOT rows that cannot be routed (unseen
  categories/values) form the extra bin `<UNSEEN>` with `P_expected = ε`.
  Empty or zero-mass cohorts are rejected fail-fast, and `leaf_psi` divides
  strictly by total cohort weight (`total_act`), preserving scale invariance
  even when `Σ w_oot < 1`.
- CSI: continuous variables reject `±inf`, separate `NaN` into an explicit
  `<MISSING>` bin (preserving probability sum `1.0`), handle 100%-`NaN` and
  constant-train covariates (`==v0` + `<OTHER>`), and otherwise bin non-`NaN`
  values into **deciles learned on train only** with `np.digitize(..., right=True)`
  so intervals are `(a, b]` (first and last bins open: `−∞` / `+∞` absorb
  out-of-range OOT values). Nominal variables use train categories, track `NaN`
  in `<MISSING>`, and group unseen OOT categories into `<OTHER>` with
  `P_expected = ε`.

Industry-standard monitoring thresholds (Siddiqi 2006; not prescribed
by Basel or EBA):
- PSI/CSI < 0.10 → STABLE.
- 0.10 ≤ PSI/CSI < 0.25 → MODERATE.
- PSI/CSI ≥ 0.25 → UNSTABLE.

**Gini Drop (relative degradation of discriminative power):**

```
drop_X = (Gini_train − Gini_X) / Gini_train      (X in {OOS, OOT})
alert: drop > 0.40 → CRITICAL;  drop > 0.20 → WARNING;  else NONE.
NaN or undefined drop → UNDETERMINED.
If Gini_train ≤ 0 → drop = None (undefined; alert = UNDETERMINED; WARNING in log).
```

Temporal governance: the OOT cohort is an external, independent file
(`Session.load_oot`), never a random partition. Temporal order is certified
only when a `time_col` exists in both dev and OOT (else the report is
flagged `temporal_verified=False`: "OOS, not OOT").

**Citation:** Siddiqi, N. (2006). *Credit Risk Scorecards: Developing and
Implementing Intelligent Credit Scoring*. Wiley.

### 8.5bis Weighted PSI and CSI — each cohort carries its own weights

OOT monitoring compares the tree-leaf distribution (PSI) and each
covariate (CSI) between train (reference) and the OOT cohort. With
per-sample weights, **each cohort uses its own weights** to represent its
own population:

    p_exp,k = Σ weights_train in bin k / Σ all weights_train
    p_act,k = Σ weights_oot   in bin k / Σ all weights_oot
    PSI     = Σ_k (p_act,k − p_exp,k) · ln(p_act,k / p_exp,k)

The bins are unchanged: leaves for PSI, train-learned deciles for
continuous CSI, train-observed categories for nominal CSI. The `<UNSEEN>`
bin (PSI) and `<OTHER>` bin (CSI) accumulate the **sum of weights** of the
non-assignable / unseen rows, not their count.

**Convention.** If train and OOT share the same population composition,
the weights coincide and PSI reflects only the change in the model
distribution. If they differ (real population drift), PSI captures both
changes.

**Alternative mode.** With `weight_oot=False` in `Session.evaluate_oot`,
the OOT cohort uses uniform weights (measures only the model drift,
ignoring the OOT cohort bias).

**Citation:** Siddiqi (2006), §8.5 (PSI/CSI with weights in scorecards).

> See `docs/design_decisions.md` §13.10 for the full decision rationale.

### 8.6 Asymmetric decision threshold (Business decision, not IFRS 9 provision)

Expected loss function:

E[Loss](θ) = C_FN × FN(θ) + C_FP × FP(θ)

where:
- C_FN = LGD × EAD (false-negative cost).
- C_FP = NIM (false-positive cost).

Search for θ* = argmin_θ E[Loss](θ) via grid search.

**Scope: conceptual business-decision reference — not implemented as a
provisioning engine and not an IFRS 9 prescription.** This section documents
the standard Bayesian cost-minimization cut-off as a conceptual reference for
analysts choosing an operating threshold `threshold` in
`build_classification_matrix`. TreeGov does **not** implement an automated
threshold optimizer or provisioning engine from this formula (the stored
`cost_matrix` in `SessionState` is traceability metadata; see
`design_decisions.md` §18.8). θ* minimises the institution's own
misclassification cost; it is **not** a provision, an ECL measurement, nor a
threshold that IFRS 9 requires. IFRS 9 prescribes how to measure expected
credit losses (see §9 below); it does not prescribe the cut-off at which a
model classifies an exposure as bad. The cost matrix (`C_FN`, `C_FP`) is an
input of the business owner, not a regulatory constant, and any θ* is only as
defensible as those two values.

Consequences:
- Changing `C_FP` (for example a new NIM assumption) moves θ* without
  touching the model, the data or the ECL calculation. θ* is not part of
  the model fingerprint.
- θ* must be documented with its cost matrix and re-approved whenever the
  business inputs change; an MRM reviewer will ask for both.
- Do not report θ* as "the IFRS 9 threshold". The correct label is
  "cost-optimal threshold under the declared cost matrix".

### 8.7 PSI with configurable clip ε (default 1e-4) and no renormalization

The Population Stability Index (see §8.5) uses a natural logarithm. When
a bin's probability is zero (either in the expected or the actual
distribution), the log is undefined. TreeGov clips each probability to a
configurable floor `eps` (default `ε = 1e-4`, validated finite in `(0, 0.5)`,
no booleans) **without renormalizing** the resulting vector by default.

**Formula.**

    p_k ← max(p_k, eps)   for every bin k    (default eps = 1e-4)
    PSI = Σ_k (p_act,k − p_exp,k) · ln(p_act,k / p_exp,k)
    (no renormalization after clipping when renormalize=False)

**Rationale.** If a bin present in train vanishes in OOT (or vice
versa), the correct signal is "this bin's probability dropped to ~0",
which is genuine drift. Renormalizing the probabilities after clipping
would dilute this signal — the very thing PSI is designed to detect.
The scale error from not renormalizing is negligible compared to the
0.10 / 0.25 thresholds when bins are non-empty.

**Configuration.** Both `psi_index(..., eps=1e-4, renormalize=False)` and
`StabilityMonitor(eps=1e-4, renormalize=False)` expose `eps` and
`renormalize` (canonical renormalized variant: `renormalize=True`).

**Citation:** Siddiqi, N. (2006). *Credit Risk Scorecards*. Wiley.

> See `docs/design_decisions.md` §7.4 and §32 for the full decision rationale.

### 8.8 CSI: deciles learned on train, `(a, b]` intervals, `<MISSING>` and constant covariates

The Characteristic Stability Index (CSI) is PSI computed per covariate.
For continuous covariates, TreeGov rejects `±inf`, separates `NaN` into an
explicit `<MISSING>` bin, and bins finite non-`NaN` observations into
**deciles learned on the training partition only** using
`np.digitize(..., interior, right=True)`, yielding half-open `(a, b]`
intervals with open extreme bins:

    bin_0   = (−inf,  q_10]
    bin_1   = (q_10, q_20]
    ...
    bin_9   = (q_90, +inf)

where `q_10, …, q_90` are the unique interior deciles of non-`NaN` training
values.

**Edge cases (Block 2F).**
- **Constant continuous covariate in train (`v_0`):** encoded with two bins
  `==v0` and `<OTHER>` (plus `<MISSING>` if `NaN` occurs), so drift away from
  `v_0` in OOT is detected instead of returning a false `CSI = 0`.
- **All-`NaN` covariate in train:** encoded as `["<MISSING>"]` (or
  `["<MISSING>", "<OTHER>"]` if OOT introduces finite values).
- **Nominal covariates:** bins are the non-null categories observed in train;
  `NaN` values go to `<MISSING>` and unseen OOT categories are grouped into
  `<OTHER>` with `p_expected = eps`.

**Rationale.**
- **Learned on train:** anti-leakage rule (see §5). The bins must not
  depend on OOT data.
- **Open extreme bins and `<MISSING>`:** an OOT value outside the train range
  or an increase in missingness is genuine drift and contributes directly to
  CSI while keeping `Σ p_exp = Σ p_act = 1`.

**Citation:** Siddiqi, N. (2006). *Credit Risk Scorecards*. Wiley.

> See `docs/design_decisions.md` §7.5 and §32 for the full decision rationale.

### 8.9 Hosmer-Lemeshow: tie-preserving grouping, external `df = G_eff` and `_HL_EPS = 1e-6` (Block 2F)

The Hosmer-Lemeshow statistic (see §8.3) has the term:

    H = Σ_g (O_g − N_g π_g)² / [N_g π_g (1 − π_g)]

In practice, `π_g` can hit `0` or `1` (for example, a pure leaf under
`RESEARCH` mode without Jeffreys smoothing or PD floor).

**Formula and rules (Block 2F, `backend_v3/validation.py`).**

1. **Tie-preserving grouping:** sorted predicted probabilities are partitioned
   into up to `n_groups` buckets while advancing every boundary past tied
   scores, making `H`, `G_eff` and `hl_p` strictly invariant to input row
   order.
2. **External degrees of freedom:** `hl_groups = G_eff`, `hl_df = G_eff`,
   `hl_p = χ²_sf(H, G_eff)` (Hosmer, Lemeshow & Sturdivant 2013, §5.2.2).
3. **Exact extreme match:** if `(π_g == 0 and O_g == 0)` or
   `(π_g == 1 and O_g == N_g)`, the group contributes **`0.0`** exactly without
   warning.
4. **Numerical clip (`_HL_EPS = 1e-6`):** otherwise, if `π_g < 1e-6` or
   `π_g > 1 − 1e-6`, `π_g` is clipped to `[1e-6, 1 − 1e-6]` and an explicit
   `WARNING` is emitted in the log.

**Rationale.** Replacing the legacy `1e-15` clip with `_HL_EPS = 1e-6`
prevents artificial `~1e15` explosions when a `RESEARCH`-mode leaf predicts
`0.0` and encounters a single OOS event, while still flagging severe
miscalibration loudly and keeping `H` finite without silently dropping groups.

**Citation:** Hosmer, D.W., Lemeshow, S. & Sturdivant, R.X. (2013). *Applied
Logistic Regression* (3rd ed.), §5.2.2. Wiley.

> See `docs/design_decisions.md` §7.2 and §32 for the full decision rationale.

### 8.9bis Weighted validation metrics and check B2

When sample weights `w_i > 0` are active (`backend_v3/validation.py`,
`backend_v3/reporting.py`, `backend_v3/splitting.py`), all evaluation metrics
incorporate `w_i` consistently while preserving exact bit-for-bit parity when
`weights=None` or `w_i ≡ 1`:

- **Weighted AUC & Gini (`_pair_auc_ks`):** concordant and tied pairs are
  weighted by `w_i · w_j`, divided by `W_1 · W_0` (`W_1 = Σ_{y=1} w_i`,
  `W_0 = Σ_{y=0} w_i`). Scale-invariant in `w`.
- **Weighted KS:** maximum vertical distance between the weighted empirical
  CDFs `F_bad^w(s)` and `F_good^w(s)`. Scale-invariant in `w`.
- **Weighted PR-AUC:** step-wise Average Precision using weighted true
  positives `TP_w` and weighted predicted positives `TP_w + FP_w`.
  Scale-invariant in `w`.
- **Weighted Brier Score and BSS:**
  `BS_w = (Σ_i w_i (y_i − p̂_i)²) / W`, with weighted prevalence
  `ȳ_w = (Σ_i w_i y_i) / W` and `BS_ref,w = ȳ_w (1 − ȳ_w)` (multiclass
  generalization in §8.12). Scale-invariant in `w`.
- **Weighted Hosmer-Lemeshow:** per-group aggregates become weighted sums
  `O_g^w = Σ_{i ∈ g} w_i y_i`, `N_g^w = Σ_{i ∈ g} w_i`,
  `π_g^w = (Σ_{i ∈ g} w_i p̂_i) / N_g^w`. Because both numerator and
  denominator scale linearly with `W`, **weighted HL scales linearly with the
  total weight mass** (not scale-invariant; see `docs/design_decisions.md`
  §13.8).
- **Weighted accuracy (`w_accuracy`, Block 2F):** populated in both binary
  (`K = 2`) and multiclass (`K > 2`) classification matrices as
  `w_accuracy = (Σ_i w_i · 1[ŷ_i = y_i]) / W` (for binary:
  `(w_tp + w_tn) / w_total`), matching `accuracy` exactly under uniform
  weights.
- **Stratification guard (`check B2`):** in weighted mode,
  `splitting.stratified_split` validates `weights` (1D, finite, strictly
  positive) and enforces `check B2`: every class must retain **at least 2
  physical rows in train and at least 2 physical rows in test** (§7).

**Citation:** Heeringa, West & Berglund (2010), §5.3.
**MRM scope clarification:** TreeGov applies direct weight-mass weighted tables
and moments **without** complex-survey design corrections (no Rao-Scott
adjustment and no design-effect DEFF rescaling). See
`docs/design_decisions.md` §13.6–§13.8 and §32.

### 8.10 PR-AUC as step-wise Average Precision

Precision-Recall AUC has multiple definitions in the literature. TreeGov
uses the **step-wise Average Precision** without trapezoidal
interpolation.

**Formula.**

    AP = Σ_i (R_i − R_{i−1}) · P_i

where `R_i` and `P_i` are the recall and precision at the `i`-th
operating point (ordered by descending score), and `R_0 = 0`.

**Rationale.** Davis & Goadrich (2006) showed that linear interpolation
between operating points of a PR curve produces points that are not
achievable by any threshold — the interpolated points are outside the
achievable frontier. The step-wise sum is the correct estimator of the
expected precision under the empirical distribution.

**Consequences.** TreeGov's `pr_auc` matches
`sklearn.metrics.average_precision_score` numerically, though the
implementations are independent (no shared code).

**Citation:** Davis, J. & Goadrich, M. (2006). "The relationship between
Precision-Recall and ROC curves." *Proceedings of the 23rd International
Conference on Machine Learning (ICML)*, 233-240.

> See `docs/design_decisions.md` §7.3 for the full decision rationale.

### 8.11 Multiclass discrimination — Hand & Till AUC, worst-case KS

Phase 3.5.a extended `compute_oos_metrics` to targets with K ≥ 2
classes. The binary path (K = 2) is unchanged; the multiclass path
is documented here.

**Hand & Till (2001) multiclass AUC.**

    For every unordered pair (i, j) with i < j:
      A_ij = P(score_i of a random class-i member > score_i of a random class-j member) + 0.5 * P(tie)
      A_ji = P(score_j of a random class-j member > score_j of a random class-i member) + 0.5 * P(tie)
      pair_contribution(i, j) = (A_ij + A_ji) / 2

    M = (1 / (K*(K-1)/2)) * sum_{i<j} (A_ij + A_ji) / 2
    auc = M
    gini = 2*M - 1

    where K = number of classes.

The per-pair AUCs use the same direct pair-counting kernel as the
binary path (concordant = 1, tied = 0.5, discordant = 0; with weights,
over weighted class masses). The reported `ks_pairs` and `auc_pairs`
tuples expose the per-pair values; the reviewer sees which pair
dominates.

**Worst-case pairwise KS (decision D4).**
ks_pair(i, j) computed over the pair (i, j), evaluated in both directions and symmetrized, following the same logic as Hand & Till's AUC:

    ks_ij = KS with score = column i of p, positives = rows with y == i, negatives = rows with y == j.
    ks_ji = KS with score = column j of p, positives = rows with y == j, negatives = rows with y == i.
    ks_pair(i, j) = 0.5 * (ks_ij + ks_ji)

    ks = min over all pairs of ks_pair(i, j)

The minimum is the worst case, the number an MRM reviewer would use to
challenge the model. For K = 2 there is a single pair and the reported
value equals the binary KS exactly.

**K = 2 parity.** With one pair, M equals the binary AUC by
construction, and the worst-case KS equals the binary KS. The K = 2
result is bit-identical to the pre-3.5 computation given identical
inputs.

**Citation:** Hand, D.J. & Till, R.J. (2001). A simple generalisation of
the area under the ROC curve for multiple class classification
problems. *Machine Learning*, 45(2), 171–186. Decision D1 and D4; see
`docs/3.5_design_multiclass_weighted_reports.md` §2.1 and §2.3.

> See `docs/design_decisions.md` §7.1 for the Gini convention, and
> §8.1 above for the binary case.

**Related defaults feeding these metrics.** C&RT tree growth accepts
only splits with impurity gain above `min_impurity_decrease = 1e-9`
(see `docs/design_decisions.md` §3.1), so the leaves behind every
reported metric already satisfy that threshold. Row scoring through
`predict_pd` is governed by `unseen_policy` (see
`docs/design_decisions.md` §7.6): `Session.evaluate_oos` uses the
default `"error"` (a row that cannot be routed aborts the evaluation),
while `Session.evaluate_oot` uses `"exclude"` and reports the count in
`n_excluded`.

### 8.12 Multiclass calibration — Brier, BSS, Hosmer-Lemeshow block

Phase 3.5.a generalised the Brier score and Brier skill score to K ≥ 2
classes and blocked the Hosmer-Lemeshow test by design.

**Multiclass Brier score (decision D6, factor 1/2 per D12).**

    Y_ik = 1 if observation i belongs to class k, else 0
    brier = (1 / (2 * N)) * sum_i sum_k (Y_ik - p_ik)^2

The factor 1/2 makes the K = 2 case reduce exactly to the conventional
binary Brier score, since the two class terms sum to twice the binary
squared error. Without the factor, K = 2 parity would break.

**Multiclass Brier skill score.**

    pi_k = (sum_i w_i * Y_ik) / W          (weighted empirical class frequency)
    brier_ref = (1/2) * sum_k pi_k * (1 - pi_k)
    brier_skill = 1 - brier / brier_ref    (NaN when brier_ref == 0)

For K = 2, `brier_ref` reduces to `pi_event * (1 - pi_event)`, which
matches the binary reference score of §8.4 exactly.

**Hosmer-Lemeshow: blocked by design (decision D5, typing per D16).**

In multiclass mode the fields `hl_stat`, `hl_df` and `hl_p` of the
`OOSMetrics` DTO are set to `None`; a WARNING is logged citing
Fagerland, Hosmer & Bofin (2012). The Hosmer-Lemeshow statistic is
intrinsically binary: it groups observations by predicted probability
of a single event class. The multinomial extension of Fagerland et al.
introduces a second grouping dimension and a different reference
distribution, which the project evaluated and rejected on
complexity-versus-value grounds. The per-class observed-versus-predicted
rates in the gains table provide the operational calibration view
instead.

The `n_groups >= 3` and `n_groups * 5 <= n` validations of §8.3 are
skipped in multiclass mode (HL is not computed) and preserved in full
for K = 2.

**Citation:** Fagerland, M.W., Hosmer, D.W. & Bofin, A.M. (2012).
Multinomial goodness-of-fit tests for logistic regression models.
*Statistics in Medicine*, 31(30), 4238–4253 (evaluated and rejected).
Decision D5, D6, D12, D16; see `docs/3.5_design_multiclass_weighted_reports.md`
§2.4 and §2.5.

### 8.13 Multiclass PR-AUC — micro-average (K > 2), K = 2 shortcut

Phase 3.5.a generalised the precision-recall area to K ≥ 3 classes via
micro-averaging, with an explicit K = 2 shortcut for parity.

**Micro-average (K > 2).**

    Pooled problem: N * K examples, one per (observation, class) pair.
    Example (i, k) is positive iff y_i == k, negative otherwise.
    Score = p[i, k], weight = w_i (per-observation weight).

    The pooled PR curve is integrated step-wise, exactly as in the
    binary case (see §8.10):

        AP = sum_i (R_i - R_{i-1}) * P_i

    with operating points ordered by descending pooled score and
    R_0 = 0.

**K = 2 shortcut (decision D14).** For K = 2 the design reports the
same target-class PR-AUC as the pre-3.5 binary path, not the
micro-average of the pooled problem. The shortcut is documented in
the implementation docstring so that parity holds bit-for-bit.

**Citation:** Davis, J. & Goadrich, M. (2006). The relationship between
Precision-Recall and ROC curves. *ICML*, 233–240. Decision D7 and D14;
see `docs/3.5_design_multiclass_weighted_reports.md` §2.6.

### 8.14 Multiclass reports — gains table, K×K matrix, adaptive n_groups

Phase 3.5.b generalised the two report DTOs to K ≥ 2 classes and closed
the deferred §13.7 for the multiclass path (decision D13). Phase 3.5.c
unblocked the Session-level calls.

**Gains table (decision D2).** A single table ordered by the predicted
probability of the class of interest (ascending, bureau convention).
Each row carries per-class columns (n_per_class, cumulative and
decumulative siblings, and their weighted counterparts in the weighted
mode) in canonical class order. `class_labels` is propagated from the
model.

**Classification matrix (decision D3, DTO per D19).** A K×K
contingency table of true class (rows) versus predicted class
(columns), canonical order on both axes. Per-class precision, recall
and F1; `accuracy` = trace / n_total, populated in both K = 2 and K > 2.
The binary fields of the DTO (`tp`, `tn`, `fp`, `fn`, `precision`,
`recall`, `f1`, `bad_capture_rate`, `n_good`, `n_bad`) keep their
meaning for K > 2 by grouping the class of interest (index 0) as
positive and the remaining classes as negative. Assignment is argmax
of the predicted probability vector; the binary `threshold` is ignored
in K > 2 and recorded as NaN for traceability.

**Discrimination metrics.** For K > 2 the gains-table `ks`, `auc` and
`gini` are computed by calling `validation.compute_oos_metrics` with
the full 2D probability matrix and the label-translated `y` (see
§8.11, §8.13). The `ks_pairs` and `auc_pairs` fields are exposed on
the DTO.

**Adaptive n_groups (decision D20).** `compute_oos_metrics` requires
`n_groups >= 3` and `n_groups * 5 <= n`. To avoid a spurious
`ValueError` on small multiclass gains tables, the reporting layer
computes

    n_groups_eff = min(10, max(3, n // 5))

where `n` is the number of routed rows. If `n < 15` (the minimum for
`n_groups = 3`), `ks`, `auc`, `gini` are set to `None` and the pair
tuples remain empty; the counts, `bad_rate`, `lift` and weighted
columns are still populated. This mirrors the same pattern already
used in `Session.evaluate_oot` (see §8.5).

**Label translation (Session-level, decision Z2).** Internally the
class of interest always sits at index 0 (canonical order). At
evaluation time the Session translates the external `y` labels to the
internal canonical order via a private helper before calling
`compute_oos_metrics`. This preserves the public signature of
`compute_oos_metrics` from Phase 3.5.a and keeps the K = 2 path
untouched.

**Citation:** Breiman et al. (1984), *Classification and Regression
Trees* (per-class error decomposition). Decision D2, D3, D13, D19,
D20; see `docs/3.5_design_multiclass_weighted_reports.md` §3 and §5.

---

## 9. Simplified IFRS 9 / ECL and deterministic staging (Phase 7.0, Block 2C)

`backend_v3.ecl.calculate_ecl` implements a **single-scenario, single-period**
expected credit loss calculation. It is anchored to IFRS 9, Section 5.5
(impairment) and Appendix A (credit-impaired financial assets), and is
deliberately narrower than a full accounting engine.

**Inputs and validation.** Required columns: `exposure_id`, `ead`, `lgd`,
`days_past_due`, `pd_initial`, plus the non-empty PD column named by
`pd_column` (default `pd_current`, forbidden from colliding with reserved
input columns including `is_default`). Optional: `is_default` (booleans or
0/1; absent ⇒ all `False`) and `pd_lifetime`. Validation is fail-fast on a
non-empty `DataFrame`: boolean numeric columns are rejected, `ead ≥ 0`,
`lgd ∈ [0, 1]`, `days_past_due ≥ 0`, PD columns finite and in `[0, 1]` with
no missing values, and **`pd_lifetime + 1e-12 ≥ pd_12m`** (a lifetime PD
cannot be strictly lower than the 12-month PD).

**Staging rules and mandatory Stage 3 default PD (deterministic, top-down).**

| Order | Stage | Condition | Effective PD & Horizon |
|---|---|---|---|
| 1 | **Stage 3** | `days_past_due > 90` **or** `is_default` | **`PD_12m = 1.0`, `PD_lifetime = 1.0`** (mandatory, IFRS 9 §5.5 / Appendix A); applicable horizon = **lifetime** |
| 2 | **Stage 2** | `days_past_due > 30` **or** `pd_current > 2 × pd_initial` | input `pd_12m`, `pd_lifetime`; applicable horizon = **lifetime** |
| 3 | **Stage 1** | everything else | input `pd_12m`, `pd_lifetime`; applicable horizon = **12-month** |

The order matters: an exposure with `days_past_due = 120` and a default flag
is Stage 3, not Stage 2, and its effective PD is forced to `1.0` regardless of
the model-predicted PD column. There is no fitting, no simulation and no
random component: the same input CSV always yields the same stages, the same
per-exposure rows and the same totals. The input DataFrame is never mutated.

**ECL formula.**

    ECL_12m        = PD_12m      × LGD × EAD × d
    ECL_lifetime   = PD_lifetime × LGD × EAD × d
    ECL_applicable = ECL_12m        if Stage == 1
                   = ECL_lifetime   if Stage ∈ {2, 3}

    d = 1                       if eir is None
    d = 1 / (1 + EIR)           if eir is not None   (EIR ≥ 0, finite, non-bool)

    total_ecl_12m      = Σ_exposures ECL_12m        (math.fsum)
    total_ecl_lifetime = Σ_exposures ECL_lifetime   (math.fsum)
    total_ecl_staged   = Σ_exposures ECL_applicable (math.fsum)

The discount factor `d` is a **one-period simplification in v1**: it discounts
the whole horizon with a single factor instead of a multi-period amortised-cost
schedule. `ECLConfig(eir=None)` disables discounting, and `eir < 0` is
rejected (`ValueError`) so `d` never exceeds `1`. In the GUI (`ECLDialog`),
the user enters annual `EIR (%)` in `[0.0, 200.0]` and the dialog performs
the pure presentation conversion `eir = value / 100.0` before calling the
backend. When `pd_lifetime` is absent, `pd_12m` is reused (still overridden
to `1.0` in Stage 3) with an explicit `UserWarning`.

**Outputs.** `ECLRow` per exposure (`exposure_id`, `stage`, `pd_12m`,
`pd_lifetime`, `lgd`, `ead`, `ecl_12m`, `ecl_lifetime`, `ecl_applicable`) and
an `ECLSummary` with `total_ecl_12m`, `total_ecl_lifetime`, `stage_counts`
(Stage 1/2/3 order) and **`total_ecl_staged`** (the combined IFRS 9 staged
provision: Stage 1 at 12 months + Stages 2 and 3 at lifetime). The Session
facade (`Session.calculate_ecl`) returns only the bounded summary: the
per-exposure detail is discarded so the MCP channel does not leak
exposure-level data.

**Governance separation: Prudential Basel PD vs. Accounting IFRS 9 PIT PD.**
A PD produced under TreeGov's `BANKING` mode (§6.3, §6.7) incorporates
Jeffreys smoothing and the prudential BCBS CRE 32.4 floor (`≥ 0.0005`), which
are **prudential conservatism adjustments** for IRB capital. IFRS 9 §5.5.17
requires **unbiased, probability-weighted, point-in-time (PIT)** PDs without
prudential floors or regulatory margins of conservatism. Consequently,
`calculate_ecl` applies **no** Basel floor, and the institution must ensure
that the PD supplied in `pd_column` is properly calibrated as an unbiased PIT
accounting estimate rather than reusing a floored prudential `BANKING` PD
without documented reconciliation.

**Scope limits — what this is not.**

- Not a multi-scenario model: no probability-weighted macroeconomic
  scenarios, no forward-looking overlay.
- Not a multi-period schedule: one-period discount factor `1 / (1 + EIR)` in
  v1, no year-by-year amortisation or prepayment modelling.
- The Stage 2 trigger `pd_current > 2 × pd_initial` is a **documented
  simplification** of the significant-increase-in-credit-risk test, not the
  IFRS 9 text.
- Passing these checks does **not** certify IFRS 9 compliance. Calibration,
  default definition, staging policy and *point-in-time* adequacy remain the
  institution's responsibility.

**Citation:** IFRS 9 *Financial Instruments* (IASB), Section 5.5 —
Impairment, and Appendix A. See `docs/design_decisions.md` §22.1, §22.2 and
§29; `docs/api.md` (`backend_v3.ecl`, `Session.calculate_ecl`);
`docs/security_audit.md` §0 for the sensitivity of the resulting artefacts.

---

## Full bibliographic references

- Biggs, D., de Ville, B. & Suen, E. (1991). *A Method of Choosing Multiway Partitions for Classification and Decision Trees*. Journal of Applied Statistics 18(1), 49-62.
- Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984). *Classification and Regression Trees*. Wadsworth.
- Brier, G.W. (1950). *Verification of forecasts expressed in terms of probability*. Monthly Weather Review 78(1), 1-3.
- Brown, M.B. & Forsythe, A.B. (1974). *Robust Tests for the Equality of Variances*. Journal of the American Statistical Association 69(346), 364-367.
- Chan, T.F., Golub, G.H. & LeVeque, R.J. (1983). *Algorithms for Computing the Sample Variance: Analysis and Recommendations*. The American Statistician 37(3), 242-247.
- Cochran, W.G. (1954). *Some Methods for Strengthening the Common Chi-2 Tests*. Biometrics 10(4), 417-451.
- Davis, J. & Goadrich, M. (2006). *The relationship between Precision-Recall and ROC curves*. Proceedings of the 23rd International Conference on Machine Learning (ICML), 233-240.
- Fagerland, M.W., Hosmer, D.W. & Bofin, A.M. (2012). *Multinomial goodness-of-fit tests for logistic regression models*. Statistics in Medicine, 31(30), 4238-4253.
- Fisher, R.A. (1925). *Statistical Methods for Research Workers*. Oliver & Boyd, Edinburgh.
- Hand, D.J. & Till, R.J. (2001). *A simple generalisation of the area under the ROC curve for multiple class classification problems*. Machine Learning, 45(2), 171-186.
- Hanley, J.A. & McNeil, B.J. (1982). *The meaning and use of the area under a receiver operating characteristic (ROC) curve*. Radiology 143(1), 29-36.
- Heeringa, S.G., West, B.T. & Berglund, P.A. (2010). *Applied Survey Data Analysis*. Chapman & Hall/CRC.
- Hosmer, D.W. & Lemeshow, S. (1980). *A goodness-of-fit test for the multiple logistic regression model*. Communications in Statistics A10, 1043-1069.
- Hosmer, D.W., Lemeshow, S. & Sturdivant, R.X. (2013). *Applied Logistic Regression* (3rd ed.). Wiley.
- Jeffreys, H. (1946). *An invariant form for the prior probability in estimation problems*. Proceedings of the Royal Society of London A 186(1007), 453-461.
- Kass, G.V. (1980). *An Exploratory Technique for Investigating Large Quantities of Categorical Data*. Applied Statistics 29(2), 119-127.
- Kish, L. (1965). *Survey Sampling*. Wiley.
- Kohavi, R. (1995). *A study of cross-validation and bootstrap for accuracy estimation and model selection*. Proceedings of the 14th International Joint Conference on Artificial Intelligence (IJCAI), 1137-1143.
- Levene, H. (1960). *Robust tests for equality of variances*. In *Contributions to Probability and Statistics*, Stanford University Press, 278-292.
- Loh, W.-Y. & Shih, Y.-S. (1997). *Split Selection Methods for Classification Trees*. Statistica Sinica 7(4), 815-840.
- Massey, F.J. (1951). *The Kolmogorov-Smirnov Test for Goodness of Fit*. Journal of the American Statistical Association 46(253), 68-78.
- Pearson, K. (1900). *On the criterion that a given system of deviations from the probable in the case of a correlated system of variables is such that it can be reasonably supposed to have arisen from random sampling*. Philosophical Magazine Ser. 5, 50(302), 157-175.
- Press, W.H., Teukolsky, S.A., Vetterling, W.T. & Flannery, B.P. (2007). *Numerical Recipes: The Art of Scientific Computing* (3rd ed.), §5.6. Cambridge University Press.
- Siddiqi, N. (2006). *Credit Risk Scorecards: Developing and Implementing Intelligent Credit Scoring*. Wiley.

---

## Reference regulatory standards

- **Basel (BCBS CRE 32.4)**: Regulatory PD floors for IRB exposures
  (0.05% for corporate, bank and retail; 0.03% or exempt for
  sovereign).
- **EBA/GL/2017/16**: guidelines on the specification, estimation and validation of PD/LGD parameters in IRB models.
- **IFRS 9**: staging and expected credit loss (ECL) impairment (§5.5 and Appendix A).
- **SR 11-7 / OCC 2011-12**: model risk management (MRM) guidance.
