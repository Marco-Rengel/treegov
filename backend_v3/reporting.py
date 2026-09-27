"""Fase 2.3.d: DTO plano OOS/OOT para el frontend. Sin lógica, sin Qt."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # solo type-checkers; en runtime no se importa session_state
    from .session_state import SessionState

__all__ = ["build_oos_oot_report"]


def build_oos_oot_report(st: SessionState) -> dict[str, Any] | None:
    """Devuelve None si no hay modelo; si no, DTO con claves 'oos'/'oot' (None o asdict)."""
    if st.tree is None:
        return None
    return {
        "oos": None if st.oos_metrics is None else asdict(st.oos_metrics),
        "oot": None if st.oot_report is None else asdict(st.oot_report),
    }
