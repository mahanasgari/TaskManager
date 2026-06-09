from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import dateparser
from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.time_utils import to_utc_naive


logger = logging.getLogger(__name__)

DATE_HINT_PATTERN = re.compile(
    r"(\b(today|tomorrow|tonight|now)\b|"
    r"\b(امروز|فردا|امشب|الان|پس[\s‌-]?فردا)\b|"
    r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b|"
    r"\b\d{1,2}[-/]\d{1,2}([-/]\d{2,4})?\b)",
    re.IGNORECASE,
)
TIME_HINT_PATTERN = re.compile(
    r"(\b\d{1,2}(:\d{2})?\s*(am|pm)?\b|"
    r"\b\d{1,2}[:٫.]\d{2}\b|"
    r"\b(noon|midnight)\b|"
    r"\b(ساعت|صبح|عصر|شب|ظهر|بعدازظهر)\b)",
    re.IGNORECASE,
)


class TaskDraft(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    datetime: str = Field(min_length=1, max_length=32)


@dataclass(frozen=True)
class ParsedTask:
    title: str
    due_at_utc: datetime
    due_at_local: datetime
    source: str


class TaskParser:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": "https://github.com/anoncredi/TaskMan",
                "X-Title": "TaskMan",
            },
        )

    async def parse(self, text: str) -> ParsedTask:
        now_local = datetime.now(self._settings.timezone).replace(microsecond=0)

        try:
            draft = await asyncio.to_thread(self._parse_with_llm, text, now_local)
            return self._build_result(draft.title, draft.datetime, text, now_local, "openrouter")
        except Exception as exc:
            logger.warning("LLM parse failed, using deterministic parser: %s", exc)
            return self._parse_deterministic(text, now_local)

    def _parse_with_llm(self, text: str, now_local: datetime) -> TaskDraft:
        default_due = (now_local + timedelta(days=1)).replace(
            hour=9,
            minute=0,
            second=0,
            microsecond=0,
        )
        system_prompt = (
            "You are a task extraction engine. "
            "Always respond with valid JSON only, no extra text."
        )
        user_prompt = (
            f"Current time: {now_local.strftime('%Y-%m-%d %H:%M (%A)')}\n"
            f'User input: "{text}"\n\n'
            "Return JSON with:\n"
            "- title: short clear task title in the same language as the input\n"
            '- datetime: exact local datetime in "YYYY-MM-DD HH:MM"\n\n'
            "Rules:\n"
            f"- If a time is missing, use {default_due.strftime('%Y-%m-%d %H:%M')}\n"
            "- Do not invent extra meaning\n"
            "- Remove scheduling words from the title"
        )

        response = self._client.chat.completions.create(
            model=self._settings.openrouter_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=256,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned empty response")

        parsed = json.loads(content)
        return TaskDraft.model_validate(parsed)

    def _parse_deterministic(self, text: str, now_local: datetime) -> ParsedTask:
        due_local = self._extract_due_datetime(text, now_local)
        title = self._clean_title(text)
        if not title:
            title = text.strip() or "بدون عنوان"
        return self._finalize(title, due_local, "fallback")

    def _build_result(
        self,
        title: str,
        due_text: str,
        original_text: str,
        now_local: datetime,
        source: str,
    ) -> ParsedTask:
        due_local = self._parse_due_text(due_text, original_text, now_local)
        cleaned_title = self._clean_title(title)
        if not cleaned_title:
            cleaned_title = self._clean_title(original_text) or original_text.strip() or "بدون عنوان"
        return self._finalize(cleaned_title, due_local, source)

    def _finalize(self, title: str, due_local: datetime, source: str) -> ParsedTask:
        aware_local = due_local if due_local.tzinfo else due_local.replace(tzinfo=self._settings.timezone)
        due_at_utc = to_utc_naive(aware_local, self._settings.app_timezone)
        return ParsedTask(
            title=title.strip(),
            due_at_utc=due_at_utc,
            due_at_local=aware_local,
            source=source,
        )

    def _parse_due_text(self, due_text: str, original_text: str, now_local: datetime) -> datetime:
        parsed = datetime.strptime(due_text.strip(), "%Y-%m-%d %H:%M")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self._settings.timezone)
        return parsed

    def _extract_due_datetime(self, text: str, now_local: datetime) -> datetime:
        has_date_hint = bool(DATE_HINT_PATTERN.search(text))
        has_time_hint = bool(TIME_HINT_PATTERN.search(text))
        relative_base = now_local

        parsed = dateparser.parse(
            text,
            languages=["en", "fa"],
            settings={
                "RELATIVE_BASE": relative_base,
                "TIMEZONE": self._settings.app_timezone,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future",
            },
        )

        if parsed is None:
            return self._default_due_datetime(now_local)

        parsed_local = parsed.astimezone(self._settings.timezone)

        if not has_time_hint:
            if has_date_hint:
                parsed_local = parsed_local.replace(
                    hour=9,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            else:
                return self._default_due_datetime(now_local)

        return parsed_local.replace(second=0, microsecond=0)

    def _default_due_datetime(self, now_local: datetime) -> datetime:
        return (now_local + timedelta(days=1)).replace(
            hour=9,
            minute=0,
            second=0,
            microsecond=0,
        )

    def _clean_title(self, text: str) -> str:
        cleaned = text
        cleaned = re.sub(r"\b(remind(?: me)? to|reminder|please|set a reminder)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(یادآوری|یادم\s*بنداز|لطفا|برای|ساعت|امروز|فردا|امشب|الان|صبح|عصر|شب|ظهر)\b", " ", cleaned)
        cleaned = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", " ", cleaned)
        cleaned = re.sub(r"\b\d{1,2}(:\d{2})?\s*(am|pm)?\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b\d{1,2}[:٫.]\d{2}\b", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -—_,،؛:()[]{}")
        return cleaned
