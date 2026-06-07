from __future__ import annotations

import datetime as dt

from sqlalchemy import Column, DateTime, Integer, String, Text

from db import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    source_text = Column(Text, nullable=False, default="")
    due_at_utc = Column(DateTime, nullable=False, index=True)
    timezone = Column(String(64), nullable=False, default="Asia/Tehran")
    status = Column(String(20), nullable=False, default="pending", index=True)
    next_attempt_at_utc = Column(DateTime, nullable=False, index=True)
    claimed_at_utc = Column(DateTime, nullable=True)
    sent_at_utc = Column(DateTime, nullable=True)
    completed_at_utc = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at_utc = Column(DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at_utc = Column(
        DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )
