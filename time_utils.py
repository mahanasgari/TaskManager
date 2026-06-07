from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def get_zoneinfo(timezone_name: str) -> ZoneInfo:
    return ZoneInfo(timezone_name)


def now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(value: datetime, timezone_name: str) -> datetime:
    zone = get_zoneinfo(timezone_name)
    if value.tzinfo is None:
        localized = value.replace(tzinfo=zone)
    else:
        localized = value.astimezone(zone)
    return localized.astimezone(timezone.utc).replace(tzinfo=None)


def utc_naive_to_local(value: datetime, timezone_name: str) -> datetime:
    zone = get_zoneinfo(timezone_name)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(zone)


def format_local_datetime(value: datetime, timezone_name: str) -> str:
    return utc_naive_to_local(value, timezone_name).strftime("%Y-%m-%d %H:%M")
