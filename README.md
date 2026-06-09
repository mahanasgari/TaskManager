# Telegram Task Manager Bot

A Telegram bot for creating tasks, scheduling reminders, and keeping your task list easy to manage.

## Features

- Create tasks in Persian or English with natural language dates
- Store reminders safely in SQLite with UTC normalization
- Run a background scheduler that avoids duplicate notifications
- Validate LLM output (via OpenRouter) before it reaches the database
- Manage tasks with `/list`, `/done`, and `/delete`

## Requirements

- Python 3.11+
- A Telegram bot token from [BotFather](https://t.me/BotFather)
- An OpenRouter API key

## Setup

1. Clone the repository.
2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv venv
   .\\venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your values.
4. Run the bot:

   ```bash
   python main.py
   ```

The app will create or refresh `tasks.db` automatically. If the local schema is outdated, it will be rebuilt so the bot can keep running cleanly.

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `BOT_TOKEN` | Yes | Telegram bot token |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key |
| `OPENROUTER_MODEL` | No | Model to use via OpenRouter, default `openrouter/auto` |
| `OPENROUTER_BASE_URL` | No | OpenRouter API base URL, default `https://openrouter.ai/api/v1` |
| `APP_TIMEZONE` | No | Local timezone used for parsing and display, default `Asia/Tehran` |
| `LOG_LEVEL` | No | Logging level, default `INFO` |
| `LOG_FILE` | No | Log file path, default `logs/task_manager.log` |
| `SCHEDULER_INTERVAL_SECONDS` | No | How often the reminder loop checks due tasks |
| `SCHEDULER_CLAIM_TIMEOUT_SECONDS` | No | When a claimed task is considered stale and safe to recover |
| `SCHEDULER_RETRY_DELAY_SECONDS` | No | Delay before retrying a failed notification |

> **Upgrading from Gemini:** If you have an existing `.env` with `GEMINI_API_KEY`, rename it to `OPENROUTER_API_KEY` and get a key from [openrouter.ai/keys](https://openrouter.ai/keys). `GEMINI_MODEL` → `OPENROUTER_MODEL`.

## Commands

### `/start`
Shows the welcome message and the main commands.

### `/help`
Shows a short Persian guide with examples.

### `/add <task>`
Creates a new task from free text.

Examples:

```text
/add فردا ساعت ۸ خرید نان
/add شنبه ۹ صبح جلسه تیم
/add tomorrow 5pm call Ali
```

If no time is provided, the bot uses the next day at 09:00 in the configured timezone.

### `/list`
Shows your tasks with task IDs, due times, and statuses.

### `/done <id>`
Marks a task as completed.

Example:

```text
/done 3
```

### `/delete <id>`
Deletes a task permanently.

Example:

```text
/delete 3
```

## How reminders work

- Task times are parsed in the configured local timezone.
- The bot stores the final due time in UTC.
- A single async scheduler claims due tasks one time only.
- If the bot restarts, stale in-progress tasks are recovered safely.
- LLM output is never inserted directly; it is validated first and then normalized.

## Troubleshooting

- If the bot exits immediately, check that `BOT_TOKEN` and `OPENROUTER_API_KEY` are set.
- If time parsing looks wrong, verify `APP_TIMEZONE`.
- If you want a clean local database, run:

  ```bash
  python init_db.py
  ```

## Project Layout

- `main.py` — entrypoint: bootstraps logging, database, and the bot
- `app/` — application package
  - `bot.py` — Telegram command handlers
  - `task_parser.py` — OpenRouter LLM + deterministic dateparser fallback
  - `task_repository.py` — SQLite CRUD and workflow
  - `task_service.py` — orchestration layer
  - `scheduler.py` — background reminder loop
  - `models.py` — database schema
  - `config.py` — settings from environment variables
  - `db.py` — database engine and session
  - `time_utils.py` — timezone conversion helpers
  - `logging_utils.py` — rotating file + stream logging
- `init_db.py` — force-recreate the database

## License

Add your preferred license here before publishing.
