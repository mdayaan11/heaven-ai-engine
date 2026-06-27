"""Celery worker entry point."""
from tasks.build_tasks import celery_app

if __name__ == '__main__':
    celery_app.start()
