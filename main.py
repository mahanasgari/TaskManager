from __future__ import annotations

import logging
import sys

from app.bot import run_bot
from app.config import ConfigurationError, get_settings
from app.db import initialize_database
from app.logging_utils import setup_logging


def main() -> None:
    try:
        settings = get_settings()
        _ = settings.timezone
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    setup_logging(settings.log_level, settings.log_file)
    logger = logging.getLogger(__name__)
    logger.info(
        "Starting — model=%s tz=%s interval=%ss claim_timeout=%ss retry_delay=%ss",
        settings.openrouter_model,
        settings.app_timezone,
        settings.scheduler_interval_seconds,
        settings.scheduler_claim_timeout_seconds,
        settings.scheduler_retry_delay_seconds,
    )
    initialize_database()
    logger.info("Database ready")
    run_bot(settings)


if __name__ == "__main__":
    main()
