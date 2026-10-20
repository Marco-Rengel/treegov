import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.session_state import Session

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "uci"

CONFIGS = {
    "german_credit": {
        "csv": "german_credit/german_credit.csv",
        "target": "target",
        "target_class": 1,
        "class_labels": {0: "Good", 1: "Bad"},
        "max_depth": 4,
        "min_child_size": 50,
        "seed": 42,
    },
    "car_evaluation": {
        "csv": "car_evaluation/car_evaluation.csv",
        "target": "target",
        "target_class": 0,
        "class_labels": {0: "unacc", 1: "acc", 2: "good", 3: "vgood"},
        "max_depth": 3,
        "min_child_size": 50,
        "seed": 42,
    },
    "balance_scale": {
        "csv": "balance_scale/balance_scale.csv",
        "target": "target",
        "target_class": 0,
        "class_labels": {0: "L", 1: "B", 2: "R"},
        "max_depth": 3,
        "min_child_size": 20,
        "seed": 42,
    },
    "breast_cancer_wdbc": {
        "csv": "breast_cancer_wdbc/breast_cancer_wdbc.csv",
        "target": "target",
        "target_class": 1,
        "class_labels": {0: "Benign", 1: "Malignant"},
        "max_depth": 4,
        "min_child_size": 20,
        "seed": 42,
    },
    "iris": {
        "csv": "iris/iris.csv",
        "target": "target",
        "target_class": 0,
        "class_labels": {0: "Setosa", 1: "Versicolor", 2: "Virginica"},
        "max_depth": 3,
        "min_child_size": 10,
        "seed": 42,
    },
    "blood_transfusion": {
        "csv": "blood_transfusion/blood_transfusion.csv",
        "target": "target",
        "target_class": 1,
        "class_labels": {0: "Non-donor", 1: "Donor"},
        "max_depth": 4,
        "min_child_size": 20,
        "seed": 42,
    }
}

EXPECTED = {
    "german_credit": {"fingerprint": "85fc3fee3afe2015", "nodes": 9},
    "car_evaluation": {"fingerprint": "5c9c4ac311a2efc5", "nodes": 7},
    "balance_scale": {"fingerprint": "d06048e406f9b220", "nodes": 13},
    "breast_cancer_wdbc": {"fingerprint": "e46011f55ed957bf", "nodes": 3},
    "iris": {"fingerprint": "cbc4051bc41e628a", "nodes": 5},
    "blood_transfusion": {"fingerprint": "4bbeec6ddda3d774", "nodes": 11},
}


def _build_session(cfg, engine="CRT"):
    sess = Session()
    sess.load_dataset(str(FIXTURES / cfg["csv"]))
    cols, _ = sess.describe_dataset()
    predictors = [c for c in cols if c != cfg["target"]]

    sess.fix_spec(
        target=cfg["target"],
        predictors=predictors,
        target_class=cfg["target_class"],
        class_labels=cfg["class_labels"]
    )
    sess.partition(train_frac=0.7, seed=cfg["seed"])
    sess.train(
        engine=engine,
        max_depth=cfg["max_depth"],
        min_child_size=cfg["min_child_size"]
    )
    sess.evaluate_oos()
    return sess


EXPECTED_CHAID = {
    "car_evaluation": {"fingerprint": "2fef573e713c8b5b", "nodes": 14},
    "balance_scale": {"fingerprint": "464bb506b94b8e8b", "nodes": 21},
}

EXPECTED_QUEST = {
    "german_credit": {"fingerprint": "4cb2415a6ce26776", "nodes": 7},
    "car_evaluation": {"fingerprint": "d52401118ea2078b", "nodes": 7},
    "balance_scale": {"fingerprint": "34678ed5eaa34241", "nodes": 13},
    "breast_cancer_wdbc": {"fingerprint": "389f70f0fba1a180", "nodes": 7},
    "iris": {"fingerprint": "32a5ee7f69260fed", "nodes": 5},
    "blood_transfusion": {"fingerprint": "cd6b4399350c44e4", "nodes": 7},
}


def _check_dataset(name, engine="CRT"):
    cfg = CONFIGS[name]
    if engine == "CHAID":
        exp = EXPECTED_CHAID[name]
    elif engine == "QUEST":
        exp = EXPECTED_QUEST[name]
    else:
        exp = EXPECTED[name]

    sess = _build_session(cfg, engine)

    tree = sess.state.tree
    metrics = sess.state.oos_metrics

    assert tree.params_fingerprint == exp["fingerprint"]
    assert len(tree.nodes) == exp["nodes"]
    assert metrics.gini is not None and metrics.gini > 0.3


def test_uci_german_credit():
    _check_dataset("german_credit")


def test_uci_car_evaluation():
    _check_dataset("car_evaluation")


def test_uci_balance_scale():
    _check_dataset("balance_scale")


def test_uci_breast_cancer_wdbc():
    _check_dataset("breast_cancer_wdbc")


def test_uci_iris():
    _check_dataset("iris")


def test_uci_blood_transfusion():
    _check_dataset("blood_transfusion")


def test_uci_car_evaluation_chaid():
    _check_dataset("car_evaluation", "CHAID")


def test_uci_balance_scale_chaid():
    _check_dataset("balance_scale", "CHAID")


def test_uci_german_credit_quest():
    _check_dataset("german_credit", "QUEST")


def test_uci_car_evaluation_quest():
    _check_dataset("car_evaluation", "QUEST")


def test_uci_balance_scale_quest():
    _check_dataset("balance_scale", "QUEST")


def test_uci_breast_cancer_wdbc_quest():
    _check_dataset("breast_cancer_wdbc", "QUEST")


def test_uci_iris_quest():
    _check_dataset("iris", "QUEST")


def test_uci_blood_transfusion_quest():
    _check_dataset("blood_transfusion", "QUEST")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        obj
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests passed")
