from apscheduler.schedulers.background import BackgroundScheduler
from db import SessionLocal
from models import Task
from datetime import datetime
from telegram import Bot
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)

def check_tasks():
    db = SessionLocal()

    now = datetime.now()

    tasks = db.query(Task).filter(
        Task.is_done == False,
        Task.notified == False
    ).all()

    for task in tasks:
        # فعلاً ساده: اگر زمان گذشته باشد
        if task.due_time <= now:
            bot.send_message(
                chat_id=task.user_id,
                text=f"⏰ یادآوری:\n{task.title}"
            )

            task.notified = True

    db.commit()
    db.close()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_tasks, "interval", seconds=30)
    scheduler.start()