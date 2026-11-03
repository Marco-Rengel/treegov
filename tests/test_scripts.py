"""Contract tests for the Phase-1 infrastructure scripts (design §4).

Covers scripts/fetch_datasets.py, scripts/update_readme_date.py and
scripts/validate_uci.py. No real network: urllib.request.urlopen is
always replaced by an in-memory fake. No writes under the repository:
every filesystem target is redirected to a temporary directory.

The tests are argless on purpose: they run identically under pytest and
with ``python tests/test_scripts.py`` (CONVENTIONS.md §Tests). Isolation
uses ``tempfile.TemporaryDirectory`` and ``unittest.mock.patch``.

Exit-code contract: the script entrypoints return int codes (0 = OK,
1 = pending/regenerable in --check, 2 = data error); the CLI wrapper
``raise SystemExit(main())`` turns them into process exit codes.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import os
import sys
import tempfile
import urllib.request
from datetime import date as Date
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_datasets  # noqa: E402
import update_readme_date  # noqa: E402
import validate_uci  # noqa: E402
from backend_v3.types import TargetType  # noqa: E402

MARKER = "\U0001F4C5"  # calendar emoji of the README date contract


class _FakeResponse:
    """Minimal urlopen() response: context manager with read()."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


class _CollectHandler(logging.Handler):
    """Capture log messages emitted by a specific logger."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


# ---------------------------------------------------------------------------
# fetch_datasets.py
# ---------------------------------------------------------------------------

def test_fetch_parse_robust() -> None:
    """F3/F4: csv.reader rows are parsed and unmapped targets raise."""
    ds = {
        "name": "fake",
        "target_idx": 1,
        "target_map": {"1": "0", "2": "1"},
    }
    # F3: the row comes from csv.reader, never from str.split.
    rows = list(csv.reader(["7,1", "8,2"], delimiter=","))
    assert fetch_datasets.process_row(rows[0], ds) == ["7", "0"]
    assert fetch_datasets.process_row(rows[1], ds) == ["8", "1"]

    # F4: an unmapped target names the dataset and the offending value.
    with pytest.raises(ValueError, match="sin mapear"):
        fetch_datasets.process_row(["9", "9"], ds)

    # Blank rows are skipped, not mapped.
    assert fetch_datasets.process_row([], ds) is None
    assert fetch_datasets.process_row(["", ""], ds) is None


def test_fetch_idempotency_and_hash() -> None:
    """F1/F5/F6: first run writes CSV + sidecar; second run skips."""
    payload = b"alpha,1\nbeta,2\ngamma,1\n"
    dataset = {
        "url": "https://example.invalid/fake.csv",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "sep": ",",
        "has_header": False,
        "cols": ["feature", "target"],
        "target_idx": 1,
        "target_map": {"1": "0", "2": "1"},
    }
    calls: list[str] = []

    def fake_urlopen(req, timeout=30):  # noqa: ANN001, ARG001
        calls.append(req.full_url)
        return _FakeResponse(payload)

    handler = _CollectHandler()
    logger = logging.getLogger("treegov.fetch")
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(fetch_datasets, "DATA_DIR", tmp / "uci"), \
                 mock.patch.object(fetch_datasets, "LOG_PATH", tmp / "fetch.log"), \
                 mock.patch.object(fetch_datasets, "DATASETS", {"fake": dataset}), \
                 mock.patch.object(
                     fetch_datasets, "setup_logging",
                     lambda *args, **kwargs: None,
                 ), \
                 mock.patch.object(urllib.request, "urlopen", fake_urlopen):
                assert fetch_datasets.main([]) == 0

                out = tmp / "uci" / "fake" / "fake.csv"
                sidecar = out.with_name("fake.csv.sha256")
                assert out.exists()
                assert sidecar.exists()
                disk_sha = fetch_datasets._sha256_hex(out.read_bytes())
                assert sidecar.read_text(encoding="utf-8") == disk_sha
                assert len(calls) == 1
                lines = out.read_text(encoding="utf-8").splitlines()
                assert lines[0] == "feature,target"
                assert lines[1:] == ["alpha,0", "beta,1", "gamma,0"]
                assert not any("skip" in message for message in handler.messages)

                # Second pass: sidecar matches, so no download happens.
                handler.messages.clear()
                assert fetch_datasets.main([]) == 0
                assert len(calls) == 1
                assert any("skip fake" in message for message in handler.messages)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


# ---------------------------------------------------------------------------
# update_readme_date.py
# ---------------------------------------------------------------------------

def _write_readmes(root: Path, en_date: str, es_date: str) -> None:
    en = f'ST["<b>Current status</b><br/>{MARKER} {en_date}"]\n'
    es = f'ST["<b>Estado actual</b><br/>{MARKER} {es_date}"]\n'
    with (root / "README.md").open("w", encoding="utf-8", newline="") as f:
        f.write(en)
    with (root / "README.es.md").open("w", encoding="utf-8", newline="") as f:
        f.write(es)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        name: (root / name).read_bytes()
        for name in ("README.md", "README.es.md")
    }


def test_update_readme_check_mode() -> None:
    """U4/U5: --check returns 1 on stale dates, 0 when up to date."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with mock.patch.object(update_readme_date, "ROOT_DIR", tmp):
            # Up to date: exit code 0 and no writes.
            _write_readmes(tmp, "Nov 02, 2026", "02 nov 2026")
            before = _snapshot(tmp)
            assert update_readme_date.main(
                ["--check", "--date", "2026-11-02"]
            ) == 0
            assert _snapshot(tmp) == before

            # Stale: exit code 1 and still no writes.
            _write_readmes(tmp, "Nov 01, 2026", "01 nov 2026")
            before = _snapshot(tmp)
            assert update_readme_date.main(
                ["--check", "--date", "2026-11-02"]
            ) == 1
            assert _snapshot(tmp) == before


def test_update_readme_atomic() -> None:
    """U2: a failing second rename restores the first target."""
    en_old = f'ST["{MARKER} Nov 02, 2026"]\n'
    es_old = f'ST["{MARKER} 02 nov 2026"]\n'
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        en_path = tmp / "README.md"
        es_path = tmp / "README.es.md"
        with en_path.open("w", encoding="utf-8", newline="") as f:
            f.write(en_old)
        with es_path.open("w", encoding="utf-8", newline="") as f:
            f.write(es_old)

        real_replace = os.replace
        calls = {"n": 0}

        def flaky_replace(src, dst):  # noqa: ANN001
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("simulated failure on the second rename")
            return real_replace(src, dst)

        with mock.patch.object(update_readme_date, "ROOT_DIR", tmp), \
             mock.patch.object(os, "replace", flaky_replace):
            with pytest.raises(RuntimeError, match="escritura atomica fallida"):
                update_readme_date.run_mutate(Date(2026, 11, 20))

        assert calls["n"] == 2
        with en_path.open("r", encoding="utf-8", newline="") as f:
            assert f.read() == en_old
        with es_path.open("r", encoding="utf-8", newline="") as f:
            assert f.read() == es_old
        assert not list(tmp.glob("*.tmp"))


# ---------------------------------------------------------------------------
# validate_uci.py
# ---------------------------------------------------------------------------

class _FakeNode:
    def __init__(self, is_leaf: bool) -> None:
        self.is_leaf = is_leaf


class _FakeTree:
    params_fingerprint = "0123456789abcdef"
    nodes = (_FakeNode(False), _FakeNode(True))


class _FakeMetrics:
    gini = 0.42
    ks = 0.31
    auc = 0.71


class _FakeState:
    def __init__(self, n_test: int) -> None:
        self.test_idx = tuple(range(n_test))
        self.tree = _FakeTree()
        self.oos_metrics = _FakeMetrics()


class _FakeSession:
    """Minimal Session double that records train/evaluate_oos kwargs."""

    instances: list["_FakeSession"] = []
    n_test = 20

    def __init__(self) -> None:
        self.train_kwargs: dict = {}
        self.n_groups: int | None = None
        self._state = _FakeState(self.n_test)
        type(self).instances.append(self)

    def load_dataset(self, path: str) -> None:
        self.dataset_path = path

    def describe_dataset(self):
        return ["feature_a", "feature_b", "target"], None

    def fix_spec(self, **kwargs) -> None:
        self.spec_kwargs = kwargs

    def partition(self, **kwargs) -> None:
        self.partition_kwargs = kwargs

    def train(self, **kwargs) -> None:
        self.train_kwargs = kwargs

    def evaluate_oos(self, *, n_groups: int = 10) -> None:
        self.n_groups = n_groups

    @property
    def state(self) -> _FakeState:
        return self._state

    def get_classification_matrix(self):
        return {"accuracy": 0.8}


def test_validate_n_groups_adaptive() -> None:
    """V1: 20 test rows give n_groups = min(10, max(3, 20 // 5)) = 4."""
    _FakeSession.instances.clear()
    _FakeSession.n_test = 20
    with mock.patch.object(validate_uci, "Session", _FakeSession):
        row = validate_uci._run_one(
            "german_credit", validate_uci.CONFIGS["german_credit"], "CRT"
        )

    assert row["error"] is None
    session = _FakeSession.instances[-1]
    assert len(session.state.test_idx) == 20
    # Session.evaluate_oos forwards n_groups to compute_oos_metrics
    # (backend_v3/session_state.py); here we assert the value _run_one
    # computes from the real test size.
    assert session.n_groups == 4
    assert session.n_groups * 5 <= len(session.state.test_idx)


def test_validate_target_type() -> None:
    """V2: car trains as CATEGORICAL, german_credit as BINARY."""
    _FakeSession.instances.clear()
    _FakeSession.n_test = 20
    with mock.patch.object(validate_uci, "Session", _FakeSession):
        car_row = validate_uci._run_one(
            "car_evaluation", validate_uci.CONFIGS["car_evaluation"], "CRT"
        )
        car = _FakeSession.instances[-1]

        german_row = validate_uci._run_one(
            "german_credit", validate_uci.CONFIGS["german_credit"], "CRT"
        )
        german = _FakeSession.instances[-1]

    assert car_row["error"] is None
    assert german_row["error"] is None
    assert car.train_kwargs["target_type"] is TargetType.CATEGORICAL
    assert german.train_kwargs["target_type"] is TargetType.BINARY


if __name__ == "__main__":
    tests = [
        obj
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
