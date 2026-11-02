"""Tests for Phase 6.0.a batch scoring through the public Session facade."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from backend_v3.crt_engine import CrtEngine  # noqa: F401,E402
from backend_v3.session_state import Session  # noqa: E402
from backend_v3.tree_builder import TreeBuilder  # noqa: F401,E402
from backend_v3.types import PredictorType, TargetType  # noqa: E402
from backend_v3.validation import predict_leaf_assignment  # noqa: E402


TREEGOV_COLUMNS = [
    "treegov_row_id",
    "treegov_model_fingerprint",
    "treegov_leaf_id",
    "treegov_pd",
    "treegov_pd_vector",
    "treegov_rule_path",
    "treegov_route_status",
    "treegov_imputed_columns",
]


def _setup_session(tmp_path: Path) -> tuple[Session, Path]:
    """Build a deterministic trained session and its 100-row source CSV."""
    rng = np.random.default_rng(42)
    edad = rng.integers(20, 61, size=100)
    seg = rng.choice(["A", "B", "C"], size=100, p=[0.2, 0.2, 0.6])
    # The union keeps both predictors informative: within seg != C, the
    # target is exactly 1_{edad >= 40}. Thus unseen seg values reach a real
    # categorical split instead of being ignored by an age-only tree.
    target = ((edad >= 40) | (seg == "C")).astype(int)
    csv_path = tmp_path / "train.csv"
    pd.DataFrame({"edad": edad, "seg": seg, "target": target}).to_csv(
        csv_path, index=False
    )

    s = Session()
    s.load_dataset(str(csv_path))
    s.fix_spec(
        target="target",
        spec={
            "edad": PredictorType.CONTINUOUS,
            "seg": PredictorType.NOMINAL,
        },
        target_class=1,
        class_labels={0: "Non-event", 1: "Event"},
    )
    s.partition(train_frac=0.7, seed=42)
    s.train(
        "CRT",
        target_type=TargetType.BINARY,
        max_depth=3,
        min_child_size=5,
    )
    return s, csv_path


def test_score_batch_success():
    """La salida conserva las columnas originales y puntúa las 100 filas."""
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        s, csv_path = _setup_session(tmp_path)
        output_path = tmp_path / "scored.csv"

        summary = s.score_batch(str(csv_path), str(output_path))
        out = pd.read_csv(output_path)

        assert list(out.columns) == ["edad", "seg", "target"] + TREEGOV_COLUMNS
        assert len(out) == 100
        assert summary["total_rows"] == 100
        assert summary["scored_rows"] == 100
        assert summary["excluded_rows"] == 0
        np.testing.assert_array_equal(
            out["treegov_row_id"].to_numpy(), np.arange(100)
        )
        assert out["treegov_pd"].notna().all()
        assert out["treegov_pd"].between(0.0, 1.0).all()
        assert set(out["treegov_route_status"]) == {"SCORED"}


def test_score_batch_unseen_policy():
    """Una categoría nueva se excluye o usa el fallback de forma explícita."""
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        s, _ = _setup_session(tmp_path)
        scoring_path = tmp_path / "unseen.csv"
        scoring_df = pd.DataFrame({"edad": [30], "seg": ["Z"], "target": [0]})
        scoring_df.to_csv(scoring_path, index=False)

        exclude_path = tmp_path / "excluded.csv"
        s.score_batch(
            str(scoring_path), str(exclude_path), unseen_policy="exclude"
        )
        excluded = pd.read_csv(exclude_path).iloc[0]
        assert excluded["treegov_route_status"] == "EXCLUDED_UNSEEN"
        assert pd.isna(excluded["treegov_pd"])

        majority_path = tmp_path / "majority.csv"
        s.score_batch(
            str(scoring_path), str(majority_path), unseen_policy="majority"
        )
        majority = pd.read_csv(majority_path).iloc[0]
        assert majority["treegov_route_status"] == "MAJORITY_FALLBACK"
        assert s.state.tree is not None
        expected_leaf_id = int(
            predict_leaf_assignment(
                s.state.tree, scoring_df, unseen_policy="majority"
            )[0]
        )
        expected_pd = s.state.tree.nodes[expected_leaf_id].pd_final[0]
        assert majority["treegov_leaf_id"] == expected_leaf_id
        assert majority["treegov_pd"] == pytest.approx(expected_pd)


def test_score_batch_missing_columns():
    """Un CSV sin un predictor requerido falla de forma explícita."""
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        s, _ = _setup_session(tmp_path)
        scoring_path = tmp_path / "missing.csv"
        pd.DataFrame({"edad": [35], "target": [0]}).to_csv(
            scoring_path, index=False
        )

        with pytest.raises(ValueError, match="columnas predictoras ausentes"):
            s.score_batch(str(scoring_path), str(tmp_path / "missing_out.csv"))


def test_score_batch_atomicity():
    """Un fallo no publica salida final ni deja temporales de scoring."""
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        s, _ = _setup_session(tmp_path)
        scoring_path = tmp_path / "invalid.csv"
        output_path = tmp_path / "atomic.csv"
        pd.DataFrame({"edad": [35], "target": [0]}).to_csv(
            scoring_path, index=False
        )

        with pytest.raises(ValueError):
            s.score_batch(str(scoring_path), str(output_path))

        assert not output_path.exists()
        assert not list(tmp_path.glob("*.tmp"))


def test_score_batch_rules():
    """Cada fila puntuada incluye una regla raíz-hoja legible y no vacía."""
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        s, csv_path = _setup_session(tmp_path)
        output_path = tmp_path / "rules.csv"

        s.score_batch(str(csv_path), str(output_path), include_rules=True)
        out = pd.read_csv(output_path)
        rules = out["treegov_rule_path"]

        assert rules.notna().all()
        assert rules.str.strip().ne("").all()
        assert rules.str.contains("Hoja ", regex=False).all()
        assert rules.str.contains("edad", regex=False).any()
