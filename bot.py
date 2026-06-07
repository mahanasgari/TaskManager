from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN

# حافظه موقت (فعلاً بدون دیتابیس)
tasks = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام ربات Task Manager فعاله")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    task_text = " ".join(context.args)

    if not task_text:
        await update.message.reply_text("مثال: /add خرید نان")
        return

    tasks.setdefault(user_id, []).append(task_text)

    await update.message.reply_text(f"✅ اضافه شد: {task_text}")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_tasks = tasks.get(user_id, [])

    if not user_tasks:
        await update.message.reply_text("هیچ تسکی نداری")
        return

    msg = "\n".join([f"{i+1}. {t}" for i, t in enumerate(user_tasks)])
    await update.message.reply_text(msg)

def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_tasks))

    app.run_polling()