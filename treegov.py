"""TreeGov - orquestador headless Fase 0 (demo auditable de los 4 motores).

Pipeline (todo registrado en logs/opencode_debug_<timestamp>.log, nivel DEBUG):

  1. install_import_guard() ANTES de cualquier import pesado (caja blanca);
     verificacion en runtime (sklearn bloqueado).
  2. setup_logging -> archivo DEBUG + consola en WARNING (la demo imprime por
     print(); el detalle completo queda en el archivo).
  3. Lectura del CSV en MODO SOLO LECTURA: nunca se escribe en data/.
     Anti-sabotaje MRM: se registra os.stat(csv).st_mtime al inicio y al
     final; si cambio durante la corrida -> RuntimeError.
  4. Target explicito (--target, default "default"), exigencia binaria.
  5. Inferencia de tipos de predictor (heuristica documentada):
         dtype no numerico             -> NOMINAL
         numerico, n_distinct <= 20    -> ORDINAL
         numerico, n_distinct >  20    -> CONTINUOUS   (MAX_ORDINAL_CATS=20)
     Nota MRM: edad (48 valores) -> CONTINUOUS es decision deliberada (la
     variable se trata como continua para umbrales/QDA).
  6. Split train/test estratificado (Hamilton-Hare / largest remainder,
     semilla fija).
  7. TrainOnlyImputer: fit SOLO en train; transform solo en train (la
     particion test queda reservada para validacion OOS de la Fase 1; nunca
     se toca en esta demo).
  8. Demo de los 4 motores sobre train:
       CHAID y CHAID_EXHAUSTIVE reciben el spec SIN predictores CONTINUOUS
       (el motor los rechaza por contrato; el orquestador filtra y lo
       declara en el log). CRT y QUEST reciben el spec completo.
  9. Reporte final en consola (ASCII) + exit code de 3 estados:
       >=1 split valido            -> 0
       0 splits pero sin excepcion -> 0 + WARNING al log (pipeline sano,
                                      senal debil: revisable)
       >=1 excepcion               -> 1

Uso:
    .venv\\Scripts\\python treegov.py
    .venv\\Scripts\\python treegov.py --csv data/credit_risk_dataset.csv --seed 42
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# ORDEN CRITICO: la guardia se instala ANTES de importar el resto del backend.
from backend_v3.import_guard import install_import_guard, is_installed

install_import_guard()

import numpy as np
import pandas as pd

from backend_v3.chaid_engine import ChaidEngine
from backend_v3.crt_engine import CrtEngine
from backend_v3.imputation import TrainOnlyImputer
from backend_v3.log_config import get_logger, setup_logging
from backend_v3.profiling import infer_spec
from backend_v3.quest_engine import QuestEngine
from backend_v3.splitting import stratified_split
from backend_v3.types import PredictorType, SplitConfig, TargetType

DEFAULT_CSV = os.path.join("data", "credit_risk_dataset.csv")
DEFAULT_TARGET = "default"
DEFAULT_TRAIN_FRAC = 0.7
DEFAULT_SEED = 42


@dataclass(frozen=True)
class EngineReport:
    motor: str
    cfg: SplitConfig | None
    seconds: float
    veredicto: str  # "OK" | "SIN_SPLIT" | "FALLO(<tipo>)"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="treegov", description="Demo headless TreeGov Fase 0"
    )
    p.add_argument("--csv", default=DEFAULT_CSV)
    p.add_argument("--target", default=DEFAULT_TARGET)
    p.add_argument("--train-frac", type=float, default=DEFAULT_TRAIN_FRAC)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return p.parse_args(argv)


def verify_guard_runtime(log: logging.Logger) -> None:
    """Evidencia en runtime de que la caja blanca esta activa."""
    if not is_installed():
        raise RuntimeError("[treegov] import_guard no esta instalado")
    try:
        importlib.import_module("sklearn")
    except ImportError:
        log.info("[treegov] import_guard verificado: sklearn bloqueado OK")
        return
    raise RuntimeError("[treegov] import_guard ineficaz: sklearn importable")


def load_dataset(csv_path: str, log: logging.Logger) -> pd.DataFrame:
    """Lectura en modo solo lectura (nunca escribe en data/)."""
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"[treegov] dataset inexistente: {csv_path}")
    df = pd.read_csv(csv_path)
    if df.shape[0] == 0 or df.shape[1] == 0:
        raise ValueError(
            f"[treegov] dataset vacio: shape={df.shape}"
        )
    log.info("[treegov] dataset cargado: %s (%d filas x %d cols)",
             csv_path, df.shape[0], df.shape[1])
    return df


def run_engines(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    spec: dict[str, PredictorType],
    log: logging.Logger,
) -> list[EngineReport]:
    """Ejecuta los 4 motores sobre train; nunca propaga excepciones."""
    spec_chaid = {k: v for k, v in spec.items() if v != PredictorType.CONTINUOUS}
    log.info(
        "[treegov] CHAID: %d/%d predictores evaluados (%d CONTINUOUS excluidos "
        "por contrato del motor)",
        len(spec_chaid), len(spec), len(spec) - len(spec_chaid),
    )
    motores = [
        ("CHAID", ChaidEngine(logger=get_logger("chaid")), spec_chaid),
        ("CHAID_EXHAUSTIVE", ChaidEngine(exhaustive=True, logger=get_logger("chaid")),
         spec_chaid),
        ("CRT", CrtEngine(logger=get_logger("crt")), spec),
        ("QUEST", QuestEngine(logger=get_logger("quest")), spec),
    ]
    reportes: list[EngineReport] = []
    for nombre, eng, sp in motores:
        t0 = time.perf_counter()
        try:
            cfg = eng.best_split(
                X_train, y_train, sp, target_type=TargetType.BINARY
            )
        except Exception as e:  # noqa: BLE001 - la demo agota y reporta
            dt = time.perf_counter() - t0
            log.exception("[treegov] %s FALLO", nombre)
            reportes.append(EngineReport(nombre, None, dt, f"FALLO({type(e).__name__})"))
            continue
        dt = time.perf_counter() - t0
        verd = "OK" if cfg is not None else "SIN_SPLIT"
        reportes.append(EngineReport(nombre, cfg, dt, verd))
        log.info("[treegov] %s -> %s en %.4fs", nombre, verd, dt)
    return reportes


def _fmt_cfg(cfg: SplitConfig | None) -> tuple[str, str, str]:
    if cfg is None:
        return "-", "-", "-"
    stat = f"{cfg.statistic_name}={cfg.statistic:.6g}"
    if cfg.p_value_adjusted is not None:
        tercero = f"p_adj={cfg.p_value_adjusted:.4g}"
    else:
        tercero = f"dI={cfg.impurity_gain:.4g}"
    return cfg.predictor, stat, tercero


def print_report(
    reportes: list[EngineReport],
    surr_line: str | None,
    meta: dict,
) -> None:
    """Reporte final en consola (ASCII puro)."""
    print("\n================ TreeGov Fase 0 - demo headless ================")
    print(f"Dataset : {meta['csv']} | {meta['n']} filas x {meta['cols']} cols "
          f"| solo lectura (mtime verificado)")
    print(f"Target  : {meta['target']} (binario; k={meta['eventos']} eventos, "
          f"tasa={meta['tasa']:.2f}%)")
    print(f"Spec    : {meta['n_pred']} predictores "
          f"[continuous={meta['n_cont']}, ordinal={meta['n_ord']}, "
          f"nominal={meta['n_nom']}]")
    print(f"Split   : train={meta['n_train']} / test={meta['n_test']} "
          f"(estratificado, seed={meta['seed']}, Hamilton-Hare)")
    print("Imputer : fit SOLO train | test reservado para OOS (Fase 1)")
    print("Guardia : import_guard ACTIVO (verificado en runtime)")
    print(f"Nota    : CHAID recibio {meta['n_chaid']}/{meta['n_pred']} predictores "
          f"({meta['n_pred'] - meta['n_chaid']} CONTINUOUS excluidos por contrato)")
    print()
    print(f"{'Motor':<18} {'Ganador':<22} {'Estadistico':<18} {'p_adj / dI':<14} s")
    print("-" * 76)
    for rep in reportes:
        pred, stat, ter = _fmt_cfg(rep.cfg)
        print(f"{rep.motor:<18} {pred:<22} {stat:<18} {ter:<14} {rep.seconds:.3f}")
        if rep.motor == "CRT" and surr_line:
            print(f"  Surrogates:{surr_line}")
    print("-" * 76)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = Path("logs") / f"opencode_debug_{ts}.log"
    log = setup_logging(str(log_path))
    for h in log.handlers:  # consola menos verbosa; el archivo queda DEBUG
        if isinstance(h, logging.StreamHandler) and not isinstance(
            h, logging.FileHandler
        ):
            h.setLevel(logging.WARNING)
    log.info("[treegov] arranque Fase 0 | args=%s", vars(args))

    csv_abs = os.path.abspath(args.csv)
    try:
        verify_guard_runtime(log)
        mtime_0 = os.stat(csv_abs).st_mtime if os.path.isfile(csv_abs) else None

        df = load_dataset(csv_abs, log)

        # target explicito y binario
        y = df[args.target]
        uniq = sorted(pd.unique(y.dropna()))
        if len(uniq) != 2:
            raise ValueError(
                f"[treegov] target {args.target!r} no binario: {len(uniq)} clases"
            )

        spec = infer_spec(df, args.target, log)
        idx_tr, idx_te = stratified_split(y, args.train_frac, args.seed, log)

        X = df[[c for c in df.columns if c != args.target]]
        X_train = X.iloc[idx_tr].reset_index(drop=True)
        y_train = y.iloc[idx_tr].reset_index(drop=True)

        imp = TrainOnlyImputer(logger=get_logger("imputation"))
        imp.fit(X_train, spec)              # SOLO train
        X_train_i = imp.transform(X_train)
        # TODO Fase 1 (OOS): X_test_i = imp.transform(X_test)

        reportes = run_engines(X_train_i, y_train, spec, log)

        # surrogates de CRT (si hay primario)
        surr_line: str | None = None
        crt_rep = next(r for r in reportes if r.motor == "CRT")
        if crt_rep.cfg is not None:
            surr = CrtEngine(logger=get_logger("crt")).surrogate_splits(
                crt_rep.cfg, X_train, y_train, spec, target_type=TargetType.BINARY
            )
            if surr:
                surr_line = " " + ", ".join(
                    f"{s.split.predictor} (agreement={s.agreement:.2f})"
                    for s in surr
                )
                log.info("[treegov] surrogates CRT: %d aceptados", len(surr))

        meta = {
            "csv": args.csv, "n": df.shape[0], "cols": df.shape[1],
            "target": args.target,
            "eventos": int((pd.Series(y).map({uniq[0]: 0, uniq[1]: 1})).sum()),
            "tasa": 100.0 * float((y == uniq[1]).mean()),
            "n_pred": len(spec),
            "n_chaid": sum(v != PredictorType.CONTINUOUS for v in spec.values()),
            "n_cont": sum(v == PredictorType.CONTINUOUS for v in spec.values()),
            "n_ord": sum(v == PredictorType.ORDINAL for v in spec.values()),
            "n_nom": sum(v == PredictorType.NOMINAL for v in spec.values()),
            "n_train": len(idx_tr), "n_test": len(idx_te), "seed": args.seed,
        }
        # verificacion mtime ANTES del reporte: si data/ fue modificado durante
        # la corrida, el usuario jamas ve un reporte potencialmente invalido
        if mtime_0 is not None and os.stat(csv_abs).st_mtime != mtime_0:
            raise RuntimeError("[treegov] data/ modificado durante la ejecucion")
        print_report(reportes, surr_line, meta)

        fallos = [r for r in reportes if r.veredicto.startswith("FALLO")]
        splits = [r for r in reportes if r.cfg is not None]
        if fallos:
            print(f"VEREDICTO: {len(fallos)} excepcion(es). exit=1")
            return 1
        if not splits:
            log.warning(
                "[treegov] Fase 0 ejecutada correctamente pero ningun motor "
                "encontro split. Verifique el dataset o el spec."
            )
            print("VEREDICTO: sin splits (sin excepciones; WARNING al log). exit=0")
            return 0
        print(f"VEREDICTO: {len(splits)}/4 motores con split valido. exit=0")
        log.info("[treegov] cierre OK: %d/4 splits", len(splits))
        return 0
    except Exception as e:  # noqa: BLE001 - top level: reporta y sale 1
        log.exception("[treegov] abortado: %s", e)
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
