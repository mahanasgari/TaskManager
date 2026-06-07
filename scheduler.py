from __future__ import annotations

import asyncio
import logging

from telegram import Bot

from config import Settings
from task_repository import TaskRepository
from time_utils import format_local_datetime, now_utc_naive


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

        due_tasks = self._repository.claim_due_tasks(now)
        for task in due_tasks:
            await self._notify_task(bot, task)

    async def _notify_task(self, bot: Bot, task) -> None:
        display_timezone = task.timezone or self._settings.app_timezone
        due_text = format_local_datetime(task.due_at_utc, display_timezone)
        message = (
            "⏰ یادآوری\n\n"
            f"📝 {task.title}\n"
            f"⏳ {due_text}\n"
            f"🆔 #{task.id}"
        )

        try:
            await bot.send_message(chat_id=task.user_id, text=message)
            self._repository.mark_sent(task.id, now_utc_naive())
            logger.info("Notified task %s for user %s", task.id, task.user_id)
        except Exception as exc:
            logger.exception("Failed to notify task %s", task.id)
            self._repository.mark_failed(
                task.id,
                now_utc_naive(),
                str(exc),
                self._settings.scheduler_retry_delay_seconds,
            )
