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

**Citation:** Pearson (1900); Heeringa, West & Berglund (2010), §5.4
(weighted tables under complex survey designs).

> See `docs/design_decisions.md` §13.2 for the full decision rationale.

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

---

## 3. QUEST (Quick, Unbiased, Efficient Statistical Tree)

Binary engine with unbiased variable selection and univariate QDA split.

### 3.1. Stage 1 — Variable selection

For each predictor j:

- Continuous/ordinal: pⱼ = p-value of the ANOVA F-test between classes.
- Nominal: pⱼ = p-value of Pearson's χ².

Bonferroni threshold: α / (2J), where J = number of predictors.

If no test beats the threshold, Brown-Forsythe (Levene with median) is run on the continuous/ordinal variables to detect discrimination by variance.

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

**Configuration.** Exposed as `nominal_high_card: str = "rate"`
(canonical: `"dummies_lda"`) in Phase 3.0.g.

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

### 3.7bis Weighted QUEST — QDA split and weighted variance

Weighting affects both QUEST stages.

**Stage 1 (variable selection).** Weighted F over the groups defined by the
target class: weighted means, effective sizes `W_i = Σ weights in group`.
Weighted χ² for nominal predictors, same scheme as §1.9bis.

**Stage 2 (QDA cut).**

    Weighted class means:      m_k = Σ_i w_i x_i / W_k
    Weighted variances:        v_k = Σ_i w_i (x_i − m_k)² / (W_k − 1)
    Weighted empirical priors: π_k = W_k / W
    Weighted midpoint (fallback when no real root lies between the means):
                               x̄ = (W_0 m_0 + W_1 m_1) / (W_0 + W_1)

**Divisor convention (W − 1).** The divisor W − 1 (instead of W) is the
natural generalization of the classic n − 1 when weights act as
frequencies. It matches SPSS `WEIGHT BY`, R `survey` with the sample
divisor, and SAS survey procedures.

**Non-intuitive consequence.** With divisor W − 1, the weighted variance
is **not** scale-invariant: multiplying the weights by k turns the
denominator from W − 1 into kW − 1, which is not k·(W − 1). The QUEST QDA
threshold therefore depends on the scale chosen by the analyst. The
alternative with divisor W (population variance) would be scale-invariant
but would systematically underestimate. W − 1 is kept for consistency with
standard practice.

**Citation:** Loh & Shih (1997); Heeringa, West & Berglund (2010), §5.3
(weighted variance in complex surveys).

> See `docs/design_decisions.md` §13.4 for the full decision rationale.

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
- branches: category groups per branch (categorical only).
- impurity_gain: impurity gain (C&RT only).

### 4.2. Validated invariants

In the constructor (__post_init__) the following is verified:
- method ∈ {"CHAID", "CHAID_EXHAUSTIVE", "CRT", "QUEST"}.
- method ↔ statistic_name ↔ required-field coherence.
- Exactly one of threshold / branches is defined.
- branches forms a real partition (non-empty groups, disjoint categories).
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

No exposure may have a PD below 0.03% (3 bps) as per Basel (BCBS CRE 20.39):

PD_final(t) = max(PD_floor, PD_Jeffreys(t))

**Citation**: Basel (BCBS CRE 20.39), EBA/GL/2017/16, IFRS 9.

### 6.4. Governance modes

TreeGov supports two modes (`backend_v3.types.GovernanceMode`):

- **Banking (default):** Jeffreys estimator + PD Floor (BCBS CRE 20.39).
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
- The regulatory floor of 3 bps (BCBS CRE 20.39) does not apply.

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
`pd_floor / sum(pd_temp)`, not exactly `pd_floor`. For K = 2 it reduces
to the standard binary floor: the class of interest receives
`max(pd_floor, pd_jeffreys[0])` and the other class one minus that
value (§6.3).

**Citation:** Jeffreys, H. (1946). An invariant form for the prior
probability in estimation problems. *Proceedings of the Royal Society
of London A*, 186(1007), 453-461.

**Cross-reference:** `docs/3.1_design_multiclass.md` §3.2 and §3.3 for
the phase design; `docs/design_decisions.md` §5.2 for the tuple-fields
decision.

---

## 7. Hamilton-Hare partition (Largest Remainder)

For a dataset with N observations and target training quota N_train = round(N × train_frac):

Per stratum j (j ∈ {0, 1} for a binary target):

1. Ideal quota: Q_j = N_j × (N_train / N).
2. Integer part: n_j = floor(Q_j).
3. Remainder: R = N_train − (n_0 + n_1).
4. Allocation of the R remaining observations: the classes with the largest residual fraction f_j = Q_j − n_j receive +1 unit each.

It guarantees that the event rate in train matches the population exactly.

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

### 8.2. Kolmogorov-Smirnov

KS = max_s |F_bad(s) − F_good(s)|

Maximum vertical distance between the cumulative distribution functions of events and non-events.

### 8.3. Hosmer-Lemeshow

H = Σ_g (O_g − N_g π̄_g)² / [N_g π̄_g (1 − π̄_g)]

Under H₀: H ~ χ²(G − 2), where G is the number of groups (typically 10 deciles).

If p > 0.05, H₀ is not rejected (calibrated model).

### 8.4. Brier Score and BSS

BS = (1/N) Σᵢ (yᵢ − p̂ᵢ)²
BSS = 1 − BS / BS_ref

where BS_ref = ȳ(1 − ȳ) is the Brier Score of the null model.

### 8.5. PSI, CSI and Gini Drop (Phase 1.3 monitoring, `backend_v3/stability.py`)

**Population Stability Index (PSI)** over the tree-leaf distribution and
**Characteristic Stability Index (CSI)** per covariate, always against the
**training partition** (the development population, by definition).

```
PSI = Σ_k (P_actual,k − P_expected,k) · ln(P_actual,k / P_expected,k)
    = KL(actual || expected) + KL(expected || actual)    (symmetric KL)
```

TreeGov policy:
- Clip ε = 1e-4 per bin **before the log and without renormalization**: this
  preserves the signal of empty OOT bins; the scale error is negligible
  against the 0.10 / 0.25 thresholds when bins are non-empty.
- Leaf PSI: bins are the leaves. OOT rows that cannot be routed (unseen
  categories/values) form the extra bin `<UNSEEN>` with P_expected = ε.
- CSI: continuous variables are binned into the **deciles learned on train
  only** (first and last bins open: −inf / +inf absorb out-of-range OOT
  values); nominal variables use the train categories, and unseen OOT
  categories are grouped into `<OTHER>` with P_expected = ε.

Regulatory traffic lights (Basel / EBA):
- PSI/CSI < 0.10 → STABLE.
- 0.10 ≤ PSI/CSI < 0.25 → MODERATE.
- PSI/CSI ≥ 0.25 → UNSTABLE.

**Gini Drop (relative degradation of discriminative power):**

```
drop_X = (Gini_train − Gini_X) / Gini_train      (X in {OOS, OOT})
alert: drop > 0.40 → CRITICAL;  drop > 0.20 → WARNING;  else NONE.
NaN or undefined drop → UNDETERMINED.
If Gini_train == 0 → drop = None (undefined; WARNING in the log).
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

### 8.6. Asymmetric cut optimization (IFRS 9)

Expected loss function:

E[Loss](θ) = C_FN × FN(θ) + C_FP × FP(θ)

where:
- C_FN = LGD × EAD (false-negative cost).
- C_FP = NIM (false-positive cost).

Search for θ* = argmin_θ E[Loss](θ) via grid search.

### 8.7 PSI with clip ε=1e-4 and no renormalization

The Population Stability Index (see §8.5) uses a natural logarithm. When
a bin's probability is zero (either in the expected or the actual
distribution), the log is undefined. TreeGov clips each probability to
`ε = 1e-4` **without renormalizing** the resulting vector.

**Formula.**

    p_k ← max(p_k, 1e-4)   for every bin k
    PSI = Σ_k (p_act,k − p_exp,k) · ln(p_act,k / p_exp,k)
    (no renormalization after clipping)

**Rationale.** If a bin present in train vanishes in OOT (or vice
versa), the correct signal is "this bin's probability dropped to ~0",
which is genuine drift. Renormalizing the probabilities after clipping
would dilute this signal — the very thing PSI is designed to detect.
The scale error from not renormalizing is negligible compared to the
0.10 / 0.25 thresholds when bins are non-empty.

**Configuration.** Exposed as `psi_renormalize: bool = False`
(canonical: `True`) in Phase 3.0.g.

**Citation:** Siddiqi, N. (2006). *Credit Risk Scorecards*. Wiley.

> See `docs/design_decisions.md` §7.4 for the full decision rationale.

### 8.8 CSI: deciles learned on train, with open extreme bins

The Characteristic Stability Index (CSI) is PSI computed per covariate.
For continuous covariates, the binning must be defined; TreeGov uses
**deciles learned on the training partition only**, with the first and
last bins open:

    bin_0   = (−inf,  q_10]
    bin_1   = (q_10, q_20]
    ...
    bin_9   = (q_90, +inf)

where `q_10, …, q_90` are the deciles of the covariate in train.

**Formula.**

    Bins learned on X_train (deciles of the train distribution).
    Bins applied unchanged to X_actual (typically the OOT cohort).
    Out-of-range values fall into the open extreme bins.

**Rationale.**
- **Learned on train:** anti-leakage rule (see §5). The bins must not
  depend on OOT data.
- **Open extreme bins:** an OOT value outside the train range is
  genuine drift. It must contribute to the CSI, not be silently
  dropped. Open bins capture this.

For nominal covariates, the bins are the categories observed in train;
unseen OOT categories are grouped into `<OTHER>` with `p_expected = ε`.

**Citation:** Siddiqi, N. (2006). *Credit Risk Scorecards*. Wiley.

> See `docs/design_decisions.md` §7.5 for the full decision rationale.

### 8.9 Hosmer-Lemeshow: `π_g` clipped to `[1e-15, 1−1e-15]`

The Hosmer-Lemeshow statistic (see §8.3) has the term:

    H = Σ_g (O_g − N_g π_g)² / [N_g π_g (1 − π_g)]

If `π_g = 0` or `π_g = 1` for some group, the denominator is zero. In
practice, `π_g` can hit exactly 0 or 1 when a leaf predicts a constant
PD across the group.

**Formula (with clip).**

    π_g ← max(π_g, 1e-15)
    π_g ← min(π_g, 1 − 1e-15)

**Rationale.** A model that predicts `π = 0` or `π = 1` for a group is
itself suspect; clipping keeps the statistic computable **without
discarding the group**. `1e-15` is above floating-point epsilon but
below any analytically meaningful probability.

**Consequences.** The HL statistic is always finite, and no group is
silently dropped. Documented in `validation.py` as constant `_HL_EPS`.

> See `docs/design_decisions.md` §7.2 for the full decision rationale.

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

---

## Full bibliographic references

- Biggs, D., de Ville, B. & Suen, E. (1991). A Method of Choosing Multiway Partitions for Classification and Decision Trees. Journal of Applied Statistics, 18(1), 49-62.
- Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984). Classification and Regression Trees. Wadsworth.
- Cochran, W.G. (1954). Some Methods for Strengthening the Common Chi-2 Tests. Biometrics, 10(4), 417-451.
- Fisher, R.A. (1925). Statistical Methods for Research Workers. Oliver & Boyd.
- Kass, G.V. (1980). An Exploratory Technique for Investigating Large Quantities of Categorical Data. Applied Statistics, 29(2), 119-127.
- Loh, W.-Y. & Shih, Y.-S. (1997). Split Selection Methods for Classification Trees. Statistica Sinica, 7(4), 815-840.
- Pearson, K. (1900). On the criterion that a given system of deviations from the probable in the case of a correlated system of variables is such that it can be reasonably supposed to have arisen from random sampling. Philosophical Magazine, Ser. 5, 50(302), 157-175.
- Siddiqi, N. (2006). Credit Risk Scorecards: Developing and Implementing Intelligent Credit Scoring. Wiley.

---

## Reference regulatory standards

- **Basel (BCBS CRE 20.39)**: Regulatory PD Floors.
- **EBA/GL/2017/16**: guidelines on the specification, estimation and validation of PD/LGD parameters in IRB models.
- **IFRS 9**: staging, ECL and threshold optimization.
- **SR 11-7 / OCC 2011-12**: model risk management (MRM) guidance.
