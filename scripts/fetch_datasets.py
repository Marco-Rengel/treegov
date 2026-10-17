import urllib.request
import hashlib
import csv
from pathlib import Path

ROOT = Path("tests/fixtures/uci")

DATASETS = {
    "german_credit": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/statlog/german/german.data",
        "sha256": "b21f3d81db8071257d5ff1deaeba1fd4303b62712e6fcc9715c7a86202cb5871",
        "sep": " ",
        "has_header": False,
        "cols": ["checking_status", "duration_months", "credit_history", "purpose", "credit_amount", "savings_status", "employment", "installment_rate", "personal_status", "other_parties", "residence_since", "property_magnitude", "age", "other_payment_plans", "housing", "existing_credits", "job", "num_dependents", "own_telephone", "foreign_worker", "target"],
        "target_idx": 20,
        "target_map": {"1": "0", "2": "1"}
    },
    "car_evaluation": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/car/car.data",
        "sha256": "b703a9ac69f11e64ce8c223c0a40de4d2e9d769f7fb20be5f8f2e8a619893d83",
        "sep": ",",
        "has_header": False,
        "cols": ["buying", "maint", "doors", "persons", "lug_boot", "safety", "target"],
        "target_idx": 6,
        "target_map": {"unacc": "0", "acc": "1", "good": "2", "vgood": "3"}
    },
    "balance_scale": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/balance-scale/balance-scale.data",
        "sha256": "5611187ef7345d807aa8ae22615945ade52a190537c0b1434bd44c3e877c5bb4",
        "sep": ",",
        "has_header": False,
        "cols": ["left_weight", "left_distance", "right_weight", "right_distance", "target"],
        "target_idx": 0,
        "target_map": {"L": "0", "B": "1", "R": "2"}
    },
    "breast_cancer_wdbc": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/breast-cancer-wisconsin/wdbc.data",
        "sha256": "d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a",
        "sep": ",",
        "has_header": False,
        "cols": [f"f{i}" for i in range(1, 31)] + ["target"],
        "target_idx": 1,
        "target_map": {"M": "1", "B": "0"},
        "drop_cols": [0]
    },
    "iris": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data",
        "sha256": "6f608b71a7317216319b4d27b4d9bc84e6abd734eda7872b71a458569e2656c0",
        "sep": ",",
        "has_header": False,
        "cols": ["sepal_length", "sepal_width", "petal_length", "petal_width", "target"],
        "target_idx": 4,
        "target_map": {"Iris-setosa": "0", "Iris-versicolor": "1", "Iris-virginica": "2"}
    },
    "blood_transfusion": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/blood-transfusion/transfusion.data",
        "sha256": "96c8e1091b9c037bcaf25a19b24b49d07771cd88689ffd273e056e9e8845ffe7",
        "sep": ",",
        "has_header": True,
        "cols": ["recency_months", "frequency_times", "monetary_cc", "time_months", "target"],
        "target_idx": 4,
        "target_map": {}
    }
}

def download_and_verify(url, expected_sha):
    req = urllib.request.Request(url, headers={"User-Agent": "TreeGov/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != expected_sha:
        raise RuntimeError(f"Hash mismatch for {url}: expected {expected_sha}, got {actual_sha}")
    return data.decode("utf-8")

def process_row(row, ds):
    row = [x.strip() for x in row]
    if not row or all(x == '' for x in row):
        return None
    
    target_val = row[ds["target_idx"]]
    target_val = ds["target_map"].get(target_val, target_val)
    
    features = []
    for i, val in enumerate(row):
        if i == ds["target_idx"]:
            continue
        if i in ds.get("drop_cols", []):
            continue
        features.append(val)
        
    return features + [target_val]

def main():
    for name, ds in DATASETS.items():
        print(f"Fetching {name}...")
        raw_text = download_and_verify(ds["url"], ds["sha256"])
        lines = raw_text.splitlines()
        if ds["has_header"]:
            lines = lines[1:]
            
        out_dir = ROOT / name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{name}.csv"
        
        written_rows = 0
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(ds["cols"])
            for line in lines:
                row = line.split(ds["sep"])
                processed = process_row(row, ds)
                if processed:
                    writer.writerow(processed)
                    written_rows += 1
        
        with open(out_path, "rb") as f:
            out_data = f.read()
        out_sha = hashlib.sha256(out_data).hexdigest()
        sidecar = out_dir / f"{name}.csv.sha256"
        sidecar.write_text(out_sha, encoding="utf-8")
        print(f"  -> {out_path} ({written_rows} rows), sha256: {out_sha}")

if __name__ == "__main__":
    main()
