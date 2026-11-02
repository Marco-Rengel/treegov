"""End-to-end test for the MCP ECL tool (Phase 7)."""

import json
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

mcp = pytest.importorskip("mcp")
from mcp_v3 import server  # noqa: E402


@pytest.fixture
def csv_path(tmp_path: Path) -> Iterator[Path]:
    """Create a temporary training and ECL input dataset."""
    server._session = None
    n_rows = 100
    ages = [20 + (index % 40) for index in range(n_rows)]
    df = pd.DataFrame(
        {
            "exposure_id": [f"E{index:03d}" for index in range(n_rows)],
            "ead": [1000.0 + 10.0 * index for index in range(n_rows)],
            "lgd": [0.45] * n_rows,
            "days_past_due": [[0, 45, 100][index % 3] for index in range(n_rows)],
            "pd_initial": [0.02] * n_rows,
            "pd_current": [0.02 + 0.01 * (index % 5) for index in range(n_rows)],
            "pd_lifetime": [0.10 + 0.05 * (index % 5) for index in range(n_rows)],
            "age": ages,
            "y": [int(age >= 40) for age in ages],
        }
    )
    path = tmp_path / "ecl.csv"
    df.to_csv(path, index=False)
    yield path
    server._session = None


def test_calculate_ecl_tool(csv_path: Path):
    server.load_dataset(str(csv_path))
    server.fix_spec(
        target="y",
        target_class=1,
        class_labels={0: "Good", 1: "Bad"},
        predictors=["age"],
    )
    server.partition()
    state = server.train(engine="CRT", max_depth=2, min_child_size=5)
    assert state["state"] == "TRAINED"

    res = server.calculate_ecl(str(csv_path))

    assert res["total_ecl_12m"] > 0
    assert "stage_counts" in res
    assert "total_ecl_lifetime" in res
    json.dumps(res, allow_nan=False)
