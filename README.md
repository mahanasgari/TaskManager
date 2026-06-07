# Telegram Task Manager Bot

A Telegram bot for creating tasks, scheduling reminders, and keeping your task list easy to manage.

## Features

- Create tasks in Persian or English with natural language dates
- Store reminders safely in SQLite with UTC normalization
- Run a background scheduler that avoids duplicate notifications
- Validate Gemini output before it reaches the database
- Manage tasks with `/list`, `/done`, and `/delete`

## Requirements

- Python 3.11+
- A Telegram bot token from [BotFather](https://t.me/BotFather)
- A Gemini API key

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
| `GEMINI_API_KEY` | Yes | Gemini API key |
| `GEMINI_MODEL` | No | Gemini model name, default `gemini-2.0-flash` |
| `APP_TIMEZONE` | No | Local timezone used for parsing and display, default `Asia/Tehran` |
| `LOG_LEVEL` | No | Logging level, default `INFO` |
| `LOG_FILE` | No | Log file path, default `logs/task_manager.log` |
| `SCHEDULER_INTERVAL_SECONDS` | No | How often the reminder loop checks due tasks |
| `SCHEDULER_CLAIM_TIMEOUT_SECONDS` | No | When a claimed task is considered stale and safe to recover |
| `SCHEDULER_RETRY_DELAY_SECONDS` | No | Delay before retrying a failed notification |

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
- Gemini output is never inserted directly; it is validated first and then normalized.

## Troubleshooting

- If the bot exits immediately, check that `BOT_TOKEN` and `GEMINI_API_KEY` are set.
- If time parsing looks wrong, verify `APP_TIMEZONE`.
- If you want a clean local database, run:

  ```bash
  python init_db.py
  ```

## Project Layout

- `main.py` bootstraps logging, database setup, and the bot
- `bot.py` contains Telegram handlers
- `task_parser.py` handles Gemini plus deterministic parsing
- `task_repository.py` owns SQLite persistence logic
- `scheduler.py` runs the reminder loop
- `models.py` defines the database schema

## License

Add your preferred license here before publishing.
