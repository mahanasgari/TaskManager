from __future__ import annotations

import logging
import sys

from bot import run_bot
from config import ConfigurationError, get_settings
from db import initialize_database
from logging_utils import setup_logging


def main() -> None:
    try:
        settings = get_settings()
        _ = settings.timezone
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    setup_logging(settings.log_level, settings.log_file)
    initialize_database()
    logging.getLogger(__name__).info("Database ready")
    run_bot(settings)


if __name__ == "__main__":
    main()
