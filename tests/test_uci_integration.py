import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.session_state import Session
from backend_v3.types import TargetType

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
    "german_credit": {"fingerprint": "446828aabc058614", "nodes": 9},
    "car_evaluation": {"fingerprint": "6cf501a3bbd9a52e", "nodes": 7},
    "balance_scale": {"fingerprint": "a09f3f34dc301b8f", "nodes": 13},
    "breast_cancer_wdbc": {"fingerprint": "dcaa012993a65f8f", "nodes": 3},
    "iris": {"fingerprint": "219eed39e7117a49", "nodes": 5},
    "blood_transfusion": {"fingerprint": "fc203ac81f15cea6", "nodes": 11},
}


def _build_session(name, cfg, engine="CRT"):
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
    if name in ("german_credit", "breast_cancer_wdbc", "blood_transfusion"):
        target_type = TargetType.BINARY
    elif name in ("car_evaluation", "balance_scale", "iris"):
        target_type = TargetType.CATEGORICAL
    else:
        raise ValueError(f"Unknown dataset: {name}")
    sess.train(
        engine=engine,
        max_depth=cfg["max_depth"],
        min_child_size=cfg["min_child_size"],
        target_type=target_type,
    )
    sess.evaluate_oos()
    return sess


EXPECTED_CHAID = {
    "car_evaluation": {"fingerprint": "5338999051a797a1", "nodes": 14},
    "balance_scale": {"fingerprint": "877a6e1e3fa28697", "nodes": 21},
}

EXPECTED_QUEST = {
    "german_credit": {"fingerprint": "2859f6c5a0b6b9bd", "nodes": 7},
    "car_evaluation": {"fingerprint": "73b70052738ce671", "nodes": 7},
    "balance_scale": {"fingerprint": "0ebe693b7eb51653", "nodes": 13},
    "breast_cancer_wdbc": {"fingerprint": "24cb11d933da55c6", "nodes": 7},
    "iris": {"fingerprint": "cafc73dcf547ec12", "nodes": 5},
    "blood_transfusion": {"fingerprint": "eb420400fbbbf0fc", "nodes": 7},
}


def _check_dataset(name, engine="CRT"):
    cfg = CONFIGS[name]
    if engine == "CHAID":
        exp = EXPECTED_CHAID[name]
    elif engine == "QUEST":
        exp = EXPECTED_QUEST[name]
    else:
        exp = EXPECTED[name]

    sess = _build_session(name, cfg, engine)

    tree = sess.state.tree
    metrics = sess.state.oos_metrics

    assert tree.params_fingerprint == exp["fingerprint"]
    assert len(tree.nodes) == exp["nodes"]
    assert metrics.gini is not None and metrics.gini > 0.3
    assert metrics.auc is not None and metrics.auc > 0.65
    assert metrics.ks is not None
    # KS multiclase: mínimo de los pares (decisión D4). Un par no separable
    # por min_child_size (good/vgood en car_evaluation con max_depth=3)
    # puede dar 0.0 aunque el modelo discrimine bien. En K=2 el KS
    # coincide con el binario y sigue siendo exigible.
    if len(tree.class_labels) == 2:
        assert metrics.ks > 0.25, (
            f"{name}/{engine}: KS binario <= 0.25 (ks={metrics.ks})"
        )


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
