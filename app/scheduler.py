from __future__ import annotations

import asyncio
import html
import logging

from telegram import Bot
from telegram.error import BadRequest

from app.config import Settings
from app.task_repository import TaskRepository
from app.time_utils import format_local_datetime, now_utc_naive


logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self, settings: Settings, repository: TaskRepository | None = None):
        self._settings = settings
        self._repository = repository or TaskRepository()
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    async def run(self, bot: Bot) -> None:
        logger.info("Task scheduler started")
        try:
            while not self._stop_requested:
                await self._tick(bot)
                await asyncio.sleep(self._settings.scheduler_interval_seconds)
        except asyncio.CancelledError:
            logger.info("Task scheduler cancelled")
            raise
        finally:
            logger.info("Task scheduler stopped")

    async def _tick(self, bot: Bot) -> None:
        now = now_utc_naive()
        recovered = self._repository.recover_stale_processing(
            now,
            self._settings.scheduler_claim_timeout_seconds,
        )
        if recovered:
            logger.warning("Recovered %s stale task claims", recovered)

        exhausted = self._repository.fail_exhausted_tasks(now)
        if exhausted:
            logger.warning("Permanently failed %s tasks (max attempts)", exhausted)

        due_tasks = self._repository.claim_due_tasks(now)
        for task in due_tasks:
            await self._notify_task(bot, task)

    async def _notify_task(self, bot: Bot, task) -> None:
        if not task.pre_reminded:
            await self._send_pre_reminder(bot, task)
        else:
            await self._send_on_time_reminder(bot, task)

    async def _send_pre_reminder(self, bot: Bot, task) -> None:
        now = now_utc_naive()
        display_timezone = task.timezone or self._settings.app_timezone
        due_text = format_local_datetime(task.due_at_utc, display_timezone)
        message = (
            "\U0001f514 \u06cc\u0627\u062f\u0622\u0648\u0631\u06cc \u067e\u06cc\u0634 \u0627\u0632 \u0645\u0648\u0639\u062f\n\n"
            f"\U0001f4dd <b>{html.escape(task.title)}</b>\n"
            f"\u23f3 \u062a\u0627 \u06f1\u06f0 \u062f\u0642\u06cc\u0642\u0647 \u062f\u06cc\u06af\u0631 (\u0645\u0648\u0639\u062f: {due_text})\n"
            f"\U0001f194 #{task.id}"
        )

        try:
            await bot.send_message(chat_id=task.user_id, text=message, parse_mode="HTML")
            self._repository.mark_pre_reminded(task.id, now)
            logger.info("Pre-reminder sent for task %s", task.id)
        except BadRequest as exc:
            if "chat not found" in str(exc).lower():
                logger.warning("Chat not found for user %s — permanently failing task %s", task.user_id, task.id)
                self._repository.mark_sent(task.id, now)
            elif now >= task.due_at_utc:
                self._repository.mark_pre_reminded(task.id, now)
                await self._send_on_time_reminder(bot, task)
            else:
                self._repository.mark_failed(
                    task.id,
                    now,
                    str(exc),
                    self._settings.scheduler_retry_delay_seconds,
                )
        except Exception as exc:
            logger.exception("Failed to send pre-reminder for task %s", task.id)
            if now >= task.due_at_utc:
                self._repository.mark_pre_reminded(task.id, now)
                await self._send_on_time_reminder(bot, task)
            else:
                self._repository.mark_failed(
                    task.id,
                    now,
                    str(exc),
                    self._settings.scheduler_retry_delay_seconds,
                )

    async def _send_on_time_reminder(self, bot: Bot, task) -> None:
        now = now_utc_naive()
        display_timezone = task.timezone or self._settings.app_timezone
        due_text = format_local_datetime(task.due_at_utc, display_timezone)
        message = (
            "\u23f0 \u0632\u0645\u0627\u0646\u0634 \u0631\u0633\u06cc\u062f!\n\n"
            f"\U0001f4dd <b>{html.escape(task.title)}</b>\n"
            f"\u23f3 {due_text}\n"
            f"\U0001f194 #{task.id}"
        )

        try:
            await bot.send_message(chat_id=task.user_id, text=message, parse_mode="HTML")
            self._repository.mark_sent(task.id, now)
            logger.info("Notified task %s for user %s", task.id, task.user_id)
        except BadRequest as exc:
            if "chat not found" in str(exc).lower():
                logger.warning("Chat not found for user %s — permanently failing task %s", task.user_id, task.id)
                self._repository.mark_sent(task.id, now)
            else:
                self._repository.mark_failed(
                    task.id,
                    now,
                    str(exc),
                    self._settings.scheduler_retry_delay_seconds,
                )
        except Exception as exc:
            logger.exception("Failed to notify task %s", task.id)
            self._repository.mark_failed(
                task.id,
                now,
                str(exc),
                self._settings.scheduler_retry_delay_seconds,
            )
