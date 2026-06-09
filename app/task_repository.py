from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import case

from app.db import SessionLocal
from app.models import Task


logger = logging.getLogger(__name__)


PENDING = "pending"
PROCESSING = "processing"
SENT = "sent"
FAILED = "failed"
DONE = "done"
CLAIMABLE_STATUSES = {PENDING, FAILED}
MAX_ATTEMPTS = 10


class TaskRepository:
    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    def create_task(
        self,
        *,
        user_id: int,
        title: str,
        source_text: str,
        due_at_utc: datetime,
        timezone_name: str,
        now_utc: datetime,
    ) -> Task:
        pre_reminded_at = due_at_utc - timedelta(minutes=10)
        if pre_reminded_at > now_utc:
            pre_reminded = False
            next_attempt = pre_reminded_at
        else:
            pre_reminded = True
            next_attempt = due_at_utc

        with self._session_factory() as session:
            task = Task(
                user_id=user_id,
                title=title,
                source_text=source_text,
                due_at_utc=due_at_utc,
                timezone=timezone_name,
                status=PENDING,
                pre_reminded=pre_reminded,
                next_attempt_at_utc=next_attempt,
                claimed_at_utc=None,
                sent_at_utc=None,
                completed_at_utc=None,
                attempt_count=0,
                last_error=None,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            return task

    def list_user_tasks(self, user_id: int) -> list[Task]:
        with self._session_factory() as session:
            status_rank = case(
                (Task.status == PENDING, 0),
                (Task.status == PROCESSING, 1),
                (Task.status == FAILED, 2),
                (Task.status == SENT, 3),
                (Task.status == DONE, 4),
                else_=5,
            )
            return (
                session.query(Task)
                .filter(Task.user_id == user_id)
                .order_by(status_rank, Task.due_at_utc.asc(), Task.id.asc())
                .all()
            )

    def get_user_task(self, user_id: int, task_id: int) -> Task | None:
        with self._session_factory() as session:
            return (
                session.query(Task)
                .filter(Task.user_id == user_id, Task.id == task_id)
                .one_or_none()
            )

    def mark_done(self, user_id: int, task_id: int, completed_at_utc: datetime) -> Task | None:
        with self._session_factory() as session:
            task = (
                session.query(Task)
                .filter(Task.user_id == user_id, Task.id == task_id)
                .one_or_none()
            )
            if task is None:
                return None

            task.status = DONE
            task.completed_at_utc = completed_at_utc
            task.updated_at_utc = completed_at_utc
            session.commit()
            session.refresh(task)
            return task

    def delete_task(self, user_id: int, task_id: int) -> bool:
        with self._session_factory() as session:
            task = (
                session.query(Task)
                .filter(Task.user_id == user_id, Task.id == task_id)
                .one_or_none()
            )
            if task is None:
                return False

            session.delete(task)
            session.commit()
            return True

    def recover_stale_processing(self, now_utc: datetime, stale_after_seconds: int) -> int:
        stale_cutoff = now_utc - timedelta(seconds=stale_after_seconds)
        with self._session_factory() as session:
            stale_tasks = (
                session.query(Task)
                .filter(
                    Task.status == PROCESSING,
                    Task.claimed_at_utc.isnot(None),
                    Task.claimed_at_utc < stale_cutoff,
                )
                .all()
            )

            for task in stale_tasks:
                task.status = FAILED
                task.claimed_at_utc = None
                task.next_attempt_at_utc = now_utc
                task.last_error = "Recovered stale claim"
                task.updated_at_utc = now_utc

            session.commit()
            return len(stale_tasks)

    def claim_due_tasks(self, now_utc: datetime, limit: int = 25) -> list[Task]:
        with self._session_factory() as session:
            eligible_tasks = (
                session.query(Task)
                .filter(
                    Task.status.in_(CLAIMABLE_STATUSES),
                    Task.next_attempt_at_utc <= now_utc,
                    Task.attempt_count < MAX_ATTEMPTS,
                )
                .order_by(Task.next_attempt_at_utc.asc(), Task.id.asc())
                .limit(limit)
                .all()
            )

            for task in eligible_tasks:
                task.status = PROCESSING
                task.claimed_at_utc = now_utc
                task.updated_at_utc = now_utc
                task.attempt_count += 1

            session.commit()
            return eligible_tasks

    def mark_sent(self, task_id: int, sent_at_utc: datetime) -> Task | None:
        with self._session_factory() as session:
            task = session.query(Task).filter(Task.id == task_id).one_or_none()
            if task is None:
                return None

            task.status = SENT
            task.sent_at_utc = sent_at_utc
            task.claimed_at_utc = None
            task.updated_at_utc = sent_at_utc
            task.last_error = None
            session.commit()
            session.refresh(task)
            return task

    def mark_pre_reminded(self, task_id: int, now_utc: datetime) -> Task | None:
        with self._session_factory() as session:
            task = session.query(Task).filter(Task.id == task_id).one_or_none()
            if task is None:
                return None

            task.pre_reminded = True
            task.claimed_at_utc = None
            task.status = PENDING
            task.next_attempt_at_utc = task.due_at_utc
            task.updated_at_utc = now_utc
            task.last_error = None
            session.commit()
            session.refresh(task)
            return task

    def fail_exhausted_tasks(self, now_utc: datetime) -> int:
        with self._session_factory() as session:
            exhausted = (
                session.query(Task)
                .filter(
                    Task.status.in_(CLAIMABLE_STATUSES),
                    Task.attempt_count >= MAX_ATTEMPTS,
                )
                .all()
            )
            for task in exhausted:
                task.status = FAILED
                task.claimed_at_utc = None
                task.next_attempt_at_utc = task.next_attempt_at_utc
                task.updated_at_utc = now_utc
                task.last_error = "Exceeded max retry attempts"
            session.commit()
            return len(exhausted)

    def mark_failed(
        self,
        task_id: int,
        failed_at_utc: datetime,
        error_message: str,
        retry_delay_seconds: int,
    ) -> Task | None:
        with self._session_factory() as session:
            task = session.query(Task).filter(Task.id == task_id).one_or_none()
            if task is None:
                return None

            task.status = FAILED
            task.claimed_at_utc = None
            task.last_error = error_message[:1000]
            task.updated_at_utc = failed_at_utc
            task.next_attempt_at_utc = failed_at_utc + timedelta(seconds=retry_delay_seconds)
            session.commit()
            session.refresh(task)
            return task
