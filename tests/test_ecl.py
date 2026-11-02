"""Tests for the simplified ECL calculation (Phase 7)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from backend_v3.ecl import ECLConfig, calculate_ecl  # noqa: E402


def _mock_ecl_df() -> pd.DataFrame:
    """Build three exposures covering Stages 1, 2 and 3."""
    return pd.DataFrame(
        {
            "exposure_id": ["A", "B", "C"],
            "ead": [1000, 2000, 500],
            "lgd": [0.45, 0.45, 0.45],
            "pd_current": [0.02, 0.05, 0.20],
            "pd_initial": [0.02, 0.02, 0.05],
            "days_past_due": [0, 45, 100],
            "pd_lifetime": [0.10, 0.20, 0.80],
        }
    )


def test_ecl_stage_assignment():
    """Days past due assign A to Stage 1, B to Stage 2 and C to Stage 3."""
    _summary, rows = calculate_ecl(
        _mock_ecl_df(), pd_column="pd_current", config=ECLConfig()
    )

    stages = {row.exposure_id: row.stage for row in rows}
    assert stages == {"A": 1, "B": 2, "C": 3}


def test_ecl_stage_2_by_pd():
    """A current PD above twice the initial PD triggers Stage 2."""
    df = _mock_ecl_df()
    df.loc[df["exposure_id"] == "B", "days_past_due"] = 0

    _summary, rows = calculate_ecl(
        df, pd_column="pd_current", config=ECLConfig()
    )

    stages = {row.exposure_id: row.stage for row in rows}
    assert stages["B"] == 2


def test_ecl_calculation():
    """Row A and the 12-month total match manual arithmetic."""
    summary, rows = calculate_ecl(
        _mock_ecl_df(), pd_column="pd_current", config=ECLConfig()
    )

    row_a = next(row for row in rows if row.exposure_id == "A")
    assert row_a.ecl_12m == pytest.approx(9.0)
    assert row_a.ecl_lifetime == pytest.approx(45.0)
    assert summary.total_ecl_12m == pytest.approx(99.0)


def test_ecl_invalid_data():
    """LGD above one is rejected explicitly."""
    df = _mock_ecl_df()
    df["lgd"] = 1.5

    with pytest.raises(ValueError, match="lgd"):
        calculate_ecl(df, pd_column="pd_current", config=ECLConfig())
