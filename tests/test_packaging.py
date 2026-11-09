"""Tests de empaquetado: previenen la regresión del bug de rc1-rc5.

Regresión de rc6: pyproject.toml declaraba `packages` pero no `py-modules`,
y `treegov.py`, `treegov_gui.py`, `treegov_mcp.py` quedaban fuera del wheel
publicado en PyPI. Cualquier persona que hiciera `pip install treegov` y luego
`treegov-mcp` recibía ModuleNotFoundError.

Dual: ejecutable con pytest o con python tests/test_packaging.py.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _ROOT / "pyproject.toml"


def _load_pyproject() -> dict:
    with _PYPROJECT.open("rb") as f:
        return tomllib.load(f)


def test_py_modules_declared():
    """Los 3 .py raíz están declarados en py-modules."""
    data = _load_pyproject()
    py_modules = data["tool"]["setuptools"].get("py-modules", [])
    expected = {"treegov", "treegov_gui", "treegov_mcp"}
    assert expected <= set(py_modules), (
        f"py-modules debe contener {expected}, recibido: {py_modules}"
    )


def test_py_modules_exist_on_disk():
    """Los 3 .py raíz existen en la raíz del repo."""
    for module in ("treegov", "treegov_gui", "treegov_mcp"):
        path = _ROOT / f"{module}.py"
        assert path.is_file(), f"Falta {path}"


def test_packages_declared():
    """Las 4 carpetas de código están declaradas en packages."""
    data = _load_pyproject()
    packages = data["tool"]["setuptools"].get("packages", [])
    expected = {"backend_v3", "frontend_v3", "frontend_v3.resources", "mcp_v3"}
    assert expected <= set(packages), (
        f"packages debe contener {expected}, recibido: {packages}"
    )


def test_version_matches_between_pyproject_and_frontend():
    """La versión en pyproject.toml coincide con frontend_v3.__version__."""
    data = _load_pyproject()
    pyproject_version = data["project"]["version"]

    from frontend_v3 import __version__ as frontend_version
    assert pyproject_version == frontend_version, (
        f"pyproject={pyproject_version} != frontend={frontend_version}"
    )


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
