"""End-to-end tests for the Phase 6 MCP scoring tools (hardened in Block 2C)."""

import json

import numpy as np
import pandas as pd
import pytest

mcp = pytest.importorskip("mcp")
from mcp_v3 import server  # noqa: E402


@pytest.fixture
def csv_path(tmp_path, monkeypatch):
    """Create a 200-row mixed-predictor CSV inside TREEGOV_MCP_ROOT."""
    monkeypatch.setenv("TREEGOV_MCP_ROOT", str(tmp_path))
    server._session = None
    rng = np.random.default_rng(42)
    edad = rng.integers(20, 61, size=200)
    seg = rng.choice(["A", "B", "C"], size=200, p=[0.2, 0.2, 0.6])
    target = ((edad >= 40) | (seg == "C")).astype(int)
    path = tmp_path / "evaluation.csv"
    pd.DataFrame({"edad": edad, "seg": seg, "target": target}).to_csv(
        path, index=False
    )
    yield path
    server._session = None


def _train_model(csv_path):
    """Drive the MCP session from a local CSV to a trained CRT."""
    server.load_dataset(str(csv_path))
    server.fix_spec(
        target="target",
        target_class=1,
        class_labels={0: "Non-event", 1: "Event"},
        predictors=["edad", "seg"],
    )
    server.partition()
    server.train(engine="CRT")


def test_score_batch_tool(csv_path, tmp_path):
    """The batch tool writes all predictions and returns a bounded summary."""
    _train_model(csv_path)
    output_path = tmp_path / "out.csv"

    res = server.score_batch(str(csv_path), str(output_path))

    assert res["total_rows"] == 200
    assert res["scored_rows"] == 200
    assert output_path.exists()
    assert "treegov_pd" in pd.read_csv(output_path).columns
    json.dumps(res, allow_nan=False)


def test_score_batch_rejects_same_path_and_overwrite(csv_path, tmp_path):
    """score_batch blocks input==output and overwriting an existing CSV."""
    _train_model(csv_path)

    with pytest.raises(ValueError, match="output_path no puede ser igual a csv_path"):
        server.score_batch(str(csv_path), str(csv_path))

    existing_out = tmp_path / "existing.csv"
    existing_out.write_text("sentinel\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="sobrescritura bloqueada"):
        server.score_batch(str(csv_path), str(existing_out))
    assert existing_out.read_text(encoding="utf-8") == "sentinel\n1\n"


def test_compare_champion_challenger_tool(csv_path):
    """The comparison tool returns JSON-native metrics for a CHAID challenger."""
    _train_model(csv_path)

    res = server.compare_champion_challenger(
        str(csv_path), challenger_engine="CHAID"
    )

    assert res["champion_fingerprint"] != res["challenger_fingerprint"]
    assert res["n_common_routed"] > 0
    json.dumps(res, allow_nan=False)
