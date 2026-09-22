"""Benchmark de rendimiento Fase 0 (TreeGov) - script, NO test de pytest.

Datos sinteticos DETERMINISTAS (np.random.default_rng(seed)) con señal real:

  continuas : x1 fuerte, x2 media, x3 debil, x4/x5 ruido   (logit real)
  ordinales : o1 (1..5, tasa creciente), o2 (1..8, ruido)
  nominales : n1 (K=6, tasas graduadas), n2 (K=3 ruido), n3 (K=12 heuristica)

Fases medidas: generacion, imputacion (fit+transform train-only), y por
motor: evaluacion completa (CHAID clasico+exhaustivo ven excluidos los
CONTINUOUS por contrato; CRT incluye surrogates con el primario).

Objetivo regulatorio: < 1.5 s por predictor y motor.

Uso:
    .venv\\Scripts\\python tests\\benchmark_1m.py --n 1000000 --seed 42
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from backend_v3.import_guard import install_import_guard

install_import_guard()

from backend_v3.chaid_engine import ChaidEngine
from backend_v3.crt_engine import CrtEngine
from backend_v3.imputation import TrainOnlyImputer
from backend_v3.quest_engine import QuestEngine
from backend_v3.types import PredictorType, TargetType

_OBJETIVO_S_POR_EVAL = 1.5


def build_synthetic(n: int, seed: int) -> tuple[pd.DataFrame, pd.Series, dict]:
    rng = np.random.default_rng(seed)
    z = rng.normal(0.0, 1.0, size=(5, n))
    cats6 = np.array([f"g{i}" for i in range(6)], dtype=object)
    cats3 = np.array([f"g{i}" for i in range(3)], dtype=object)
    cats12 = np.array([f"k{i:02d}" for i in range(12)], dtype=object)

    # orden inducido por z1 (tasas crecientes 0.02..0.42) y ruido puro de otros
    o1 = 1 + np.digitize(z[0] + 0.5 * rng.normal(size=n), np.linspace(-2, 2, 4))
    o2 = 1 + np.digitize(rng.normal(size=n), np.linspace(-2.5, 2.5, 7))
    n1 = cats6[np.digitize(z[1] + rng.normal(size=n), np.linspace(-3, 3, 5))]
    n2 = cats3[rng.integers(0, 3, n)]
    n3 = cats12[rng.integers(0, 12, n)]

    logit = (
        1.2 * z[0] + 0.8 * z[1] + 0.35 * z[2]
        + 0.5 * (n1 == "g4").astype(float) + 0.5 * (n1 == "g5").astype(float)
        - 3.0
    )
    p = 1.0 / (1.0 + np.exp(-logit))
    y = (rng.random(n) < p).astype(np.int8)

    X = pd.DataFrame(
        {
            "x1_fuerte": z[0], "x2_media": z[1], "x3_debil": z[2],
            "x4_ruido": z[3], "x5_ruido": z[4],
            "o1": o1, "o2": o2,
            "n1": n1, "n2": n2, "n3": n3,
        }
    )
    spec = {
        "x1_fuerte": PredictorType.CONTINUOUS, "x2_media": PredictorType.CONTINUOUS,
        "x3_debil": PredictorType.CONTINUOUS, "x4_ruido": PredictorType.CONTINUOUS,
        "x5_ruido": PredictorType.CONTINUOUS,
        "o1": PredictorType.ORDINAL, "o2": PredictorType.ORDINAL,
        "n1": PredictorType.NOMINAL, "n2": PredictorType.NOMINAL,
        "n3": PredictorType.NOMINAL,
    }
    return X, pd.Series(y), spec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="benchmark_1m")
    ap.add_argument("--n", type=int, default=1_000_000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    X, y, spec = build_synthetic(args.n, args.seed)
    t_gen = time.perf_counter() - t0

    t0 = time.perf_counter()
    imp = TrainOnlyImputer()
    sp = imp.fit(X, spec)
    X = imp.transform(X)
    t_imp = time.perf_counter() - t0

    spec_chaid = {k: v for k, v in spec.items() if v != PredictorType.CONTINUOUS}
    n_full = len(spec)
    n_chaid = len(spec_chaid)

    resultados: list[tuple[str, float, int, bool]] = []
    eventos: list[str] = []

    # n_eval = nº de barrados de predictor ejecutados: CRT+surrogates hace el
    # barrido del primario (n) + un barrido por cada candidato surrogate (n-1).
    motores = [
        ("CHAID", ChaidEngine(), spec_chaid, n_chaid),
        ("CHAID_EXHAUSTIVE", ChaidEngine(exhaustive=True), spec_chaid, n_chaid),
        ("CRT", CrtEngine(), spec, n_full),
        ("CRT+surrogates", CrtEngine(), spec, 2 * n_full - 1),
        ("QUEST", QuestEngine(), spec, n_full),
    ]
    for nombre, eng, sp_motor, n_pred in motores:
        t0 = time.perf_counter()
        try:
            if nombre == "CRT+surrogates":
                primario = eng.best_split(X, y, sp_motor, target_type=TargetType.BINARY)
                if primario is not None:
                    surr = eng.surrogate_splits(
                        primario, X, y, sp_motor, target_type=TargetType.BINARY
                    )
                    eventos.append(
                        f"CRT surrogates: {len(surr)} aceptados (top: "
                        + (f"{surr[0].split.predictor} agr={surr[0].agreement:.4f}"
                           if surr else "-")
                        + ")"
                    )
                else:
                    eventos.append("CRT surrogates: primario None")
            else:
                cfg = eng.best_split(X, y, sp_motor, target_type=TargetType.BINARY)
                eventos.append(
                    f"{nombre}: ganador={None if cfg is None else cfg.predictor}"
                )
            ok = True
        except Exception as e:  # noqa: BLE001
            eventos.append(f"{nombre}: EXCEPCION {type(e).__name__}: {e}")
            ok = False
        dt = time.perf_counter() - t0
        resultados.append((nombre, dt, n_pred, ok))

    print(f"\nTreeGov benchmark 1M  (N={args.n:,}, seed={args.seed})")
    print(f"fase generacion : {t_gen:8.3f} s")
    print(f"fase imputacion : {t_imp:8.3f} s  (means={len(sp.means)}, modes={len(sp.modes)})")
    print()
    # metrica principal: TIEMPO TOTAL (cada motor ejecuta distinto nº de barridos);
    # s/eval es columna auxiliar (equivale a s/predictor salvo surrogates)
    print(f"{'motor':<18}{'total_s':>10}{'evals':>8}{'s/eval':>10}   estado")
    print("-" * 56)
    todo_ok = True
    for nombre, dt, n_eval, ok in resultados:
        s_eval = dt / n_eval
        dentro = s_eval < _OBJETIVO_S_POR_EVAL
        todo_ok &= ok and dentro
        print(f"{nombre:<18}{dt:>10.3f}{n_eval:>8}{s_eval:>10.3f}   "
              f"{'OK' if (ok and dentro) else ('EXCEDE' if ok else 'FALLO')}")
    print("-" * 56)
    for ev in eventos:
        print("  ", ev)
    print(f"\nObjetivo < {_OBJETIVO_S_POR_EVAL} s/evaluacion "
          f"(= s/predictor salvo surrogates): "
          f"{'CUMPLIDO' if todo_ok else 'INCUMPLIDO'}")
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
