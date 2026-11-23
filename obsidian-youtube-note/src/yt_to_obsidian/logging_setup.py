"""Rotating file and console logging setup for yt-to-obsidian."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    *,
    log_file: Path | None = None,
    level: str = "INFO",
) -> logging.Logger:
    """Configure root logger for `yt_to_obsidian` with console + rotating file output."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger("yt_to_obsidian")
    logger.setLevel(numeric_level)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError as exc:
            logger.warning("Could not initialize file logging at %s: %s", log_file, exc)

    return logger
