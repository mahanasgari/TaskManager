from __future__ import annotations

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = "sqlite:///./tasks.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

Base = declarative_base()


def initialize_database(force_recreate: bool = False) -> None:
    from models import Task

    inspector = inspect(engine)

    if force_recreate or "tasks" not in inspector.get_table_names():
        Task.__table__.drop(bind=engine, checkfirst=True)
        Base.metadata.create_all(bind=engine)
        return

    expected_columns = {column.name for column in Task.__table__.columns}
    existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
    if existing_columns != expected_columns:
        Task.__table__.drop(bind=engine, checkfirst=True)
        Base.metadata.create_all(bind=engine)
