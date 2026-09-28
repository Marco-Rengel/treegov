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

---

## 7. Hamilton-Hare partition (Largest Remainder)

For a dataset with N observations and target training quota N_train = round(N × train_frac):

Per stratum j (j ∈ {0, 1} for a binary target):

1. Ideal quota: Q_j = N_j × (N_train / N).
2. Integer part: n_j = floor(Q_j).
3. Remainder: R = N_train − (n_0 + n_1).
4. Allocation of the R remaining observations: the classes with the largest residual fraction f_j = Q_j − n_j receive +1 unit each.

It guarantees that the event rate in train matches the population exactly.

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

### 8.6. Asymmetric cut optimization (IFRS 9)

Expected loss function:

E[Loss](θ) = C_FN × FN(θ) + C_FP × FP(θ)

where:
- C_FN = LGD × EAD (false-negative cost).
- C_FP = NIM (false-positive cost).

Search for θ* = argmin_θ E[Loss](θ) via grid search.

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
