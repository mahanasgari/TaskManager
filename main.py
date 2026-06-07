from bot import run_bot
from scheduler import start_scheduler
import threading

if __name__ == "__main__":
    start_scheduler()
    run_bot()