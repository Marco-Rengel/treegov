"""Cálculo simplificado de pérdidas crediticias esperadas (Fase 7).

Referencia normativa base: IFRS Foundation, *IFRS 9 — Financial
Instruments*, Sección 5.5 (Impairment). El producto PD × LGD × EAD, las
reglas de staging y el descuento de un periodo son convenciones explícitas de
TreeGov para esta primera versión; no constituyen un motor IFRS 9 completo.

Fórmulas de TreeGov (IFRS 9, Sección 5.5, como marco conceptual):
    ECL_12m = PD_12m × LGD × EAD
    ECL_lifetime = PD_lifetime × LGD × EAD
    factor_descuento = 1 / (1 + EIR), si EIR está configurado

La PD corriente se recibe ya calculada y sin aplicar ningún piso en este
módulo. Su calibración externa es responsabilidad del usuario.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = ["ECLConfig", "ECLRow", "ECLSummary", "calculate_ecl"]

_REQUIRED_COLUMNS = (
    "exposure_id",
    "ead",
    "lgd",
    "days_past_due",
    "pd_initial",
)


@dataclass(frozen=True)
class ECLConfig:
    """Configuración inmutable del cálculo ECL simplificado."""

    eir: float | None = None

    def __post_init__(self) -> None:
        """Exige un EIR finito con denominador de descuento positivo."""
        if self.eir is None:
            return
        try:
            eir = float(self.eir)
        except (TypeError, ValueError) as exc:
            raise ValueError("[ecl] eir debe ser un número finito o None") from exc
        if not math.isfinite(eir) or eir <= -1.0:
            raise ValueError("[ecl] eir debe ser finito y estrictamente mayor que -1")


@dataclass(frozen=True)
class ECLRow:
    """Resultado ECL inmutable de una exposición."""

    exposure_id: str
    stage: int
    pd_12m: float
    pd_lifetime: float
    lgd: float
    ead: float
    ecl_12m: float
    ecl_lifetime: float


@dataclass(frozen=True)
class ECLSummary:
    """Totales ECL y conteos en orden Etapa 1, Etapa 2 y Etapa 3."""

    total_ecl_12m: float
    total_ecl_lifetime: float
    stage_counts: tuple[int, int, int]


def _numeric_column(df: pd.DataFrame, column: str) -> np.ndarray:
    """Convierte una columna a float y exige valores numéricos finitos."""
    try:
        numeric = pd.to_numeric(df[column], errors="raise")
        values = numeric.to_numpy(dtype=float, na_value=float("nan"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"[ecl] columna {column!r} debe ser numérica") from exc
    if not np.isfinite(values).all():
        raise ValueError(
            f"[ecl] columna {column!r} contiene ausentes o valores no finitos"
        )
    return values


def _validate_probability(values: np.ndarray, column: str) -> None:
    """Valida el dominio cerrado [0, 1] de una probabilidad."""
    if ((values < 0.0) | (values > 1.0)).any():
        raise ValueError(f"[ecl] columna {column!r} debe estar en [0, 1]")


def _default_flags(df: pd.DataFrame) -> np.ndarray:
    """Lee flags booleanos o 0/1; una columna ausente equivale a False."""
    if "is_default" not in df.columns:
        return np.zeros(len(df), dtype=bool)

    flags: list[bool] = []
    for value in df["is_default"].tolist():
        if pd.isna(value):
            raise ValueError("[ecl] is_default no admite valores ausentes")
        if isinstance(value, (bool, np.bool_)):
            flags.append(bool(value))
        elif isinstance(value, (int, float, np.integer, np.floating)) and float(
            value
        ) in (0.0, 1.0):
            flags.append(bool(value))
        else:
            raise ValueError("[ecl] is_default debe contener booleanos o valores 0/1")
    return np.asarray(flags, dtype=bool)


def calculate_ecl(
    df: pd.DataFrame, pd_column: str, config: ECLConfig
) -> tuple[ECLSummary, list[ECLRow]]:
    """Calcula ECL por exposición y totales bajo el contrato de Fase 7.

    Etapa 3: ``days_past_due > 90`` o ``is_default``. Etapa 2:
    ``days_past_due > 30`` o ``pd_current > 2 * pd_initial``. En otro caso,
    Etapa 1. Si falta ``pd_lifetime``, reutiliza la PD a 12 meses con un
    ``UserWarning``. El DataFrame de entrada no se modifica.

    Referencia: IFRS 9, Sección 5.5. El factor opcional ``1 / (1 + eir)``
    es una simplificación de descuento de un periodo adoptada por TreeGov.
    """
    required = tuple(dict.fromkeys((*_REQUIRED_COLUMNS, pd_column)))
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"[ecl] columnas requeridas ausentes: {missing}")
    if df["exposure_id"].isna().any():
        raise ValueError("[ecl] exposure_id no admite valores ausentes")

    ead = _numeric_column(df, "ead")
    lgd = _numeric_column(df, "lgd")
    days_past_due = _numeric_column(df, "days_past_due")
    pd_initial = _numeric_column(df, "pd_initial")
    pd_12m = _numeric_column(df, pd_column)

    if (ead < 0.0).any():
        raise ValueError("[ecl] ead debe ser mayor o igual que 0")
    if ((lgd < 0.0) | (lgd > 1.0)).any():
        raise ValueError("[ecl] lgd debe estar en [0, 1]")
    if (days_past_due < 0.0).any():
        raise ValueError("[ecl] days_past_due debe ser mayor o igual que 0")
    _validate_probability(pd_initial, "pd_initial")
    _validate_probability(pd_12m, pd_column)

    if "pd_lifetime" in df.columns:
        pd_lifetime = _numeric_column(df, "pd_lifetime")
        _validate_probability(pd_lifetime, "pd_lifetime")
    else:
        warnings.warn(
            "[ecl] pd_lifetime no está presente; se utiliza pd_12m como "
            "aproximación de vida",
            UserWarning,
            stacklevel=2,
        )
        pd_lifetime = pd_12m.copy()

    is_default = _default_flags(df)
    discount_factor = (
        1.0 if config.eir is None else 1.0 / (1.0 + float(config.eir))
    )

    rows: list[ECLRow] = []
    stage_counts = [0, 0, 0]
    for index, exposure_id in enumerate(df["exposure_id"].tolist()):
        if is_default[index] or days_past_due[index] > 90.0:
            stage = 3
        elif (
            days_past_due[index] > 30.0
            or pd_12m[index] > 2.0 * pd_initial[index]
        ):
            stage = 2
        else:
            stage = 1
        stage_counts[stage - 1] += 1

        row_lgd = float(lgd[index])
        row_ead = float(ead[index])
        row_pd_12m = float(pd_12m[index])
        row_pd_lifetime = float(pd_lifetime[index])
        rows.append(
            ECLRow(
                exposure_id=str(exposure_id),
                stage=stage,
                pd_12m=row_pd_12m,
                pd_lifetime=row_pd_lifetime,
                lgd=row_lgd,
                ead=row_ead,
                ecl_12m=row_pd_12m * row_lgd * row_ead * discount_factor,
                ecl_lifetime=(
                    row_pd_lifetime * row_lgd * row_ead * discount_factor
                ),
            )
        )

    summary = ECLSummary(
        total_ecl_12m=float(math.fsum(row.ecl_12m for row in rows)),
        total_ecl_lifetime=float(math.fsum(row.ecl_lifetime for row in rows)),
        stage_counts=(stage_counts[0], stage_counts[1], stage_counts[2]),
    )
    return summary, rows
