from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN
from db import SessionLocal
from models import Task
from datetime import datetime

def get_db():
    return SessionLocal()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ربات Task Manager فعاله 🚀")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    try:
        text = " ".join(context.args)
        if not text:
            await update.message.reply_text("مثال: /add مطالعه زبان")
            return

        db = get_db()

        task = Task(
            user_id=user_id,
            title=text,
            due_time=datetime.now()  # فعلاً موقت (بعداً واقعی میشه)
        )

        db.add(task)
        db.commit()
        db.close()

        await update.message.reply_text(f"✅ ذخیره شد: {text}")

    except Exception as e:
        await update.message.reply_text("❌ خطا در ذخیره")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    db = get_db()
    tasks = db.query(Task).filter(Task.user_id == user_id).all()
    db.close()

    if not tasks:
        await update.message.reply_text("هیچ تسکی نداری")
        return

    msg = ""
    for i, t in enumerate(tasks):
        msg += f"{i+1}. {t.title}\n"

    await update.message.reply_text(msg)

def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_tasks))

    app.run_polling()