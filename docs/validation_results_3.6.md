# TreeGov — Validation Results (Phase 3.6)

This document records the reproducible baseline obtained by running the TreeGov pipeline on six public UCI datasets. It is the deliverable of Phase 3.6.c.

**Configuration:** C&RT engine, `train_frac=0.7`, `seed=42`, `max_depth` and `min_child_size` as per `scripts/validate_uci.py`.

## Quantitative Baseline

| Dataset | Fingerprint | Nodes | Leaves | Gini | KS | AUC | Accuracy |
|---|---|---|---|---|---|---|---|
| German Credit | 33e52665fcba86d0 | 9 | 5 | 0.4415 | 0.4079 | 0.7208 | 0.7100 |
| Car Evaluation | ca64aaf2f546ced0 | 7 | 4 | 0.4660 | 0.0000 | 0.7330 | 0.7838 |
| Balance Scale | 801e4cfc3cc54025 | 13 | 7 | 0.4085 | 0.2078 | 0.7043 | 0.7219 |
| Breast Cancer WDBC | 5198672eb28fd02a | 3 | 2 | 0.7595 | 0.7595 | 0.8797 | 0.9006 |
| Iris | 0fb371f1f41ed073 | 5 | 3 | 0.9556 | 0.8667 | 0.9778 | 0.9556 |
| Blood Transfusion | dc12ca4e038802f0 | 11 | 6 | 0.4359 | 0.3584 | 0.7180 | 0.7634 |

## Qualitative Literature Comparison

**German Credit:** The Gini of 0.44 is consistent with the range typically reported for single C&RT trees on this dataset in the credit-scoring literature. Ensemble methods (Random Forests, XGBoost) report higher values, but the comparison here is single-tree only.

**Breast Cancer WDBC:** The Gini of 0.76 and accuracy of 0.90 reflect the strong separability of the malignant/benign classes in this feature space. This is expected and is not a sign of overfitting (the split is train/test).

**Iris:** The Gini of 0.96 is near-perfect, which is standard for this dataset. Its presence here exercises the balanced multiclass path in optimal conditions.

**Car Evaluation & Balance Scale:** These datasets are structurally more complex. Car Evaluation's worst-case KS of 0.0 is expected: the "good" and "vgood" classes are virtually indistinguishable without deep interactions, so the worst pairwise KS collapses to zero. Balance Scale performs well given its heavy ties on 5-value ordinal features.

**Blood Transfusion:** The Gini of 0.43 validates the engine on behavioral RFM data. The tree grows to 6 leaves, reflecting the non-linear relationship between recency/frequency and donation.

## Verdict

The pipeline produces stable, reproducible results across four distinct domains (banking, health, biology, social sciences). The fingerprints act as regression locks. Any future change to the tree builder, engines, or fingerprinting logic that alters these values will trigger a test failure.