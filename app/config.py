"""
Configuration module
"""

import os

from pydantic import BaseSettings


class Config(BaseSettings):
    """
    Config class.
    """

    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    LOCAL_DEV = True
    if LOCAL_DEV:
        # APP_BASE_URL = "http://localhost"
        BASE_URL = "http://localhost"
        APP_BASE_URL = f"{BASE_URL}:{os.getenv('APP_PORT')}"
    else:
        APP_SUBDOMAIN = os.getenv("APP_SUBDOMAIN")
        BASE_URL = os.getenv("BASE_URL")
        APP_BASE_URL = f"https://{APP_SUBDOMAIN}.{BASE_URL}"
        # APP_BASE_URL = f"https://{os.getenv('APP_BASE_URL')}"


class CeleryConfig(BaseSettings):
    """
    Celery config class.
    """

    broker_url = os.getenv("CELERY_BROKER_URL")
    result_backend = os.getenv("CELERY_RESULT_BACKEND")
    imports = ["src.tasks.test_tasks"]
    enable_utc = True
    timezone = "Europe/Amsterdam"
    task_track_started = True
    result_persistent = True
    task_publish_retry = True
    # The acks_late setting would be used when you need the task to be executed again
    # if the worker (for some reason) crashes mid-execution
    task_acks_late = "Enabled"


app_config = Config()
celery_config = CeleryConfig()
