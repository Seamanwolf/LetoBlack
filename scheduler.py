import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, current_app
from app.utils import create_db_connection
from app.vats import change_numbers_periodically
from app.callcenter import partial_sync_data
from app.extensions import socketio
from redis import Redis
from apscheduler.jobstores.redis import RedisJobStore

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("Scheduler")

app = Flask(__name__)
app.config.from_object("app.config")

# Настраиваем RedisJobStore (например, используем db=1)
redis_conn = Redis(host='localhost', port=6379, db=1)
jobstores = {
    'default': RedisJobStore(connection=redis_conn)
}

scheduler = BackgroundScheduler(jobstores=jobstores)

def change_numbers_periodically_with_context():
    with app.app_context():
        try:
            logger.debug("Начинаем смену номеров.")
            change_numbers_periodically()
            logger.info("Смена номеров выполнена успешно.")
        except Exception as e:
            logger.error(f"Ошибка при смене номеров: {e}", exc_info=True)

def auto_sync_data_job():
    with app.app_context():
        try:
            logger.debug("🔄 Начинаем выгрузку данных в Google Таблицы.")
            partial_sync_data()
            logger.info("✅ Выгрузка данных завершена успешно.")
        except Exception as e:
            logger.error(f"❌ Ошибка при выполнении синхронизации: {e}", exc_info=True)

def initialize_scheduler():
    global scheduler

    logger.info("🛠 Инициализация планировщика задач...")

    existing_jobs = scheduler.get_jobs()
    logger.info(f"📌 Текущие задачи в планировщике: {[job.id for job in existing_jobs]}")

    # Задача: частичная синхронизация каждые 15 минут, только с 9 до 21 часов
    if not scheduler.get_job("auto_sync_data_job"):
        logger.info("➕ Добавляем задачу автоматической синхронизации.")
        scheduler.add_job(
            func=auto_sync_data_job,
            trigger=CronTrigger(minute='*/15', hour='9-21'),
            id="auto_sync_data_job",
            replace_existing=True
        )
        logger.info("✅ Задача auto_sync_data_job добавлена в планировщик.")

    # Задача: смена номеров, запуск каждый час на 59-й минуте с 9 до 21 часов
    if not scheduler.get_job("change_numbers_periodically_with_context"):
        logger.info("➕ Добавляем задачу смены номеров.")
        scheduler.add_job(
            func=change_numbers_periodically_with_context,
            trigger=CronTrigger(minute='59', hour='9-21'),
            id="change_numbers_periodically_with_context",
            replace_existing=True
        )
        logger.info("✅ Задача change_numbers_periodically_with_context добавлена в планировщик.")

    scheduler.start()
    logger.info("🚀 Планировщик запущен.")

if __name__ == "__main__":
    initialize_scheduler()
    logger.info("✅ Планировщик работает. Ожидание выполнения задач...")
    try:
        while True:
            pass  # Бесконечный цикл для поддержки работы шедулера
    except KeyboardInterrupt:
        logger.info("🛑 Остановка планировщика.")
        scheduler.shutdown()
