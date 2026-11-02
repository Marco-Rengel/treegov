"""Tests for the MCP server (Phase 5.0.b)."""

import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

mcp = pytest.importorskip("mcp")
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


def test_server_e2e_flow():
    with tempfile.TemporaryDirectory() as td:
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


def test_train_requires_partition():
    # Zona gris: reseteamos para probar el estado transaccional
    server._session = None  # Hack para el test unitario
    with pytest.raises(Exception):
        server.evaluate_oos()
