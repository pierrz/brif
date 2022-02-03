"""
Module spinning up the Celery worker
"""

from celery import Celery
from celery.utils.log import get_task_logger
from config import celery_config

celery = Celery(__name__)
celery.config_from_object(celery_config)
celery.autodiscover_tasks(force=True)

logger = get_task_logger(__name__)
