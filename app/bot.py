from __future__ import annotations

import asyncio
import html
import logging
from contextlib import suppress

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import Settings
from app.scheduler import TaskScheduler
from app.task_repository import DONE, FAILED, PENDING, PROCESSING, SENT
from app.task_service import TaskService


logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """\u0633\u0644\u0627\u0645! \u0645\u0646 Task Manager \u0647\u0633\u062a\u0645 \U0001f916

\u0628\u0627 \u0645\u0646 \u0645\u06cc\u200c\u062a\u0648\u0646\u06cc \u06a9\u0627\u0631\u0647\u0627 \u0631\u0648 \u062b\u0628\u062a \u06a9\u0646\u06cc \u0648 \u06cc\u0627\u062f\u0622\u0648\u0631\u06cc \u0628\u06af\u06cc\u0631\u06cc.

\u062f\u0633\u062a\u0648\u0631\u0647\u0627:
/add <\u0645\u062a\u0646>  \u0627\u0641\u0632\u0648\u062f\u0646 \u06a9\u0627\u0631 \u062c\u062f\u06cc\u062f
/list       \u0646\u0645\u0627\u06cc\u0634 \u0647\u0645\u0647 \u06a9\u0627\u0631\u0647\u0627
/done <id>  \u0639\u0644\u0627\u0645\u062a\u200c\u06af\u0630\u0627\u0631\u06cc \u0628\u0647\u200c\u0639\u0646\u0648\u0627\u0646 \u0627\u0646\u062c\u0627\u0645\u200c\u0634\u062f\u0647
/delete <id> \u062d\u0630\u0641 \u06cc\u06a9 \u06a9\u0627\u0631
/help       \u0646\u0645\u0627\u06cc\u0634 \u0631\u0627\u0647\u0646\u0645\u0627

\u0645\u062b\u0627\u0644:
/add \u0641\u0631\u062f\u0627 \u0633\u0627\u0639\u062a \u06f8 \u062e\u0631\u06cc\u062f \u0646\u0627\u0646
/add \u0634\u0646\u0628\u0647 \u06f9 \u0635\u0628\u062d \u062c\u0644\u0633\u0647 \u062a\u06cc\u0645
"""

HELP_MESSAGE = """\u0631\u0627\u0647\u0646\u0645\u0627\u06cc \u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u0627\u0632 Task Manager \U0001f4d8

1) \u06cc\u06a9 \u06a9\u0627\u0631 \u062c\u062f\u06cc\u062f \u0627\u0636\u0627\u0641\u0647 \u06a9\u0646:
/add \u0641\u0631\u062f\u0627 \u0633\u0627\u0639\u062a \u06f8 \u062e\u0631\u06cc\u062f \u0646\u0627\u0646

2) \u0647\u0645\u0647 \u06a9\u0627\u0631\u0647\u0627 \u0631\u0627 \u0628\u0628\u06cc\u0646:
/list

3) \u0648\u0642\u062a\u06cc \u06a9\u0627\u0631\u06cc \u0631\u0627 \u0627\u0646\u062c\u0627\u0645 \u062f\u0627\u062f\u06cc:
/done 3

4) \u0627\u06af\u0631 \u0644\u0627\u0632\u0645 \u0646\u0628\u0648\u062f\u060c \u062d\u0630\u0641\u0634 \u06a9\u0646:
/delete 3

\u0646\u06a9\u062a\u0647:
- \u0627\u06af\u0631 \u0633\u0627\u0639\u062a \u0631\u0627 \u0646\u0646\u0648\u06cc\u0633\u06cc\u060c \u0631\u0628\u0627\u062a \u0628\u0647\u200c\u0635\u0648\u0631\u062a \u067e\u06cc\u0634\u200c\u0641\u0631\u0636 \u0628\u0631\u0627\u06cc \u0641\u0631\u062f\u0627 \u0633\u0627\u0639\u062a \u06f9 \u0635\u0628\u062d \u062a\u0646\u0638\u06cc\u0645 \u0645\u06cc\u200c\u06a9\u0646\u062f.
- \u0645\u0646 \u0648\u0631\u0648\u062f\u06cc \u0641\u0627\u0631\u0633\u06cc \u0648 \u0627\u0646\u06af\u0644\u06cc\u0633\u06cc \u0631\u0627 \u0645\u06cc\u200c\u0641\u0647\u0645\u0645.
"""

STATUS_LABELS = {
    PENDING: "\u062f\u0631 \u0627\u0646\u062a\u0638\u0627\u0631",
    PROCESSING: "\u062f\u0631 \u062d\u0627\u0644 \u0627\u0631\u0633\u0627\u0644",
    SENT: "\u0627\u0639\u0644\u0627\u0646 \u0634\u062f",
    FAILED: "\u062e\u0637\u0627",
    DONE: "\u0627\u0646\u062c\u0627\u0645 \u0634\u062f",
}


def _get_service(context: ContextTypes.DEFAULT_TYPE) -> TaskService:
    return context.application.bot_data["task_service"]


def _split_message(message: str, limit: int = 3900) -> list[str]:
    if len(message) <= limit:
        return [message]

    parts: list[str] = []
    remaining = message
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        parts.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return parts


async def _reply_long(update: Update, message: str, parse_mode: str | None = None) -> None:
    for part in _split_message(message):
        await update.message.reply_text(part, parse_mode=parse_mode)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_MESSAGE)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_MESSAGE)


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = " ".join(context.args).strip()

    if not text:
        await update.message.reply_text(
            "\u0628\u0631\u0627\u06cc \u0627\u0641\u0632\u0648\u062f\u0646 \u06a9\u0627\u0631 \u0627\u0632 \u0627\u06cc\u0646 \u0627\u0644\u06af\u0648 \u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u06a9\u0646:\n/add \u0641\u0631\u062f\u0627 \u0633\u0627\u0639\u062a \u06f8 \u062e\u0631\u06cc\u062f \u0646\u0627\u0646"
        )
        return

    service = _get_service(context)

    try:
        created = await service.create_task(user_id, text)
    except Exception:
        logger.exception("Failed to create task")
        await update.message.reply_text(
            "\u0646\u062a\u0648\u0627\u0646\u0633\u062a\u0645 \u0627\u06cc\u0646 \u06a9\u0627\u0631 \u0631\u0627 \u0628\u0641\u0647\u0645\u0645. \u0644\u0637\u0641\u0627\u064b \u062f\u0648\u0628\u0627\u0631\u0647 \u0628\u0627 \u0632\u0645\u0627\u0646 \u0648\u0627\u0636\u062d\u200c\u062a\u0631 \u0627\u0645\u062a\u062d\u0627\u0646 \u06a9\u0646."
        )
        return

    due_text = service.format_due_datetime(created.task.due_at_utc, created.task.timezone)
    await update.message.reply_text(
        "\u2705 \u06a9\u0627\u0631 \u062b\u0628\u062a \u0634\u062f\n\n"
        f"\U0001f4dd <b>{html.escape(created.task.title)}</b>\n"
        f"\u23f0 {due_text}\n"
        f"\U0001f194 #{created.task.id}",
        parse_mode="HTML",
    )


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    service = _get_service(context)
    try:
        tasks = service.list_tasks(user_id)
    except Exception:
        logger.exception("Failed to list tasks")
        await update.message.reply_text("\u062e\u0637\u0627\u06cc\u06cc \u062f\u0631 \u0628\u0627\u0632\u06cc\u0627\u0628\u06cc \u0644\u06cc\u0633\u062a \u0631\u062e \u062f\u0627\u062f.")
        return

    if not tasks:
        await update.message.reply_text(
            "\u0647\u0646\u0648\u0632 \u06a9\u0627\u0631\u06cc \u062b\u0628\u062a \u0646\u06a9\u0631\u062f\u06cc.\n\n\u0628\u0631\u0627\u06cc \u0634\u0631\u0648\u0639 \u0628\u0646\u0648\u06cc\u0633:\n/add \u0641\u0631\u062f\u0627 \u0633\u0627\u0639\u062a \u06f8 \u062e\u0631\u06cc\u062f \u0646\u0627\u0646"
        )
        return

    grouped: dict[str, list] = {}
    for task in tasks:
        grouped.setdefault(task.status, []).append(task)

    status_order = [PENDING, PROCESSING, FAILED, SENT, DONE]
    section_labels = {
        PENDING: "\U0001f4cc \u062f\u0631 \u0627\u0646\u062a\u0638\u0627\u0631",
        PROCESSING: "\u23f3 \u062f\u0631 \u062d\u0627\u0644 \u0627\u0631\u0633\u0627\u0644",
        FAILED: "\u274c \u062e\u0637\u0627",
        SENT: "\u2705 \u0627\u0639\u0644\u0627\u0646 \u0634\u062f",
        DONE: "\u2705 \u0627\u0646\u062c\u0627\u0645 \u0634\u062f",
    }

    parts: list[str] = []
    for status_key in status_order:
        section_tasks = grouped.get(status_key)
        if not section_tasks:
            continue
        parts.append(f"\n<b>{section_labels[status_key]} ({len(section_tasks)})</b>")
        for t in section_tasks:
            due_text = service.format_due_datetime(t.due_at_utc, t.timezone)
            parts.append(f"#{t.id} | <b>{html.escape(t.title)}</b>  \u23f0 {due_text}")

    parts.append("\n/done &lt;id&gt; \u2014 \u0627\u0646\u062c\u0627\u0645 \u0634\u062f\u0647")
    parts.append("/delete &lt;id&gt; \u2014 \u062d\u0630\u0641")
    await _reply_long(update, "\n".join(parts), parse_mode="HTML")


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    service = _get_service(context)

    if not context.args:
        await update.message.reply_text("\u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u062f\u0631\u0633\u062a: /done 3")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("\u0634\u0646\u0627\u0633\u0647 \u06a9\u0627\u0631 \u0628\u0627\u06cc\u062f \u0639\u062f\u062f \u0628\u0627\u0634\u062f. \u0645\u062b\u0627\u0644: /done 3")
        return

    try:
        task = service.mark_done(user_id, task_id)
    except Exception:
        logger.exception("Failed to mark task done")
        await update.message.reply_text("\u062e\u0637\u0627\u06cc\u06cc \u062f\u0631 \u062b\u0628\u062a \u0627\u0646\u062c\u0627\u0645 \u06a9\u0627\u0631 \u0631\u062e \u062f\u0627\u062f.")
        return

    if task is None:
        await update.message.reply_text("\u0686\u0646\u06cc\u0646 \u06a9\u0627\u0631\u06cc \u067e\u06cc\u062f\u0627 \u0646\u0634\u062f.")
        return

    await update.message.reply_text(
        f"\u2705 <b>{html.escape(task.title)}</b> \u0627\u0646\u062c\u0627\u0645 \u0634\u062f.",
        parse_mode="HTML",
    )


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    service = _get_service(context)

    if not context.args:
        await update.message.reply_text("\u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u062f\u0631\u0633\u062a: /delete 3")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("\u0634\u0646\u0627\u0633\u0647 \u06a9\u0627\u0631 \u0628\u0627\u06cc\u062f \u0639\u062f\u062f \u0628\u0627\u0634\u062f. \u0645\u062b\u0627\u0644: /delete 3")
        return

    try:
        deleted = service.delete_task(user_id, task_id)
    except Exception:
        logger.exception("Failed to delete task")
        await update.message.reply_text("\u062e\u0637\u0627\u06cc\u06cc \u062f\u0631 \u062d\u0630\u0641 \u06a9\u0627\u0631 \u0631\u062e \u062f\u0627\u062f.")
        return

    if not deleted:
        await update.message.reply_text("\u0686\u0646\u06cc\u0646 \u06a9\u0627\u0631\u06cc \u067e\u06cc\u062f\u0627 \u0646\u0634\u062f.")
        return

    await update.message.reply_text(f"\U0001f5d1\ufe0f \u06a9\u0627\u0631 #{task_id} \u062d\u0630\u0641 \u0634\u062f.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()

    if not text:
        return

    edit_state = context.user_data.pop("edit", None)
    if edit_state:
        await _process_edit_input(update, context, user_id, text, edit_state)
        return

    service = _get_service(context)

    try:
        created = await service.create_task(user_id, text)
    except Exception:
        logger.exception("Failed to create task from free text")
        await update.message.reply_text(
            "\u0646\u062a\u0648\u0627\u0646\u0633\u062a\u0645 \u0627\u06cc\u0646 \u0631\u0627 \u0628\u0647\u200c\u0639\u0646\u0648\u0627\u0646 \u06cc\u06a9 \u06a9\u0627\u0631 \u0628\u0641\u0647\u0645\u0645.\n"
            "\u0628\u0631\u0627\u06cc \u062b\u0628\u062a \u062f\u0633\u062a\u06cc \u0627\u0632 /add \u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u06a9\u0646."
        )
        return

    due_text = service.format_due_datetime(created.task.due_at_utc, created.task.timezone)
    await update.message.reply_text(
        "\u2705 \u06a9\u0627\u0631 \u062b\u0628\u062a \u0634\u062f\n\n"
        f"\U0001f4dd <b>{html.escape(created.task.title)}</b>\n"
        f"\u23f0 {due_text}\n"
        f"\U0001f194 #{created.task.id}",
        parse_mode="HTML",
    )


async def _process_edit_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    text: str,
    edit_state: dict,
) -> None:
    service = _get_service(context)
    task_id = edit_state["task_id"]
    field = edit_state["field"]

    if field == "title":
        updated = service.repository.update_task(user_id, task_id, title=text)
        if updated:
            await update.message.reply_text(
                f"\u2705 \u0639\u0646\u0648\u0627\u0646 \u0628\u0647\u200c\u0631\u0648\u0632 \u0634\u062f: <b>{html.escape(updated.title)}</b>",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text("\u062e\u0637\u0627\u06cc \u062f\u0631 \u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc.")
    elif field == "time":
        try:
            updated = await service.update_task(user_id, task_id, text, update_title=False, update_time=True)
        except Exception:
            await update.message.reply_text("\u0646\u062a\u0648\u0627\u0646\u0633\u062a\u0645 \u0632\u0645\u0627\u0646 \u0631\u0627 \u062a\u0634\u062e\u06cc\u0635 \u062f\u0647\u0645.")
            return
        if updated:
            due_text = service.format_due_datetime(updated.task.due_at_utc, updated.task.timezone)
            await update.message.reply_text(f"\u2705 \u0632\u0645\u0627\u0646 \u0628\u0647\u200c\u0631\u0648\u0632 \u0634\u062f: {due_text}", parse_mode="HTML")
        else:
            await update.message.reply_text("\u062e\u0637\u0627\u06cc \u062f\u0631 \u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc.")
    elif field == "both":
        try:
            updated = await service.update_task(user_id, task_id, text, update_title=True, update_time=True)
        except Exception:
            await update.message.reply_text(
                "\u0646\u062a\u0648\u0627\u0646\u0633\u062a\u0645 \u0627\u06cc\u0646 \u0631\u0627 \u0628\u0641\u0647\u0645\u0645.\n"
                "\u0628\u0631\u0627\u06cc \u0648\u06cc\u0631\u0627\u06cc\u0634 \u062f\u0633\u062a\u06cc: /edit 3 title:\u0645\u062a\u0646 \u06cc\u0627 /edit 3 time:\u0632\u0645\u0627\u0646"
            )
            return
        if updated:
            due_text = service.format_due_datetime(updated.task.due_at_utc, updated.task.timezone)
            await update.message.reply_text(
                f"\u2705 \u06a9\u0627\u0631 \u0648\u06cc\u0631\u0627\u06cc\u0634 \u0634\u062f\n\n"
                f"\U0001f4dd <b>{html.escape(updated.task.title)}</b>\n"
                f"\u23f0 {due_text}\n"
                f"\U0001f194 #{updated.task.id}",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text("\u062e\u0637\u0627\u06cc \u062f\u0631 \u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc.")


async def done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    service = _get_service(context)

    try:
        task_id = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await query.edit_message_text("\u062e\u0637\u0627\u06cc \u062f\u0631 \u062f\u0631\u06cc\u0627\u0641\u062a \u0634\u0646\u0627\u0633\u0647 \u06a9\u0627\u0631.")
        return

    try:
        task = service.mark_done(user_id, task_id)
    except Exception:
        logger.exception("Failed to mark task done via callback")
        await query.edit_message_text(
            "\u062e\u0637\u0627\u06cc\u06cc \u062f\u0631 \u062b\u0628\u062a \u0627\u0646\u062c\u0627\u0645 \u06a9\u0627\u0631 \u0631\u062e \u062f\u0627\u062f."
        )
        return

    if task is None:
        await query.edit_message_text(
            f"\u2705 \u0627\u06cc\u0646 \u06a9\u0627\u0631 \u0627\u0632 \u0642\u0628\u0644 \u0627\u0646\u062c\u0627\u0645 \u0634\u062f\u0647 \u06cc\u0627 \u067e\u06cc\u062f\u0627 \u0646\u0634\u062f."
        )
        return

    await query.edit_message_text(
        f"\u2705 <b>{html.escape(task.title)}</b> \u0627\u0646\u062c\u0627\u0645 \u0634\u062f.",
        parse_mode="HTML",
    )


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    service = _get_service(context)

    if not context.args:
        await update.message.reply_text(
            "\u0627\u0633\u062a\u0641\u0627\u062f\u0647: /edit <id> [\u0645\u062a\u0646 \u062c\u062f\u06cc\u062f]\n"
            "\u0645\u062b\u0627\u0644: /edit 3 \u0641\u0631\u062f\u0627 \u0633\u0627\u0639\u062a \u06f1\u06f0 \u062e\u0631\u06cc\u062f \u0634\u06cc\u0631"
        )
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("\u0634\u0646\u0627\u0633\u0647 \u06a9\u0627\u0631 \u0628\u0627\u06cc\u062f \u0639\u062f\u062f \u0628\u0627\u0634\u062f.")
        return

    task = service.get_task(user_id, task_id)
    if task is None:
        await update.message.reply_text("\u0686\u0646\u06cc\u0646 \u06a9\u0627\u0631\u06cc \u067e\u06cc\u062f\u0627 \u0646\u0634\u062f.")
        return

    # One-command edit: /edit <id> <text>
    if len(context.args) > 1:
        text = " ".join(context.args[1:])

        lower = text.lower()
        title_prefix = lower.startswith("title:")
        time_prefix = lower.startswith("time:")

        if title_prefix and not time_prefix:
            new_title = text.split(":", 1)[1].strip()
            if not new_title:
                await update.message.reply_text("\u0645\u062a\u0646 \u062c\u062f\u06cc\u062f \u0631\u0627 \u0628\u0646\u0648\u06cc\u0633\u06cc\u062f.")
                return
            updated = service.repository.update_task(user_id, task_id, title=new_title)
            if updated:
                await update.message.reply_text(
                    f"\u2705 \u0639\u0646\u0648\u0627\u0646 \u0628\u0647\u200c\u0631\u0648\u0632 \u0634\u062f: <b>{html.escape(updated.title)}</b>",
                    parse_mode="HTML",
                )
            else:
                await update.message.reply_text("\u062e\u0637\u0627\u06cc \u062f\u0631 \u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc.")
            return

        if time_prefix and not title_prefix:
            new_time = text.split(":", 1)[1].strip()
            if not new_time:
                await update.message.reply_text("\u0632\u0645\u0627\u0646 \u062c\u062f\u06cc\u062f \u0631\u0627 \u0628\u0646\u0648\u06cc\u0633\u06cc\u062f.")
                return
            try:
                updated = await service.update_task(user_id, task_id, new_time, update_title=False, update_time=True)
            except Exception:
                await update.message.reply_text("\u0646\u062a\u0648\u0627\u0646\u0633\u062a\u0645 \u0632\u0645\u0627\u0646 \u0631\u0627 \u062a\u0634\u062e\u06cc\u0635 \u062f\u0647\u0645.")
                return
            if updated:
                due_text = service.format_due_datetime(updated.task.due_at_utc, updated.task.timezone)
                await update.message.reply_text(f"\u2705 \u0632\u0645\u0627\u0646 \u0628\u0647\u200c\u0631\u0648\u0632 \u0634\u062f: {due_text}", parse_mode="HTML")
            else:
                await update.message.reply_text("\u062e\u0637\u0627\u06cc \u062f\u0631 \u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc.")
            return

        # Full text re-parse (no prefix)
        try:
            updated = await service.update_task(user_id, task_id, text, update_title=True, update_time=True)
        except Exception:
            await update.message.reply_text(
                "\u0646\u062a\u0648\u0627\u0646\u0633\u062a\u0645 \u0627\u06cc\u0646 \u0631\u0627 \u0628\u0641\u0647\u0645\u0645.\n"
                "\u0628\u0631\u0627\u06cc \u0648\u06cc\u0631\u0627\u06cc\u0634 \u062f\u0633\u062a\u06cc: /edit 3 title:\u0645\u062a\u0646 \u06cc\u0627 /edit 3 time:\u0632\u0645\u0627\u0646"
            )
            return
        if updated:
            due_text = service.format_due_datetime(updated.task.due_at_utc, updated.task.timezone)
            await update.message.reply_text(
                f"\u2705 \u06a9\u0627\u0631 \u0648\u06cc\u0631\u0627\u06cc\u0634 \u0634\u062f\n\n"
                f"\U0001f4dd <b>{html.escape(updated.task.title)}</b>\n"
                f"\u23f0 {due_text}\n"
                f"\U0001f194 #{updated.task.id}",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text("\u062e\u0637\u0627\u06cc \u062f\u0631 \u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc.")
        return

    # Conversation flow: /edit <id> (no extra text)
    due_text = service.format_due_datetime(task.due_at_utc, task.timezone)
    status_label = STATUS_LABELS.get(task.status, task.status)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\U0001f4dd \u0639\u0646\u0648\u0627\u0646", callback_data=f"edit_title:{task.id}"),
            InlineKeyboardButton("\u23f0 \u0632\u0645\u0627\u0646", callback_data=f"edit_time:{task.id}"),
        ],
        [
            InlineKeyboardButton("\U0001f504 \u0647\u0631 \u062f\u0648", callback_data=f"edit_both:{task.id}"),
            InlineKeyboardButton("\u274c \u0644\u063a\u0648", callback_data=f"edit_cancel:{task.id}"),
        ],
    ])
    await update.message.reply_text(
        f"\U0001f4dd <b>{html.escape(task.title)}</b>\n"
        f"\u23f0 {due_text}\n"
        f"\U0001f194 #{task.id}  |  {status_label}\n\n"
        "\u0686\u0647 \u0686\u06cc\u0632\u06cc \u0631\u0627 \u0648\u06cc\u0631\u0627\u06cc\u0634 \u06a9\u0646\u06cc\u062f\u061f",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    service = _get_service(context)

    try:
        action, task_id_str = query.data.split(":", 1)
        task_id = int(task_id_str)
    except (ValueError, IndexError):
        await query.edit_message_text("\u062e\u0637\u0627\u06cc \u062f\u0631 \u062f\u0631\u06cc\u0627\u0641\u062a \u0627\u0637\u0644\u0627\u0639\u0627\u062a.")
        return

    if action == "edit_cancel":
        context.user_data.pop("edit", None)
        await query.edit_message_text("\u0648\u06cc\u0631\u0627\u06cc\u0634 \u0644\u063a\u0648 \u0634\u062f.")
        return

    if action not in ("edit_title", "edit_time", "edit_both"):
        return

    task = service.get_task(user_id, task_id)
    if task is None:
        context.user_data.pop("edit", None)
        await query.edit_message_text("\u06a9\u0627\u0631 \u067e\u06cc\u062f\u0627 \u0646\u0634\u062f.")
        return

    context.user_data["edit"] = {"task_id": task_id, "field": action.split("_", 1)[1]}

    if action == "edit_title":
        await query.edit_message_text(
            f"\U0001f4dd \u0639\u0646\u0648\u0627\u0646 \u0641\u0639\u0644\u06cc: <b>{html.escape(task.title)}</b>\n\n"
            "\u0639\u0646\u0648\u0627\u0646 \u062c\u062f\u06cc\u062f \u0631\u0627 \u0628\u0641\u0631\u0633\u062a:",
            parse_mode="HTML",
        )
    elif action == "edit_time":
        due_text = service.format_due_datetime(task.due_at_utc, task.timezone)
        await query.edit_message_text(
            f"\u23f0 \u0632\u0645\u0627\u0646 \u0641\u0639\u0644\u06cc: {due_text}\n\n"
            "\u0632\u0645\u0627\u0646 \u062c\u062f\u06cc\u062f \u0631\u0627 \u0628\u0641\u0631\u0633\u062a (\u0645\u062b\u0644: \u0641\u0631\u062f\u0627 \u0633\u0627\u0639\u062a \u06f1\u06f0 \u0634\u0628):",
            parse_mode="HTML",
        )
    elif action == "edit_both":
        due_text = service.format_due_datetime(task.due_at_utc, task.timezone)
        await query.edit_message_text(
            f"\U0001f4dd <b>{html.escape(task.title)}</b>\n"
            f"\u23f0 {due_text}\n\n"
            "\u0645\u062a\u0646 \u06a9\u0627\u0645\u0644 \u06a9\u0627\u0631 \u0631\u0627 \u0628\u0641\u0631\u0633\u062a (\u0645\u062b\u0644: \u0641\u0631\u062f\u0627 \u0633\u0627\u0639\u062a \u06f8 \u062e\u0631\u06cc\u062f \u0646\u0627\u0646):",
            parse_mode="HTML",
        )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cleared = context.user_data.pop("edit", None)
    if cleared:
        await update.message.reply_text("\u0648\u06cc\u0631\u0627\u06cc\u0634 \u0644\u063a\u0648 \u0634\u062f.")
    else:
        await update.message.reply_text("\u0648\u06cc\u0631\u0627\u06cc\u0634\u06cc \u062f\u0631 \u0627\u0646\u062a\u0638\u0627\u0631 \u0646\u06cc\u0633\u062a.")


async def _post_init(application: Application) -> None:
    scheduler: TaskScheduler = application.bot_data["scheduler"]
    scheduler_task = application.create_task(scheduler.run(application.bot))
    application.bot_data["scheduler_task"] = scheduler_task
    logger.info("Background scheduler task started")


async def _post_shutdown(application: Application) -> None:
    scheduler: TaskScheduler = application.bot_data["scheduler"]
    scheduler.stop()
    task = application.bot_data.get("scheduler_task")
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    logger.info("Background scheduler task stopped")


def build_application(settings: Settings) -> Application:
    task_service = TaskService(settings)
    scheduler = TaskScheduler(settings, task_service.repository)

    application = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    application.bot_data["task_service"] = task_service
    application.bot_data["scheduler"] = scheduler

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("list", list_tasks))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("delete", delete))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(done_callback, pattern=r"^done:\d+$"))
    application.add_handler(CallbackQueryHandler(edit_callback, pattern=r"^edit_(title|time|both|cancel):\d+$"))

    return application


def run_bot(settings: Settings) -> None:
    application = build_application(settings)
    application.run_polling()
