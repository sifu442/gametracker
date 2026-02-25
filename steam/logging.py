from __future__ import annotations

import json
import logging
from typing import Any


def get_logger(name: str = "steam") -> logging.Logger:
    """Return a configured logger."""

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def slog(logger: logging.Logger, level: int, message: str, **context: Any) -> None:
    """Log structured JSON payload."""

    logger.log(level, json.dumps({"message": message, **context}, ensure_ascii=False))

