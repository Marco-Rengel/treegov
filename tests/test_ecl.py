"""Tests for the simplified ECL calculation (Phase 7 / Block 2C).

Normative and operational reference for manual arithmetic assertions:
  - IFRS 9 Financial Instruments (IASB), §5.5 (§5.5.3 lifetime ECL, §5.5.5
    12-month ECL, §5.5.9 SICR, §5.5.11 30-day rebuttable presumption,
    §5.5.17 unbiased PIT measurement & EIR discounting) and Appendix A
    (credit-impaired / Stage 3 default forcing PD = 1.0).
  - TreeGov v1 documented operational simplifications (not normative IFRS 9
    text): Stage 2 trigger ``pd_current > 2 * pd_initial`` and single-period
    discount factor ``1 / (1 + EIR)``.
"""

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
    """Stage 3 forces PD=1.0 (IFRS 9 Appendix A) and totals match IFRS 9 §5.5 staged arithmetic.

    Manual verification (no discounting, EIR=None):
      - A (Stage 1, §5.5.5): 0.02 * 0.45 * 1000 = 9.0 (12m, applicable);
        0.10 * 0.45 * 1000 = 45.0 (lifetime).
      - B (Stage 2, §5.5.3 / §5.5.11): 0.05 * 0.45 * 2000 = 45.0 (12m);
        0.20 * 0.45 * 2000 = 180.0 (lifetime, applicable).
      - C (Stage 3, Appendix A -> PD=1.0): 1.0 * 0.45 * 500 = 225.0 (both).
      - Totals: 12m = 279.0, lifetime = 450.0, staged = 9 + 180 + 225 = 414.0.
    """
    summary, rows = calculate_ecl(
        _mock_ecl_df(), pd_column="pd_current", config=ECLConfig()
    )

    by_id = {row.exposure_id: row for row in rows}
    row_a = by_id["A"]
    row_b = by_id["B"]
    row_c = by_id["C"]

    assert row_a.ecl_12m == pytest.approx(9.0)
    assert row_a.ecl_lifetime == pytest.approx(45.0)
    assert row_a.ecl_applicable == pytest.approx(9.0)

    assert row_b.ecl_12m == pytest.approx(45.0)
    assert row_b.ecl_lifetime == pytest.approx(180.0)
    assert row_b.ecl_applicable == pytest.approx(180.0)

    assert row_c.stage == 3
    assert row_c.pd_12m == pytest.approx(1.0)
    assert row_c.pd_lifetime == pytest.approx(1.0)
    assert row_c.ecl_12m == pytest.approx(225.0)
    assert row_c.ecl_lifetime == pytest.approx(225.0)
    assert row_c.ecl_applicable == pytest.approx(225.0)

    assert summary.total_ecl_12m == pytest.approx(279.0)
    assert summary.total_ecl_lifetime == pytest.approx(450.0)
    assert summary.total_ecl_staged == pytest.approx(414.0)
    assert summary.stage_counts == (1, 1, 1)


def test_ecl_discounting_eir():
    """ECLConfig(eir=0.12) discounts 12m, lifetime and staged totals by 1/1.12.

    TreeGov v1 single-period discount simplification 1 / (1 + EIR) anchored
    conceptually to IFRS 9 §5.5.17.
    """
    summary, rows = calculate_ecl(
        _mock_ecl_df(), pd_column="pd_current", config=ECLConfig(eir=0.12)
    )
    factor = 1.0 / 1.12

    assert summary.total_ecl_12m == pytest.approx(279.0 * factor)
    assert summary.total_ecl_lifetime == pytest.approx(450.0 * factor)
    assert summary.total_ecl_staged == pytest.approx(414.0 * factor)

    by_id = {row.exposure_id: row for row in rows}
    assert by_id["A"].ecl_applicable == pytest.approx(9.0 * factor)
    assert by_id["B"].ecl_applicable == pytest.approx(180.0 * factor)
    assert by_id["C"].ecl_applicable == pytest.approx(225.0 * factor)


@pytest.mark.parametrize(
    "bad_eir",
    [-0.01, -0.5, -1.0, True, False, float("nan"), float("inf"), float("-inf")],
)
def test_ecl_config_rejects_invalid_eir(bad_eir):
    """Negative, boolean and non-finite EIR values are rejected."""
    with pytest.raises(ValueError, match="eir"):
        ECLConfig(eir=bad_eir)


def test_ecl_rejects_pd_lifetime_below_pd_12m():
    """An exposure with pd_lifetime < pd_12m is rejected."""
    df = _mock_ecl_df()
    df.loc[df["exposure_id"] == "A", "pd_lifetime"] = 0.01

    with pytest.raises(ValueError, match="pd_lifetime"):
        calculate_ecl(df, pd_column="pd_current", config=ECLConfig())


def test_ecl_invalid_data():
    """LGD above one is rejected explicitly."""
    df = _mock_ecl_df()
    df["lgd"] = 1.5

    with pytest.raises(ValueError, match="lgd"):
        calculate_ecl(df, pd_column="pd_current", config=ECLConfig())


@pytest.mark.parametrize("col", ["ead", "lgd", "pd_current"])
def test_ecl_rejects_boolean_columns(col):
    """Boolean columns (native dtype or object dtype) are rejected."""
    df = _mock_ecl_df()
    df[col] = [True, False, True]
    with pytest.raises(ValueError, match="booleanos"):
        calculate_ecl(df, pd_column="pd_current", config=ECLConfig())

    df_obj = _mock_ecl_df()
    df_obj[col] = pd.Series([True, 0.2, 0.3], dtype=object)
    with pytest.raises(ValueError, match="booleanos"):
        calculate_ecl(df_obj, pd_column="pd_current", config=ECLConfig())


def test_ecl_rejects_empty_df_and_invalid_pd_column():
    """Empty DataFrames, blank pd_column and reserved column collisions fail."""
    df = _mock_ecl_df()

    with pytest.raises(ValueError, match="vacío"):
        calculate_ecl(df.iloc[0:0], pd_column="pd_current", config=ECLConfig())

    with pytest.raises(ValueError, match="pd_column"):
        calculate_ecl(df, pd_column="", config=ECLConfig())

    with pytest.raises(ValueError, match="pd_column"):
        calculate_ecl(df, pd_column="   ", config=ECLConfig())

    for reserved in ("lgd", "pd_initial", "ead", "is_default"):
        with pytest.raises(ValueError, match="pd_column"):
            calculate_ecl(df, pd_column=reserved, config=ECLConfig())


def test_ecl_stage_3_by_is_default_forces_pd_one():
    """is_default=True forces Stage 3 and PD=1.0 even when days_past_due=0."""
    df = _mock_ecl_df()
    df["days_past_due"] = [0, 0, 0]
    df["is_default"] = [False, False, True]

    summary, rows = calculate_ecl(
        df, pd_column="pd_current", config=ECLConfig()
    )
    row_c = next(row for row in rows if row.exposure_id == "C")
    assert row_c.stage == 3
    assert row_c.pd_12m == pytest.approx(1.0)
    assert row_c.pd_lifetime == pytest.approx(1.0)
    assert row_c.ecl_12m == pytest.approx(225.0)
    assert row_c.ecl_lifetime == pytest.approx(225.0)
    assert row_c.ecl_applicable == pytest.approx(225.0)
    assert summary.stage_counts == (1, 1, 1)
