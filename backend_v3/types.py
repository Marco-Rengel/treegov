"""Contrato comun entre motores de particion (DecisionTree_Modeler, Fase 0).

Lenguaje compartido de backend_v3 (y futuro frontend_v3): enums de dominio y
el dataclass inmutable SplitConfig, evidencia auditable (MRM) de cada particion
candidata emitida por CHAID / CHAID Exhaustivo / C&RT / QUEST.

Pureza: SOLO stdlib. Prohibido numpy/pandas/scipy/PySide6 aqui dentro.
"""

from __future__ import annotations

import math
from collections.abc import Hashable
from dataclasses import dataclass
from enum import Enum, auto
from numbers import Integral, Real
from typing import Literal

__all__ = [
    "TargetType",
    "PredictorType",
    "CutKind",
    "MethodName",
    "StatisticName",
    "SplitConfig",
    "GovernanceMode",
]


class TargetType(Enum):
    """Naturaleza de la variable objetivo."""

    BINARY = auto()       # dos clases (p. ej. default 0/1)
    CATEGORICAL = auto()  # 3+ clases sin continuidad
    CONTINUOUS = auto()   # numerica (F-test en CHAID, varianza en C&RT)


class PredictorType(Enum):
    """Naturaleza del predictor; fija la regla de fusion y el multiplicador de Kass."""

    CONTINUOUS = auto()  # numerico -> busqueda de umbral (C&RT/QUEST)
    ORDINAL = auto()     # orden intrinseco: fusiones solo entre adyacentes; Kass = C(c-1, r-1)
    NOMINAL = auto()     # sin orden: cualquier par fusionable; Kass = S(c, r) Stirling 2da especie


class CutKind(Enum):
    """Forma geometrica del corte (derivado, no rol: 'surrogate' no es un kind)."""

    THRESHOLD = auto()        # continuo: x <= t / x > t
    CATEGORY_GROUPS = auto()  # categorico: pertenencia a rama por grupos de categorias


class GovernanceMode(Enum):
    """Modo de gobernanza de la PD por hoja (TreeGov, Fase 2.1).

    BANKING (defecto): estimador de Jeffreys + PD Floor (BCBS CRE 32.4);
        capa MRM/IFRS 9 para modelos bancarios.
    RESEARCH: PD empirica cruda (k/n), sin suavizado bayesiano ni floor,
        para dominios no bancarios (salud, ciencias sociales, marketing)
        donde la restriccion regulatoria no aplica.
    """

    BANKING = auto()
    RESEARCH = auto()


MethodName = Literal["CHAID", "CHAID_EXHAUSTIVE", "CRT", "QUEST"]
_ALLOWED_METHODS: frozenset[str] = frozenset({"CHAID", "CHAID_EXHAUSTIVE", "CRT", "QUEST"})

StatisticName = Literal["chi2", "f", "gini_gain", "variance_gain"]
# nº de grados de libertad esperado por estadistico: chi2 -> (gl,); F -> (df1, df2);
# ganancias de impureza -> () (no hay gl)
_DF_LEN: dict[str, int] = {"chi2": 1, "f": 2, "gini_gain": 0, "variance_gain": 0}

_EPS: float = 1e-12


def _fmt(x: float) -> str:
    """Formato compacto para el repr de auditoria."""
    return format(x, ".6g")


@dataclass(frozen=True, repr=False)
class SplitConfig:
    """Particion candidata sobre UN predictor, en UN nodo. Inmutable y hashable.

    Invariantes verificados en __post_init__ (solo lee y lanza; nunca asigna):
      - exactamente uno de threshold / branches esta definido;
      - coherencia metodo <-> statistic_name <-> campos estadisticos;
      - branches = particion real (grupos no vacios, categorias hashables y disjuntas);
      - len(child_ns) == nº de ramas; sum(child_ns) <= parent_n.
    """

    predictor: str
    method: MethodName
    statistic: float
    statistic_name: StatisticName
    df: tuple[int, ...]
    parent_n: int
    child_ns: tuple[int, ...]
    p_value: float | None = None
    p_value_adjusted: float | None = None
    bonferroni_multiplier: int | None = None
    n_merges: int | None = None
    threshold: float | None = None
    branches: tuple[tuple[Hashable, ...], ...] | None = None
    impurity_gain: float | None = None
    # Fase 3.10.b (H14): cortes del binning automatico de predictores
    # continuos en CHAID (deciles). () = split categorico clasico.
    bin_edges: tuple[float, ...] = ()

    # ---------------- validaciones estructurales ----------------

    def __post_init__(self) -> None:
        r = self._require

        r(self.method in _ALLOWED_METHODS,
          f"method desconocido: {self.method!r} (validos: {sorted(_ALLOWED_METHODS)})")
        r(self.statistic_name in _DF_LEN,
          f"statistic_name desconocido: {self.statistic_name!r}")

        head = f"[{self.method}|{self.predictor!r}]"

        if isinstance(self.method, str) and self.method.startswith("CHAID"):
            r(self.statistic_name in ("chi2", "f"),
              f"{head} CHAID usa chi2 o f, no {self.statistic_name!r}")
            r(self.p_value is not None, f"{head} CHAID exige p_value")
            r(self.p_value_adjusted is not None, f"{head} CHAID exige p_value_adjusted")
            r(self.bonferroni_multiplier is not None, f"{head} CHAID exige bonferroni_multiplier")
            r(self.n_merges is not None, f"{head} CHAID exige n_merges")
            r(self.impurity_gain is None, f"{head} CHAID no puede llevar impurity_gain")
            r(self.threshold is None, f"{head} CHAID corta por grupos, no por threshold")
            r(self.branches is not None, f"{head} CHAID exige branches")
        elif self.method == "CRT":
            r(self.statistic_name in ("gini_gain", "variance_gain"),
              f"{head} CRT usa gini_gain o variance_gain, no {self.statistic_name!r}")
            r(self.impurity_gain is not None, f"{head} CRT exige impurity_gain")
            r(self.p_value is None and self.p_value_adjusted is None,
              f"{head} CRT no admite p-valores")
            r(self.bonferroni_multiplier is None and self.n_merges is None,
              f"{head} CRT no admite campos de fusion/Bonferroni")
        elif self.method == "QUEST":
            r(self.statistic_name in ("chi2", "f"),
              f"{head} QUEST reporta la estadistica de seleccion (chi2 o f)")
            r(self.impurity_gain is None, f"{head} QUEST no usa impurity_gain")

        # --- estadistico y grados de libertad ---
        stat = float(self.statistic)
        r(math.isfinite(stat), f"{head} statistic no finito: {self.statistic!r}")
        r(stat > -_EPS, f"{head} statistic negativo: {stat}")
        r(len(self.df) == _DF_LEN[self.statistic_name],
          f"{head} df={self.df} incompatible con {self.statistic_name} "
          f"(esperados {_DF_LEN[self.statistic_name]} grados de libertad)")
        r(all(isinstance(d, Integral) and d > 0 for d in self.df),
          f"{head} df debe contener enteros > 0: {self.df!r}")

        # --- p-valores y Bonferroni ---
        for nombre, p in (("p_value", self.p_value),
                          ("p_value_adjusted", self.p_value_adjusted)):
            if p is not None:
                pv = float(p)
                r(math.isfinite(pv) and -_EPS <= pv <= 1.0 + _EPS,
                  f"{head} {nombre} fuera de [0, 1]: {p!r}")
        if self.p_value is not None and self.p_value_adjusted is not None:
            r(float(self.p_value_adjusted) >= float(self.p_value) - _EPS,
              f"{head} p_value_adjusted ({self.p_value_adjusted}) < p_value "
              f"({self.p_value}): Bonferroni nunca reduce el p-valor")

        if self.bonferroni_multiplier is not None:
            r(isinstance(self.bonferroni_multiplier, Integral)
              and self.bonferroni_multiplier >= 1,
              f"{head} bonferroni_multiplier debe ser entero >= 1: "
              f"{self.bonferroni_multiplier!r}")
        if self.n_merges is not None:
            r(isinstance(self.n_merges, Integral) and self.n_merges >= 0,
              f"{head} n_merges debe ser entero >= 0: {self.n_merges!r}")
        if self.impurity_gain is not None:
            ig = float(self.impurity_gain)
            r(math.isfinite(ig) and ig > -_EPS,
              f"{head} impurity_gain invalido: {self.impurity_gain!r}")
            if self.statistic_name in ("gini_gain", "variance_gain"):
                r(abs(ig - stat) <= 1e-9,
                  f"{head} impurity_gain ({ig}) debe coincidir con statistic ({stat})")

        # --- forma geometrica: exactamente uno de threshold / branches ---
        r((self.threshold is None) != (self.branches is None),
          f"{head} exactamente uno de threshold/branches debe estar definido "
          f"(threshold={self.threshold!r}, branches={'definido' if self.branches is not None else None})")

        if self.threshold is not None:
            th = float(self.threshold)
            r(math.isfinite(th), f"{head} threshold no finito: {self.threshold!r}")

        if self.branches is not None:
            r(len(self.branches) >= 2,
              f"{head} branches debe tener >= 2 ramas: {len(self.branches)}")
            for i, grupo in enumerate(self.branches):
                r(len(grupo) > 0, f"{head} rama {i} vacia")
                for v in grupo:
                    try:
                        hash(v)
                    except TypeError:
                        raise ValueError(
                            f"{head} categoria no hashable {v!r} en rama {i} "
                            f"(un SplitConfig debe ser hashable)") from None
            cats = [v for g in self.branches for v in g]
            r(len(set(cats)) == len(cats),
              f"{head} categorias duplicadas entre ramas (no es una particion)")

        # --- coherencia de tamanios ---
        r(isinstance(self.parent_n, Integral) and self.parent_n > 0,
          f"{head} parent_n debe ser entero > 0: {self.parent_n!r}")
        r(len(self.child_ns) >= 2, f"{head} child_ns debe tener >= 2 hijos")
        r(all(isinstance(c, Integral) and c > 0 for c in self.child_ns),
          f"{head} child_ns debe contener enteros > 0: {self.child_ns!r}")
        expected_k = len(self.branches) if self.branches is not None else 2
        r(len(self.child_ns) == expected_k,
          f"{head} len(child_ns)={len(self.child_ns)} != nº ramas={expected_k}")
        r(sum(int(c) for c in self.child_ns) <= int(self.parent_n),
          f"{head} sum(child_ns)={sum(self.child_ns)} excede parent_n={self.parent_n}")

        # --- bin_edges: binning automatico de continuas (Fase 3.10.b) ---
        r(isinstance(self.bin_edges, tuple),
          f"{head} bin_edges debe ser tuple: {type(self.bin_edges).__name__!r}")
        es: list[float] = []
        for e in self.bin_edges:
            r(isinstance(e, Real) and not isinstance(e, bool),
              f"{head} bin_edges debe contener reales: {e!r}")
            fe = float(e)
            r(math.isfinite(fe), f"{head} bin_edges no finito: {e!r}")
            es.append(fe)
        r(all(es[i] < es[i + 1] for i in range(len(es) - 1)),
          f"{head} bin_edges debe ser estrictamente creciente: {self.bin_edges!r}")
        if self.bin_edges:
            r(isinstance(self.method, str) and self.method.startswith("CHAID"),
              f"{head} bin_edges solo aplica a CHAID (binning de continuas)")
            r(self.branches is not None,
              f"{head} bin_edges exige branches (routing por rangos)")

    @staticmethod
    def _require(cond: bool, msg: str) -> None:
        if not cond:
            raise ValueError(msg)

    # ---------------- derivados y representacion ----------------

    @property
    def cut_kind(self) -> CutKind:
        """THRESHOLD si hay umbral; CATEGORY_GROUPS si hay grupos de categorias."""
        return CutKind.THRESHOLD if self.threshold is not None else CutKind.CATEGORY_GROUPS

    def __repr__(self) -> str:
        partes: list[str] = [f"SplitConfig[{self.method}] {self.predictor!r}"]
        partes.append(f"{self.statistic_name}={_fmt(float(self.statistic))}")
        if self.df:
            partes.append(f"df={self.df}")
        if self.p_value is not None:
            partes.append(f"p={_fmt(float(self.p_value))}")
        if self.p_value_adjusted is not None:
            partes.append(f"p_adj={_fmt(float(self.p_value_adjusted))}")
        if self.bonferroni_multiplier is not None:
            partes.append(f"M={self.bonferroni_multiplier}")
        if self.n_merges:
            partes.append(f"merges={self.n_merges}")
        if self.threshold is not None:
            partes.append(f"thr={_fmt(float(self.threshold))}")
        if self.branches is not None:
            partes.append(f"groups={len(self.branches)}")
        partes.append(f"n={self.parent_n}")
        partes.append(f"children={self.child_ns}")
        return " ".join(partes)
