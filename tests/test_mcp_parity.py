"""E2E parity tests for the MCP server (Phase 5.0.c).

Simulates an LLM client orchestrating the full pipeline via the
server tools, verifying I-3 (JSON-native) and K=2 parity.
"""

import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

mcp = pytest.importorskip("mcp")
from mcp_v3 import server  # noqa: E402


@pytest.fixture()
def csv_path():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "parity.csv"
        rng = np.random.default_rng(42)
        edad = rng.integers(20, 60, size=200)
        df = pd.DataFrame({
            "edad": edad,
            "seg": rng.choice(["a", "b", "c"], size=200),
            "y": (edad >= 40).astype(int)
        })
        df.to_csv(path, index=False)
        yield path
        # Teardown: reset the global server session
        server._session = None


@pytest.mark.parametrize("engine", ["CRT", "QUEST", "CHAID", "CHAID_EXHAUSTIVE"])
def test_parity_all_engines(csv_path, engine):
    """Train with every engine and verify the MCP flow parity."""
    # 1. Cargar y configurar
    server.load_dataset(str(csv_path))
    server.fix_spec(
        target="y",
        target_class=1,
        class_labels={"0": "Good", "1": "Bad"},
        predictors=["edad", "seg"],
    )

    # 2. Particionar y entrenar
    server.partition(train_frac=0.7, seed=42)
    st = server.train(engine=engine, max_depth=3, min_child_size=10)
    assert st["state"] == "TRAINED"

    # 3. Capturar fingerprint (I-6)
    fp = st["tree"]["params_fingerprint"]
    assert fp is not None

    # 4. Evaluar
    server.evaluate_oos()
    report = server.get_oos_oot_report()

    # 5. Exportar
    # H-5.0.c-1 (resuelto 01/11/2026): los splits CHAID continuos con ramas
    # fusionadas exportan por RAMA consolidada (design_decisions.md §16.3),
    # no por bin individual; ver tests/test_exporters.py para la paridad de
    # scoring con bins fusionados.
    sql = server.export_sql()
    py = server.export_python()
    md = server.export_markdown()

    assert fp in sql
    assert fp in py
    assert fp in md

    # 6. Invariante I-3 (JSON estricto)
    # Si algo tiene NaN, json.dumps fallará.
    payload = {
        "state": st,
        "report": report,
        "sql": sql,
        "py": py,
        "md": md
    }
    json.dumps(payload, allow_nan=False)


def test_all_tools_return_jsonable(csv_path):
    """Call every tool and ensure the output is JSON-serializable."""
    server.load_dataset(str(csv_path))
    server.fix_spec(
        target="y", target_class=1,
        class_labels={"0": "G", "1": "B"}, predictors=["edad", "seg"]
    )
    server.partition()
    server.train(engine="CRT", min_child_size=10)

    # Lista de llamadas para cubrir la superficie de tools
    outputs = [
        server.get_session_state(),
        server.describe_dataset(),
        server.get_data_preview(n_rows=10),
        server.describe_target("y"),
        server.evaluate_oos(),
        server.get_oos_oot_report(),
        server.get_gains_table(),
        server.get_classification_matrix(),
        server.get_univariate_trees(),
        server.get_prune_sequence(),
        server.export_sql(),
        server.export_python(),
        server.export_markdown(),
    ]

    for out in outputs:
        # Esto lanzará ValueError si hay NaN/Inf
        json.dumps(out, allow_nan=False)

# TODO(zona_gris): el contenido original de la sub-fase pedía llamar
# server.export_to_python() y server.export_to_markdown(); esas firmas
# existen solo en backend_v3.session_state.Session. La capa servidor
# (mcp_v3/server.py, Grupo F) expone export_sql/export_python/
# export_markdown. Se resolvió conservadoramente hacia los nombres de
# la capa servidor porque el test simula un cliente LLM consumiendo el
# server MCP, y registrar el desvío aquí y en docs/audit_log.md.
