"""
Module spinning up the Celery worker
"""

from celery import Celery
from celery.utils.log import get_task_logger
from config import celery_config

celery = Celery(__name__)
# a dict, not the settings object: Celery lists the attributes of an object with dir(), and pydantic puts a
# '__signature__' there that raises when read on an instance (celery.conf.table(), used by Flower, fails)
celery.config_from_object(celery_config.model_dump())
celery.autodiscover_tasks(force=True)

logger = get_task_logger(__name__)
