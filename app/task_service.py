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

    def list_tasks(self, user_id: int):
        return self.repository.list_user_tasks(user_id)

    def mark_done(self, user_id: int, task_id: int):
        return self.repository.mark_done(user_id, task_id, now_utc_naive())

    def delete_task(self, user_id: int, task_id: int) -> bool:
        return self.repository.delete_task(user_id, task_id)

    def format_due_datetime(self, due_at_utc, timezone_name: str | None = None) -> str:
        return format_local_datetime(due_at_utc, timezone_name or self.settings.app_timezone)
