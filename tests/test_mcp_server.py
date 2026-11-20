"""Tests for the MCP server (Phase 5.0.b / hardened in Block 2C)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

mcp = pytest.importorskip("mcp")
from backend_v3.import_guard import is_installed  # noqa: E402
from mcp_v3 import server  # noqa: E402


def _make_csv(path: Path) -> Path:
    rng = np.random.default_rng(42)
    edad = rng.integers(20, 60, size=100)
    df = pd.DataFrame({
        "edad": edad,
        "y": (edad >= 40).astype(int)
    })
    df.to_csv(path, index=False)
    return path


def test_server_tools_registered():
    # FastMCP registra las herramientas en app._tool_manager._tools
    assert hasattr(server.app, "_tool_manager")
    tools = server.app._tool_manager._tools
    assert len(tools) == 27


def test_server_e2e_flow(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("TREEGOV_MCP_ROOT", td)
        server._session = None
        csv = _make_csv(Path(td) / "mini.csv")

        # 1. Cargar
        st = server.load_dataset(str(csv))
        assert st["state"] == "DATA_LOADED"

        # 2. Configurar (con cast de string a int para Pydantic)
        server.fix_spec(
            target="y",
            target_class="1",  # test del cast
            class_labels={"0": "Good", "1": "Bad"},
            predictors=["edad"],
        )

        # 3. Particionar y entrenar (min_child_size=5 para que entrene)
        server.partition()
        st = server.train(engine="CRT", max_depth=2, min_child_size=5)
        assert st["state"] == "TRAINED"

        # 4. Evaluar y exportar
        server.evaluate_oos()
        report = server.get_oos_oot_report()
        assert report is not None

        sql = server.export_sql()
        assert "-- TreeGov Model Fingerprint:" in sql

        # I-3 check (allow_nan=False no debe fallar)
        json.dumps(report, allow_nan=False)
        server._session = None


def test_train_requires_partition():
    # Zona gris: reseteamos para probar el estado transaccional
    server._session = None  # Hack para el test unitario
    with pytest.raises(Exception):
        server.evaluate_oos()


def test_mcp_path_confinement_and_extension_checks(tmp_path, monkeypatch):
    """Path traversal, outside absolute paths and non-.csv files are rejected."""
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setenv("TREEGOV_MCP_ROOT", str(allowed))
    server._session = None

    outside_csv = _make_csv(outside / "outside.csv")
    for ext in (".txt", ".py", ".json"):
        bad_file = allowed / f"payload{ext}"
        bad_file.write_text("a,b\n1,2\n", encoding="utf-8")
        with pytest.raises(ValueError, match=r"\.csv"):
            server.load_dataset(str(bad_file))

    with pytest.raises(ValueError, match="fuera del directorio autorizado"):
        server.load_dataset("../outside/outside.csv")

    with pytest.raises(ValueError, match="fuera del directorio autorizado"):
        server.load_dataset(str(outside_csv))


def test_mcp_train_rejects_invalid_governance_and_target_type(
    tmp_path, monkeypatch
):
    """Typos in governance_mode or target_type fail fast with ValueError."""
    monkeypatch.setenv("TREEGOV_MCP_ROOT", str(tmp_path))
    server._session = None
    csv = _make_csv(tmp_path / "data.csv")
    server.load_dataset(str(csv))
    server.fix_spec(
        target="y",
        target_class="1",
        class_labels={"0": "Good", "1": "Bad"},
        predictors=["edad"],
    )
    server.partition()

    with pytest.raises(ValueError, match="governance_mode"):
        server.train(engine="CRT", governance_mode="reserch")

    with pytest.raises(ValueError, match="target_type"):
        server.train(engine="CRT", target_type="binry")

    server._session = None


def test_mcp_fix_spec_safe_coercion_and_validation(tmp_path, monkeypatch):
    """fix_spec rejects empty population_ok_values, handles Unicode/neg/str keys."""
    monkeypatch.setenv("TREEGOV_MCP_ROOT", str(tmp_path))
    server._session = None

    # 1. Binary dataset: empty population_ok_values and Unicode "²"
    csv_bin = _make_csv(tmp_path / "bin.csv")
    server.load_dataset(str(csv_bin))

    with pytest.raises(ValueError, match="population_ok_values"):
        server.fix_spec(
            target="y",
            target_class="1",
            class_labels={"0": "Good", "1": "Bad"},
            predictors=["edad"],
            population_ok_values=[],
        )

    # Unicode superscript digit must not crash int(); yields clean ValueError
    with pytest.raises(ValueError, match="target_class"):
        server.fix_spec(
            target="y",
            target_class="²",
            class_labels={"0": "Good", "1": "Bad"},
            predictors=["edad"],
        )

    # 2. Negative integer multiclass target (-1, 0, 1)
    server._session = None
    csv_neg = tmp_path / "neg.csv"
    pd.DataFrame(
        {
            "edad": [20 + i for i in range(30)],
            "y": [-1, 0, 1] * 10,
        }
    ).to_csv(csv_neg, index=False)
    server.load_dataset(str(csv_neg))
    st_neg = server.fix_spec(
        target="y",
        target_class="-1",
        class_labels={"-1": "Neg", "0": "Zero", "1": "Pos"},
        predictors=["edad"],
    )
    assert st_neg["state"] == "SPEC_FIXED"
    assert st_neg["target_class"] == -1

    # 3. String multiclass target preserving leading-zero keys ("01", "02", "A3")
    server._session = None
    csv_str = tmp_path / "str_target.csv"
    pd.DataFrame(
        {
            "edad": [20 + i for i in range(30)],
            "y": ["01", "02", "A3"] * 10,
        }
    ).to_csv(csv_str, index=False)
    server.load_dataset(str(csv_str))
    st_str = server.fix_spec(
        target="y",
        target_class="01",
        class_labels={"01": "Class01", "02": "Class02", "A3": "ClassA3"},
        predictors=["edad"],
    )
    assert st_str["state"] == "SPEC_FIXED"
    assert st_str["target_class"] == "01"
    assert isinstance(st_str["target_class"], str)
    server._session = None


def test_mcp_numeric_bounds_nan_inf_and_bool_rejection(tmp_path, monkeypatch):
    """Numeric MCP parameters reject out-of-range, NaN/Inf and bool values."""
    monkeypatch.setenv("TREEGOV_MCP_ROOT", str(tmp_path))
    server._session = None
    csv = _make_csv(tmp_path / "num.csv")
    server.load_dataset(str(csv))

    with pytest.raises(ValueError, match="n_rows"):
        server.get_data_preview(n_rows=0)
    with pytest.raises(ValueError, match="n_rows"):
        server.get_data_preview(n_rows=True)

    server.fix_spec(
        target="y",
        target_class="1",
        class_labels={"0": "Good", "1": "Bad"},
        predictors=["edad"],
    )

    with pytest.raises(ValueError, match="train_frac"):
        server.partition(train_frac=float("nan"))
    with pytest.raises(ValueError, match="train_frac"):
        server.partition(train_frac=float("inf"))
    with pytest.raises(ValueError, match="train_frac"):
        server.partition(train_frac=1.0)

    server.partition()

    with pytest.raises(ValueError, match="max_depth"):
        server.train(engine="CRT", max_depth=99)
    with pytest.raises(ValueError, match="min_child_size"):
        server.train(engine="CRT", min_child_size=0)
    with pytest.raises(ValueError, match="min_child_weight"):
        server.train(engine="CRT", min_child_weight=0.0)

    server.train(engine="CRT", max_depth=2, min_child_size=5)

    with pytest.raises(ValueError, match="chunksize"):
        server.score_batch(str(csv), str(tmp_path / "out.csv"), chunksize=0)

    server._session = None


def test_treegov_mcp_activates_import_guard(monkeypatch):
    """Importing and running treegov_mcp installs the white-box import guard."""
    import treegov_mcp

    assert is_installed() is True

    calls: list[str] = []
    monkeypatch.setattr(
        treegov_mcp,
        "install_import_guard",
        lambda: calls.append("guard"),
    )
    fake_run = MagicMock(side_effect=lambda: calls.append("run"))
    monkeypatch.setattr(server.app, "run", fake_run)

    treegov_mcp.main()
    assert calls == ["guard", "run"]
