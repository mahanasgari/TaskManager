from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_level: str, log_file: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    log_directory = os.path.dirname(log_file)
    if log_directory:
        os.makedirs(log_directory, exist_ok=True)

    handlers = [
        logging.StreamHandler(),
        RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        ),
    ]

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )
