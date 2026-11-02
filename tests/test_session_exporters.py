"""Tests for the Session.export_to_* wrappers (Phase 4.0.c).

These tests exercise the clean-room bridge between the frontend
(which calls Session.export_to_sql/python/markdown) and the exporter
module (which returns the raw text). They verify the three invariants
required for the GUI to enable the File > Export actions:

* Without a trained model → return None (never raise).
* After ``load_dataset → fix_spec → partition → train`` → return a
  non-empty string.
* The returned string carries the model fingerprint in its leading
  comment, so a UI consumer can display it without post-processing.

The CSV fixture is deterministic (seed=42) and reuses the shape of
``tests/test_e2e_mainwindow.py::_make_csv`` so that the trained CRT
is stable across runs.
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from backend_v3.session_state import Session  # noqa: E402
from backend_v3.types import PredictorType  # noqa: E402


def _quiet_logger() -> logging.Logger:
    lg = logging.getLogger("treegov.exporters_test")
    if not lg.handlers:
        lg.addHandler(logging.NullHandler())
    lg.propagate = False
    return lg


def _make_csv(path: Path, n: int = 200, seed: int = 42) -> Path:
    """Deterministic synthetic CSV: y = 1_{edad >= 40}."""
    rng = np.random.default_rng(seed)
    edad = rng.integers(20, 60, size=n)
    df = pd.DataFrame(
        {
            "edad": edad,
            "seg": rng.choice(["a", "b", "c"], size=n),
            "default": (edad >= 40).astype(int),
        }
    )
    df.to_csv(path, index=False)
    return path


def _trained_session(csv_path: Path) -> Session:
    """Drive a full pipeline so that _state.tree and _imputer are set."""
    s = Session(logger=_quiet_logger())
    s.load_dataset(str(csv_path))
    s.fix_spec(
        target="default",
        predictors=["edad", "seg"],
        target_class=1,
        class_labels={0: "Non-event", 1: "Event"},
    )
    s.partition(train_frac=0.7, seed=42)
    s.train("CRT", max_depth=3, min_child_size=20)
    return s


# ---------------------------------------------------------------------------
# Sin modelo entrenado → None
# ---------------------------------------------------------------------------


def test_export_to_sql_returns_none_without_model():
    s = Session(logger=_quiet_logger())
    assert s.export_to_sql() is None


def test_export_to_python_returns_none_without_model():
    s = Session(logger=_quiet_logger())
    assert s.export_to_python() is None


def test_export_to_markdown_returns_none_without_model():
    s = Session(logger=_quiet_logger())
    assert s.export_to_markdown() is None


# ---------------------------------------------------------------------------
# Con modelo entrenado → contenido verificable
# ---------------------------------------------------------------------------


def test_export_to_sql_after_train():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        s = _trained_session(csv)
        sql = s.export_to_sql()
        assert isinstance(sql, str)
        assert sql.strip()
        fp = s.state.tree.params_fingerprint
        assert sql.startswith(f"-- TreeGov Model Fingerprint: {fp}")
        assert "SELECT" in sql
        assert "COALESCE" in sql
        assert sql.rstrip().endswith(";")


def test_export_to_python_after_train():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        s = _trained_session(csv)
        source = s.export_to_python()
        assert isinstance(source, str)
        assert source.strip()
        fp = s.state.tree.params_fingerprint
        assert source.startswith(f"# TreeGov Model Fingerprint: {fp}")
        assert "def predict" in source
        assert "row.get" in source


def test_export_to_markdown_after_train():
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        s = _trained_session(csv)
        md = s.export_to_markdown()
        assert isinstance(md, str)
        assert md.strip()
        fp = s.state.tree.params_fingerprint
        assert md.startswith("# TreeGov Decision Tree")
        assert f"**Fingerprint:** {fp}" in md
        assert "**Method:**" in md
        assert "## Decision Rules" in md


def test_export_kinds_are_consistent_after_train():
    """Sanity: the three exports share the same fingerprint and all
    are non-empty strings."""
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        s = _trained_session(csv)
        fp = s.state.tree.params_fingerprint
        sql = s.export_to_sql()
        py = s.export_to_python()
        md = s.export_to_markdown()
        assert fp in sql
        assert fp in py
        assert fp in md


def test_wrappers_forward_unseen_policy():
    """Session wrappers forward the default and all implemented policies."""
    with tempfile.TemporaryDirectory() as td:
        csv = _make_csv(Path(td) / "mini.csv")
        s = _trained_session(csv)

        for export, error_marker, majority_marker in (
            (
                s.export_to_sql,
                "-- Unseen policy: error",
                "-- Unseen policy: majority",
            ),
            (
                s.export_to_python,
                "# Unseen policy: error",
                "# Unseen policy: majority",
            ),
            (
                s.export_to_markdown,
                "**Unseen policy:** error",
                "**Unseen policy:** majority",
            ),
        ):
            assert export(unseen_policy="exclude") == export()
            assert export(unseen_policy="error") != export()
            assert export(unseen_policy="majority") != export()

            error_output = export(unseen_policy="error")
            assert error_output
            assert error_marker in error_output
            majority_output = export(unseen_policy="majority")
            assert majority_output
            assert majority_marker in majority_output
