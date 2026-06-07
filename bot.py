from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

from config import Settings
from scheduler import TaskScheduler
from task_repository import DONE, FAILED, PENDING, PROCESSING, SENT
from task_service import TaskService


logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """سلام! من Task Manager هستم 🤖

با من می‌تونی کارها رو ثبت کنی و یادآوری بگیری.

دستورها:
/add <متن>  افزودن کار جدید
/list       نمایش همه کارها
/done <id>   علامت‌گذاری به‌عنوان انجام‌شده
/delete <id> حذف یک کار
/help       نمایش راهنما

مثال:
/add فردا ساعت ۸ خرید نان
/add شنبه ۹ صبح جلسه تیم
"""

HELP_MESSAGE = """راهنمای استفاده از Task Manager 📘

1) یک کار جدید اضافه کن:
/add فردا ساعت ۸ خرید نان

2) همه کارها را ببین:
/list

3) وقتی کاری را انجام دادی:
/done 3

4) اگر لازم نبود، حذفش کن:
/delete 3

نکته:
- اگر ساعت را ننویسی، ربات به‌صورت پیش‌فرض برای فردا ساعت ۹ صبح تنظیم می‌کند.
- من ورودی فارسی و انگلیسی را می‌فهمم.
"""

STATUS_LABELS = {
    PENDING: "در انتظار",
    PROCESSING: "در حال ارسال",
    SENT: "اعلان شد",
    FAILED: "خطا",
    DONE: "انجام شد",
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


async def _reply_long(update: Update, message: str) -> None:
    for part in _split_message(message):
        await update.message.reply_text(part)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_MESSAGE)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_MESSAGE)


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = " ".join(context.args).strip()

    if not text:
        await update.message.reply_text(
            "برای افزودن کار از این الگو استفاده کن:\n/add فردا ساعت ۸ خرید نان"
        )
        return

    service = _get_service(context)

    try:
        created = await service.create_task(user_id, text)
    except Exception:
        logger.exception("Failed to create task")
        await update.message.reply_text(
            "نتوانستم این کار را بفهمم. لطفاً دوباره با زمان واضح‌تر امتحان کن."
        )
        return

    due_text = service.format_due_datetime(created.task.due_at_utc, created.task.timezone)
    await update.message.reply_text(
        "✅ کار ثبت شد\n\n"
        f"📝 {created.task.title}\n"
        f"⏰ {due_text}\n"
        f"🆔 #{created.task.id}"
    )


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    service = _get_service(context)
    tasks = service.list_tasks(user_id)

    if not tasks:
        await update.message.reply_text(
            "هنوز کاری ثبت نکردی.\n\nبرای شروع بنویس:\n/add فردا ساعت ۸ خرید نان"
        )
        return

    lines = ["فهرست کارهای شما:"]
    for task in tasks:
        due_text = service.format_due_datetime(task.due_at_utc, task.timezone)
        status_label = STATUS_LABELS.get(task.status, task.status)
        lines.append(
            f"\n#{task.id} | {task.title}\n"
            f"⏰ {due_text}\n"
            f"وضعیت: {status_label}"
        )

    lines.append("\nبرای انجام‌شده کردن: /done <id>")
    lines.append("برای حذف: /delete <id>")
    await _reply_long(update, "\n".join(lines))


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    service = _get_service(context)

    if not context.args:
        await update.message.reply_text("استفاده درست: /done 3")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("شناسه کار باید عدد باشد. مثال: /done 3")
        return

    task = service.mark_done(user_id, task_id)
    if task is None:
        await update.message.reply_text("چنین کاری پیدا نشد.")
        return

    await update.message.reply_text(f"✅ کار #{task.id} به‌عنوان انجام‌شده ثبت شد.")


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    service = _get_service(context)

    if not context.args:
        await update.message.reply_text("استفاده درست: /delete 3")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("شناسه کار باید عدد باشد. مثال: /delete 3")
        return

    deleted = service.delete_task(user_id, task_id)
    if not deleted:
        await update.message.reply_text("چنین کاری پیدا نشد.")
        return

    await update.message.reply_text(f"🗑️ کار #{task_id} حذف شد.")


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

    return application


def run_bot(settings: Settings) -> None:
    application = build_application(settings)
    application.run_polling()
