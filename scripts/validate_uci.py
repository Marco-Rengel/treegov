import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.session_state import Session

FIXTURES = Path("tests/fixtures/uci")

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

def run():
    print("| Dataset | Fingerprint | Nodes | Leaves | Gini | KS | AUC | Accuracy |")
    print("|---|---|---|---|---|---|---|---|")
    
    for name, cfg in CONFIGS.items():
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
            engine="CRT",
            max_depth=cfg["max_depth"],
            min_child_size=cfg["min_child_size"]
        )
        sess.evaluate_oos()
        
        st = sess.state
        tree = st.tree
        metrics = st.oos_metrics
        mat = sess.get_classification_matrix()
        acc = mat.get("accuracy") if mat else None
        
        fp = tree.params_fingerprint
        nodes = len(tree.nodes)
        leaves = sum(1 for n in tree.nodes if n.is_leaf)
        
        gini = f"{metrics.gini:.4f}" if metrics.gini is not None else "None"
        ks = f"{metrics.ks:.4f}" if metrics.ks is not None else "None"
        auc = f"{metrics.auc:.4f}" if metrics.auc is not None else "None"
        acc_str = f"{acc:.4f}" if acc is not None else "None"
        
        print(f"| {name} | {fp} | {nodes} | {leaves} | {gini} | {ks} | {auc} | {acc_str} |")

if __name__ == "__main__":
    run()
