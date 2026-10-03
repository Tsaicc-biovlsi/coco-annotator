from celery import Celery
from config import Config
from database import connect_mongo

connect_mongo('Celery_Worker')

celery = Celery(
    Config.NAME,
    backend=Config.CELERY_RESULT_BACKEND,
    broker=Config.CELERY_BROKER_URL
)
celery.conf.update(
    broker_connection_retry_on_startup=True,
    # Run tasks in-process (no worker/broker needed) for local development
    task_always_eager=Config.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=Config.CELERY_TASK_ALWAYS_EAGER,
)
# shared_task resolves the "current" app, which is thread-local: make this
# app the process-wide default so request threads (gthread) use it too.
celery.set_default()
celery.autodiscover_tasks(['workers.tasks'])


if __name__ == '__main__':
    celery.start()
