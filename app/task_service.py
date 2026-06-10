from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.task_parser import ParsedTask, TaskParser
from app.task_repository import TaskRepository
from app.time_utils import format_local_datetime, now_utc_naive


@dataclass(frozen=True)
class CreatedTask:
    task: object
    parsed: ParsedTask


@dataclass(frozen=True)
class UpdatedTask:
    task: object
    parsed: ParsedTask


class TaskService:
    def __init__(
        self,
        settings: Settings,
        repository: TaskRepository | None = None,
        parser: TaskParser | None = None,
    ):
        self.settings = settings
        self.repository = repository or TaskRepository()
        self.parser = parser or TaskParser(settings)

    async def create_task(self, user_id: int, text: str) -> CreatedTask:
        parsed = await self.parser.parse(text)
        now = now_utc_naive()
        task = self.repository.create_task(
            user_id=user_id,
            title=parsed.title,
            source_text=text,
            due_at_utc=parsed.due_at_utc,
            timezone_name=self.settings.app_timezone,
            now_utc=now,
        )
        return CreatedTask(task=task, parsed=parsed)

    def get_task(self, user_id: int, task_id: int):
        return self.repository.get_user_task(user_id, task_id)

    async def update_task(
        self,
        user_id: int,
        task_id: int,
        text: str,
        *,
        update_title: bool = True,
        update_time: bool = True,
    ) -> UpdatedTask | None:
        task = self.repository.get_user_task(user_id, task_id)
        if task is None:
            return None

        parsed = await self.parser.parse(text)

        updated = self.repository.update_task(
            user_id=user_id,
            task_id=task_id,
            title=parsed.title if update_title else None,
            due_at_utc=parsed.due_at_utc if update_time else None,
            source_text=text if (update_title and update_time) else None,
        )
        if updated is None:
            return None
        return UpdatedTask(task=updated, parsed=parsed)

    def list_tasks(self, user_id: int):
        return self.repository.list_user_tasks(user_id)

    def mark_done(self, user_id: int, task_id: int):
        return self.repository.mark_done(user_id, task_id, now_utc_naive())

    def delete_task(self, user_id: int, task_id: int) -> bool:
        return self.repository.delete_task(user_id, task_id)

    def format_due_datetime(self, due_at_utc, timezone_name: str | None = None) -> str:
        return format_local_datetime(due_at_utc, timezone_name or self.settings.app_timezone)
