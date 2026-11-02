"""Tests for the MCP registry and DTO conversion (Phase 5.0.a)."""

import enum
import json
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from backend_v3.session_state import FlowState, Session
from mcp_v3.dto import _jsonable
from mcp_v3.tools import TOOLS


# --- Invariante I-3: JSON nativo ---

def test_jsonable_nan_and_inf_to_none():
    assert _jsonable(float("nan")) is None
    assert _jsonable(float("inf")) is None
    assert _jsonable(float("-inf")) is None
    assert _jsonable(np.float64("nan")) is None


def test_jsonable_numpy_scalars_to_native():
    assert _jsonable(np.int64(42)) == 42
    assert isinstance(_jsonable(np.int64(42)), int)
    assert _jsonable(np.float64(3.14)) == 3.14
    assert isinstance(_jsonable(np.float64(3.14)), float)
    assert _jsonable(np.bool_(True)) is True


def test_jsonable_numpy_and_pandas_collections():
    arr = np.array([1, 2, 3])
    assert _jsonable(arr) == [1, 2, 3]

    series = pd.Series([1.5, float("nan")])
    assert _jsonable(series) == [1.5, None]

    df = pd.DataFrame({"a": [1, 2], "b": ["x", None]})
    assert _jsonable(df) == [{"a": 1, "b": "x"}, {"a": 2, "b": None}]


@dataclass(frozen=True)
class _Dummy:
    a: int
    b: float

def test_jsonable_dataclass_to_dict():
    d = _Dummy(a=1, b=float("nan"))
    assert _jsonable(d) == {"a": 1, "b": None}


def test_jsonable_dict_and_list():
    obj = {"a": [1, 2, np.int64(3)], "b": float("inf")}
    assert _jsonable(obj) == {"a": [1, 2, 3], "b": None}


def test_json_dumps_allow_nan_false_never_raises():
    obj = {
        "f": float("nan"),
        "n": np.array([1, 2, np.float64("inf")]),
        "d": _Dummy(a=np.int64(1), b=2.0),
    }
    converted = _jsonable(obj)
    # Si falla, lanzará ValueError.
    assert json.dumps(converted, allow_nan=False) is not None


# --- Registro de herramientas ---

def test_tools_registry_has_27_tools():
    assert len(TOOLS) == 27


def test_tools_names_are_unique():
    names = [t.name for t in TOOLS]
    assert len(names) == len(set(names))


def test_every_tool_maps_to_a_real_session_attribute():
    for tool in TOOLS:
        assert hasattr(Session, tool.method_name), (
            f"Tool {tool.name} maps to missing Session attr "
            f"'{tool.method_name}'"
        )


def test_every_tool_has_valid_min_state():
    for tool in TOOLS:
        assert isinstance(tool.min_state, FlowState)


class _Color(enum.Enum):
    RED = "red"
    LEVEL = 3

def test_jsonable_enum_to_name():
    assert _jsonable(_Color.RED) == "RED"
    assert _jsonable(_Color.LEVEL) == "LEVEL"


def test_tool_descriptors_are_frozen():
    with pytest.raises(Exception):
        # Intentar mutar un descriptor frozen debe fallar
        TOOLS[0].name = "hacked"
