"""scripts/fetch_datasets.py — descarga y normalización de los 6 datasets UCI.

Sub-fase 1.b.1 de la Fase 1 (diseño: docs/scripts_design.md §1, contratos
F1–F8). Uso:

    python scripts/fetch_datasets.py
    python scripts/fetch_datasets.py --refresh-hash

Contratos as-built (por ID del backlog):

- F1 (idempotencia): si ``data/uci/<name>/<name>.csv`` existe y su SHA-256
  (FIPS 180-4) coincide con el sidecar ``<name>.csv.sha256``, el dataset
  se salta (log INFO). Cualquier otra combinación (sidecar ausente o hash
  distinto) aborta con ``RuntimeError`` pidiendo revisión manual.
- F2 (destino): se escribe SOLO bajo ``data/uci/``; ``tests/fixtures/uci/``
  es material versionado de solo lectura.
- F3 (parseo): las filas se parten con ``csv.reader`` (delimiter=sep),
  nunca con ``str.split``.
- F4 (target_map): un valor de target fuera del mapa lanza ``ValueError``
  que nombra el dataset y el valor; el mapa de blood_transfusion está
  completo en el manifiesto para que el binario sea explícito y el fallo
  ocurra en la fase de fetch, no en un E2E posterior.
- F5 (logging): ``backend_v3.log_config`` (logger ``treegov.fetch``); sin
  prints. Cada download/skip/verify escribe su registro.
- F6 (reintentos): backoff exponencial (pausas de 2 s y 4 s, 3 intentos en
  total) SOLO para errores transitorios de red (``URLError`` /
  ``socket.timeout``); los ``HTTPError`` deterministas (4xx) y el fallo de
  integridad del hash NO se reintentan.
- F7 (workflow de hashes): ``--refresh-hash`` re-descarga sin exigir el
  SHA del manifiesto, calcula el hash real, actualiza el diccionario
  ``DATASETS`` en memoria y reescribe este mismo archivo Python con el
  hash nuevo (el diff resultante requiere commit humano).
- F8 (paths): ``ROOT_DIR`` y ``DATA_DIR`` anclados a ``__file__``, nunca
  al cwd.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent  # F8: raíz del repo, no cwd
SRC_PATH = Path(__file__).resolve()                # F7: este archivo (refresh)
DATA_DIR = ROOT_DIR / "data" / "uci"               # F2: destino canónico
LOG_PATH = ROOT_DIR / "logs" / "fetch_datasets.log"

sys.path.insert(0, str(ROOT_DIR))  # F8: backend_v3 importable desde la raíz

from backend_v3.log_config import get_logger, setup_logging  # noqa: E402  F5

log = get_logger("fetch")

DATASETS = {
    "german_credit": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/statlog/german/german.data",
        "sha256": "b21f3d81db8071257d5ff1deaeba1fd4303b62712e6fcc9715c7a86202cb5871",
        "sep": " ",
        "has_header": False,
        "cols": ["checking_status", "duration_months", "credit_history", "purpose", "credit_amount", "savings_status", "employment", "installment_rate", "personal_status", "other_parties", "residence_since", "property_magnitude", "age", "other_payment_plans", "housing", "existing_credits", "job", "num_dependents", "own_telephone", "foreign_worker", "target"],
        "target_idx": 20,
        "target_map": {"1": "0", "2": "1"}
    },
    "car_evaluation": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/car/car.data",
        "sha256": "b703a9ac69f11e64ce8c223c0a40de4d2e9d769f7fb20be5f8f2e8a619893d83",
        "sep": ",",
        "has_header": False,
        "cols": ["buying", "maint", "doors", "persons", "lug_boot", "safety", "target"],
        "target_idx": 6,
        "target_map": {"unacc": "0", "acc": "1", "good": "2", "vgood": "3"}
    },
    "balance_scale": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/balance-scale/balance-scale.data",
        "sha256": "5611187ef7345d807aa8ae22615945ade52a190537c0b1434bd44c3e877c5bb4",
        "sep": ",",
        "has_header": False,
        "cols": ["left_weight", "left_distance", "right_weight", "right_distance", "target"],
        "target_idx": 0,
        "target_map": {"L": "0", "B": "1", "R": "2"}
    },
    # Nota as-built (31/10/2026, B9): el diseno 3.6_design_public_datasets.md
    # §3.5 pedia nombres descriptivos (radius_mean, texture_mean, ...); la
    # implementacion usa f1..f30 por simplicidad. Los fingerprints UCI
    # (e46011f55ed957bf, 389f70f0fba1a180) estan anclados a esta eleccion;
    # corregir los nombres requeriria una recaptura con rotura de rc4.
    "breast_cancer_wdbc": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/breast-cancer-wisconsin/wdbc.data",
        "sha256": "d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a",
        "sep": ",",
        "has_header": False,
        "cols": [f"f{i}" for i in range(1, 31)] + ["target"],
        "target_idx": 1,
        "target_map": {"M": "1", "B": "0"},
        "drop_cols": [0]
    },
    "iris": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data",
        "sha256": "6f608b71a7317216319b4d27b4d9bc84e6abd734eda7872b71a458569e2656c0",
        "sep": ",",
        "has_header": False,
        "cols": ["sepal_length", "sepal_width", "petal_length", "petal_width", "target"],
        "target_idx": 4,
        "target_map": {"Iris-setosa": "0", "Iris-versicolor": "1", "Iris-virginica": "2"}
    },
    "blood_transfusion": {
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/blood-transfusion/transfusion.data",
        "sha256": "96c8e1091b9c037bcaf25a19b24b49d07771cd88689ffd273e056e9e8845ffe7",
        "sep": ",",
        "has_header": True,
        "cols": ["recency_months", "frequency_times", "monetary_cc", "time_months", "target"],
        "target_idx": 4,
        "target_map": {"0": "0", "1": "1"}
    }
}


class _HashMismatch(RuntimeError):
    """Fallo de integridad SHA-256 (no de red): nunca se reintenta (F6)."""


def _sha256_hex(data: bytes) -> str:
    """SHA-256 del payload en hex minúsculas. Referencia: FIPS 180-4."""
    return hashlib.sha256(data).hexdigest()


def _download_payload(url: str, max_retries: int = 3) -> bytes:
    """Descarga en bytes con reintentos y backoff exponencial (F6).

    Solo se reintenta ante errores transitorios de red (``URLError``,
    ``socket.timeout``) con pausas de 2 s y 4 s (3 intentos totales). Un
    ``HTTPError`` con código transitorio (408/429/5xx) entra al ciclo de
    reintentos; un ``HTTPError`` determinista (4xx resto) aborta de
    inmediato: es un fallo determinista de la fuente, no de red.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TreeGov/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            return data
        except urllib.error.HTTPError as exc:
            transient = exc.code in (408, 429) or 500 <= exc.code < 600
            if not transient:
                log.error(f"HTTPError determinista {exc.code} en {url}: abortando")
                raise
            last_exc = exc
        except (urllib.error.URLError, socket.timeout) as exc:
            last_exc = exc
        if attempt < max_retries:
            delay_s = 2 ** attempt  # pausa 2 s tras el intento 1, 4 s tras el 2
            log.warning(
                f"intento {attempt}/{max_retries} falló en {url} "
                f"({type(last_exc).__name__}); reintentando en {delay_s} s"
            )
            time.sleep(delay_s)
    raise RuntimeError(
        f"Descarga agotada tras {max_retries} intentos para {url}: {last_exc!r}"
    ) from last_exc


def download_with_retry(url: str, expected_sha: str, max_retries: int = 3) -> str:
    """Descarga + verificación SHA-256 (F6/F1). Devuelve texto UTF-8.

    El fallo de integridad del hash NO es de red (F6): se lanza
    ``_HashMismatch`` (subclase de ``RuntimeError``) sin reintentos.
    """
    data = _download_payload(url, max_retries=max_retries)
    actual_sha = _sha256_hex(data)
    if actual_sha != expected_sha:
        raise _HashMismatch(
            f"Hash mismatch for {url}: expected {expected_sha}, got {actual_sha}"
        )
    log.info(f"verificado {url} sha256={actual_sha}")
    return data.decode("utf-8")


def process_row(row: list[str], ds: dict) -> list[str] | None:
    """Normaliza UNA fila ya particionada por ``csv.reader`` (F3).

    - Fila vacía (sin celdas o con todas en blanco) -> ``None`` (omisión).
    - F4: el valor del target DEBE estar en ``target_map``; un valor sin
      mapear lanza ``ValueError`` con dataset y valor (nunca passthrough
      silencioso).
    """
    row = [v.strip() for v in row]
    if not row or all(v == "" for v in row):
        return None

    raw_target = row[ds["target_idx"]]
    target_map = ds.get("target_map", {}) or {}
    if raw_target not in target_map:
        raise ValueError(
            f"Valor de target '{raw_target}' sin mapear para el dataset "
            f"'{ds.get('name', '<sin nombre>')}' (target_map={target_map!r})"
        )
    target_val = target_map[raw_target]

    drop = set(ds.get("drop_cols", []))
    features = [
        v for i, v in enumerate(row) if i != ds["target_idx"] and i not in drop
    ]
    return features + [target_val]


def _read_sidecar(sidecar_path: Path) -> str:
    """Hash registrado en el sidecar ``<name>.csv.sha256`` (whitespace strip)."""
    return sidecar_path.read_text(encoding="utf-8").strip()


def _refresh_source_hash(name: str, old_sha: str, new_sha: str) -> None:
    """Reescribe este archivo reemplazando el SHA viejo por el nuevo (F7).

    Se hace en bytes (no texto) para no perturbar los line endings del
    repo (normalizados vía ``.gitattributes``). Solo actúa si el hash
    cambió y la ocurrencia del SHA viejo en el código fuente es única.
    """
    if old_sha == new_sha:
        log.info(f"--refresh-hash: {name} ya está al día (sha {new_sha})")
        return
    src = SRC_PATH.read_bytes()
    needle = old_sha.encode("ascii")
    occurrences = src.count(needle)
    if occurrences != 1:
        raise RuntimeError(
            f"No se puede refrescar el hash de {name}: el SHA viejo no es "
            f"único en {SRC_PATH.name} (ocurrencias={occurrences}); "
            "revise el manifiesto manualmente."
        )
    SRC_PATH.write_bytes(src.replace(needle, new_sha.encode("ascii")))
    log.info(
        f"--refresh-hash: {name} manifiesto actualizado "
        f"{old_sha} -> {new_sha}"
    )


def fetch_one(name: str, ds: dict, refresh_hash: bool = False) -> None:
    """Descarga, normaliza y escribe UN dataset bajo ``DATA_DIR`` (F1–F8)."""
    ds_view = dict(ds)
    ds_view["name"] = name  # nombre disponible para los mensajes de F4

    out_dir = DATA_DIR / name                      # F2/F8: data/uci/<name>/
    out_path = out_dir / f"{name}.csv"
    sidecar_path = out_dir / f"{name}.csv.sha256"  # F1: sidecar del hash

    # ---- F1: idempotencia por hash sidecar -------------------------------
    if out_path.exists():
        disk_sha = _sha256_hex(out_path.read_bytes())
        if sidecar_path.exists() and _read_sidecar(sidecar_path) == disk_sha:
            log.info(
                f"skip {name}: {out_path} ya está al día (sha256={disk_sha})"
            )
            return
        raise RuntimeError(
            f"Integridad dudosa para {name}: {out_path} existe pero su hash "
            f"(sha256={disk_sha}) no coincide con el sidecar {sidecar_path}; "
            "requiere revisión manual (borre CSV y sidecar a mano, o use "
            "--refresh-hash tras revisar la fuente)."
        )

    # ---- F6/F7: descarga con verificación (o refresh de manifiesto) ------
    if refresh_hash:
        data = _download_payload(ds["url"])
        actual_sha = _sha256_hex(data)
        expected_sha = ds["sha256"]
        if actual_sha != expected_sha:
            log.warning(
                f"--refresh-hash: {name} SHA real difiere del manifiesto "
                f"({expected_sha} -> {actual_sha}); actualizando"
            )
        ds["sha256"] = actual_sha                            # F7: dict vivo
        _refresh_source_hash(name, expected_sha, actual_sha)  # F7: archivo
        raw_text = data.decode("utf-8")
    else:
        raw_text = download_with_retry(ds["url"], ds["sha256"])

    # ---- F3: partición CSV con csv.reader, nunca str.split ----------------
    lines = raw_text.splitlines()
    if ds["has_header"]:
        lines = lines[1:]
    reader = csv.reader(lines, delimiter=ds["sep"])

    out_dir.mkdir(parents=True, exist_ok=True)
    written_rows = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(ds["cols"])
        for row in reader:
            processed = process_row(row, ds_view)
            if processed:
                writer.writerow(processed)
                written_rows += 1

    # ---- F1: sidecar del CSV normalizado ----------------------------------
    disk_sha = _sha256_hex(out_path.read_bytes())
    sidecar_path.write_text(disk_sha, encoding="utf-8")
    log.info(f"descarga {out_path} ({written_rows} rows), sha256={disk_sha}")


def main(argv: list[str] | None = None) -> int:
    """Entrypoint del script. Devuelve 0 cuando todo el lote completa.

    Los errores de datos (F4 ``ValueError``) y de integridad (F1/F6/F7)
    se propagan: abortan con traceback y exit != 0.
    """
    parser = argparse.ArgumentParser(
        description="Descarga y normaliza los datasets UCI hacia data/uci/ "
        "(docs/scripts_design.md §1)."
    )
    parser.add_argument(
        "--refresh-hash", action="store_true", dest="refresh_hash",
        help="No valida contra el SHA del manifiesto; calcula el hash real, "
        "actualiza DATASETS en memoria y reescribe este archivo (workflow F7).",
    )
    args = parser.parse_args(argv)

    # Consola cp1252 (PowerShell legacy): evita UnicodeEncodeError en el
    # StreamHandler si un mensaje de log contiene caracteres fuera de la
    # codepage (paridad con update_readme_date.py).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    setup_logging(str(LOG_PATH), logging.INFO)  # F5
    log.info(f"fetch_datasets iniciado (refresh_hash={args.refresh_hash})")

    for name, ds in DATASETS.items():
        fetch_one(name, ds, refresh_hash=args.refresh_hash)

    log.info(f"fetch_datasets completado ({len(DATASETS)} datasets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
