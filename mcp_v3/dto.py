"""JSON-native DTO conversion for the MCP layer (Phase 5.0).

Invariant I-3 (docs/5.0_design_mcp.md): json.dumps(payload,
allow_nan=False) must never raise for any tool output.
"""

import dataclasses
import math
from typing import Any

import numpy as np
import pandas as pd


def _jsonable(obj: Any) -> Any:
    """Recursively convert obj to JSON-native types.

    - dataclasses (frozen or not) -> dict
    - numpy scalars -> int / float / bool
    - numpy arrays / pandas Series -> list
    - pandas DataFrame -> list of dicts
    - NaN / Inf (float or numpy) -> None
    - dict / list / tuple / set -> recursively converted
    - str / int / bool / None -> returned as-is
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, np.ndarray):
        return [_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, pd.Series):
        return [_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, pd.DataFrame):
        return [_jsonable(row) for row in obj.to_dict(orient="records")]
    if dataclasses.is_dataclass(obj):
        return _jsonable(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(x) for x in obj]

    # Fallback de seguridad: si es un tipo no reconocido, lo pasamos a str
    # para no romper el protocolo JSON. Se documenta con TODO(zona_gris).
    # TODO(zona_gris): evaluar si este fallback oculta tipos que deberían
    # ser convertidos explícitamente en el futuro.
    return str(obj)
