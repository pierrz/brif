# pylint: disable=too-few-public-methods

"""
Configuration module
"""

import os
import re
from pathlib import Path

from pydantic import BaseSettings


class Config(BaseSettings):
    """
    Config class. Used as a base class for the Celery config.
    """

    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    IIIF_IMG_VERSION = 2
    API_IIIF_IMAGE = f"{os.getenv('API_IMAGE_BACKEND')}iiif/{IIIF_IMG_VERSION}/"  # cantaloupe container
    DATA_DIR = Path(Path(os.getcwd()).parent, "data")
    SECRET_KEY = os.getenv("SECRET_KEY")

    # local or remote settings
    # TODO: replace 'LOCAL_DEV' with nginx container check
    LOCAL_DEV = False
    if LOCAL_DEV:
        BASE_URL = "http://localhost"
        APP_BASE_URL = f"{BASE_URL}:{os.getenv('APP_PORT')}"
        API_IIIF_IMAGE_LOCAL_PORT = re.sub(r":.*", "", os.getenv("CANTALOUPE_PORT"))
        API_IIIF_IMAGE_PUBLIC = (
            f"{BASE_URL}:{API_IIIF_IMAGE_LOCAL_PORT}/iiif/{IIIF_IMG_VERSION}/"
        )
        API_IIIF_PRES = f"{APP_BASE_URL}/iiif/pres/"

    else:
        APP_SUBDOMAIN = os.getenv("APP_SUBDOMAIN")
        BASE_URL = os.getenv("BASE_URL")
        APP_BASE_URL = f"https://{APP_SUBDOMAIN}.{BASE_URL}"
        API_IIIF_IMAGE_PUBLIC = (
            f"https://cantaloupe.{BASE_URL}/iiif/{IIIF_IMG_VERSION}/"
        )
        API_IIIF_PRES = f"{APP_BASE_URL}/iiif/pres/"


class CeleryConfig(BaseSettings):
    """
    Celery config class.
    """

    broker_url = os.getenv("CELERY_BROKER_URL")
    result_backend = os.getenv("CELERY_RESULT_BACKEND")
    imports = [
        "src.tasks.etl.task_etl_delete",
        "src.tasks.etl.task_etl_generate_single_manifest",
        "src.tasks.etl.task_etl_generate_manifests",
        "src.tasks.etl.task_etl_itemize",
        "src.tasks.etl.task_etl_load_db",
        "src.tasks.test_tasks",
    ]
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
