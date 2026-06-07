from sqlalchemy import Column, Integer, String, DateTime, Boolean
from db import Base
import datetime

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    title = Column(String)
    due_time = Column(DateTime)
    is_done = Column(Boolean, default=False)
    notified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)