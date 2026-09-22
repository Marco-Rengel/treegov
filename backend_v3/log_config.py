"""Logger transaccional en DEBUG para auditoria MRM (TreeGov, Fase 0).

Un unico logger raiz de proyecto ("treegov") con salida doble:
  - archivo (modo append, UTF-8)  -> trazabilidad persistente
  - consola (stdout)              -> seguimiento en vivo

Formato de linea:
  <ISO 8601> | <LEVELNAME> | <archivo>:<linea> | <mensaje>
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

LOGGER_NAME: str = "treegov"
_DEFAULT_LEVEL: int = logging.DEBUG

_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"


class _IsoFormatter(logging.Formatter):
    """Formatter con timestamp ISO 8601 (zona local, precision de milisegundos)."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created).astimezone()
        return dt.isoformat(timespec="milliseconds")


def setup_logging(log_path: str, level: int = _DEFAULT_LEVEL) -> logging.Logger:
    """Configura el logger raiz "treegov" con handlers de archivo y consola.

    Reconfigurable: si ya existian handlers gestionados, se sustituyen
    (evita lineas duplicadas en llamadas repetidas).
    """
    abs_path = os.path.abspath(log_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False  # aislar del root logger de terceros

    for handler in list(logger.handlers):
        if getattr(handler, "_treegov_managed", False):
            logger.removeHandler(handler)
            handler.close()

    formatter = _IsoFormatter(fmt=_FORMAT)

    file_handler = logging.FileHandler(abs_path, mode="a", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler._treegov_managed = True  # type: ignore[attr-defined]

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler._treegov_managed = True  # type: ignore[attr-defined]

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Devuelve logger hijo 'treegov.<name>' (p. ej. get_logger('chaid') -> 'treegov.chaid')."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
