"""Tests for Phase 6.0.b Champion-Challenger comparison via Session."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from backend_v3.session_state import Session  # noqa: E402
from backend_v3.types import PredictorType  # noqa: E402


def _setup_session(tmp_path: Path) -> tuple[Session, Path]:
    """Train a deterministic CRT and return it with its evaluation CSV."""
    rng = np.random.default_rng(42)
    edad = rng.integers(20, 61, size=200)
    seg = rng.choice(["A", "B", "C"], size=200, p=[0.2, 0.2, 0.6])
    # Both predictors remain informative, so a new seg category reaches a
    # real categorical branch instead of being ignored by an age-only tree.
    target = ((edad >= 40) | (seg == "C")).astype(int)
    csv_path = tmp_path / "evaluation.csv"
    pd.DataFrame({"edad": edad, "seg": seg, "target": target}).to_csv(
        csv_path, index=False
    )

    session = Session()
    session.load_dataset(str(csv_path))
    session.fix_spec(
        target="target",
        spec={
            "edad": PredictorType.CONTINUOUS,
            "seg": PredictorType.NOMINAL,
        },
        target_class=1,
        class_labels={0: "Non-event", 1: "Event"},
    )
    session.partition(train_frac=0.7, seed=42)
    # max_depth=4 is the builder default used when the Session challenger
    # clones _last_train_params. Therefore the default challenger is an exact
    # deterministic rebuild of the champion.
    session.train("CRT", max_depth=4, min_child_size=5)
    return session, csv_path


def test_compare_same_model_delta_zero():
    """Rebuilding the same model yields identical metrics and zero deltas."""
    with tempfile.TemporaryDirectory() as td:
        session, csv_path = _setup_session(Path(td))

        result = session.compare_champion_challenger(str(csv_path))

        assert result["n_common_routed"] == 200
        assert result["champion_fingerprint"] == result["challenger_fingerprint"]
        assert len(result["metrics"]) == 6
        for _, champion, challenger, delta in result["metrics"]:
            assert champion == challenger
            assert delta == 0.0


def test_compare_different_engines():
    """A CHAID challenger has its own fingerprint and a scored cohort."""
    with tempfile.TemporaryDirectory() as td:
        session, csv_path = _setup_session(Path(td))

        result = session.compare_champion_challenger(
            str(csv_path), challenger_engine="CHAID"
        )

        assert result["champion_fingerprint"] != result["challenger_fingerprint"]
        assert result["n_common_routed"] > 0


def test_compare_common_population():
    """Metrics exclude rows that either model cannot route."""
    with tempfile.TemporaryDirectory() as td:
        session, csv_path = _setup_session(Path(td))
        evaluation = pd.read_csv(csv_path)
        # Age 30 also reaches the categorical branch if the CRT puts its age
        # split first; with a categorical root, the unseen value fails sooner.
        evaluation.loc[0, "edad"] = 30
        evaluation.loc[0, "seg"] = "Z"
        evaluation.to_csv(csv_path, index=False)

        result = session.compare_champion_challenger(
            str(csv_path), unseen_policy="exclude"
        )

        assert result["n_common_routed"] < 200
        assert result["champion_coverage"] < 1.0
        assert result["challenger_coverage"] < 1.0


def test_compare_immutability():
    """Training and comparing a challenger never replaces the champion."""
    with tempfile.TemporaryDirectory() as td:
        session, csv_path = _setup_session(Path(td))
        fp_before = session.state.tree.params_fingerprint

        session.compare_champion_challenger(
            str(csv_path), challenger_params={"max_depth": 1}
        )

        assert session.state.tree.params_fingerprint == fp_before


def test_compare_incompatible_targets():
    """An evaluation target outside the trained class domain is rejected."""
    with tempfile.TemporaryDirectory() as td:
        session, csv_path = _setup_session(Path(td))
        evaluation = pd.read_csv(csv_path)
        evaluation["target"] = np.where(evaluation["target"] == 0, 1, 2)
        evaluation.to_csv(csv_path, index=False)

        with pytest.raises(ValueError, match="clases del target no coinciden"):
            session.compare_champion_challenger(str(csv_path))
