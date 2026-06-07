from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv
from zoneinfo import ZoneInfo


load_dotenv()


class ConfigurationError(RuntimeError):
    pass


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value


def _optional_env(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def _optional_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"Environment variable {name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    bot_token: str
    gemini_api_key: str
    gemini_model: str
    app_timezone: str
    log_level: str
    log_file: str
    scheduler_interval_seconds: int
    scheduler_claim_timeout_seconds: int
    scheduler_retry_delay_seconds: int

    @property
    def timezone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.app_timezone)
        except Exception as exc:
            raise ConfigurationError(
                f"Invalid APP_TIMEZONE value: {self.app_timezone}"
            ) from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        bot_token=_required_env("BOT_TOKEN"),
        gemini_api_key=_required_env("GEMINI_API_KEY"),
        gemini_model=_optional_env("GEMINI_MODEL", "gemini-2.0-flash"),
        app_timezone=_optional_env("APP_TIMEZONE", "Asia/Tehran"),
        log_level=_optional_env("LOG_LEVEL", "INFO"),
        log_file=_optional_env("LOG_FILE", "logs/task_manager.log"),
        scheduler_interval_seconds=_optional_int_env("SCHEDULER_INTERVAL_SECONDS", 15),
        scheduler_claim_timeout_seconds=_optional_int_env(
            "SCHEDULER_CLAIM_TIMEOUT_SECONDS",
            300,
        ),
        scheduler_retry_delay_seconds=_optional_int_env(
            "SCHEDULER_RETRY_DELAY_SECONDS",
            60,
        ),
    )
