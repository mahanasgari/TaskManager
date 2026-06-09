from __future__ import annotations

from app.db import initialize_database


if __name__ == "__main__":
    initialize_database(force_recreate=True)
    print("Database recreated successfully")
