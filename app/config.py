# pylint: disable=too-few-public-methods

"""
Configuration module
"""

import os
import re
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """
    Config class. Used as a base class for the Celery config.
    """

    DB_NAME: Optional[str] = os.getenv("DB_NAME")
    DB_USER: Optional[str] = os.getenv("DB_USER")
    DB_PASSWORD: Optional[str] = os.getenv("DB_PASSWORD")
    IIIF_IMG_VERSION: int = 2
    API_IIIF_IMAGE: str = (
        f"{os.getenv('API_IMAGE_BACKEND')}iiif/{IIIF_IMG_VERSION}/"  # cantaloupe container
    )
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", Path(Path(os.getcwd()).parent, "data")))
    SECRET_KEY: Optional[str] = os.getenv("SECRET_KEY")
    # The helper routes under /test (app/test/app_init_endpoints.py) write to the database and the data directory and need no login:
    # they are mounted only when ENABLE_TEST_ROUTES is true (the test suite and a local setup set it; a deployment does not).
    ENABLE_TEST_ROUTES: bool = False

    # local or remote settings
    # TODO: replace 'LOCAL_DEV' with nginx container check
    LOCAL_DEV: bool = False
    if LOCAL_DEV:
        BASE_URL: Optional[str] = "http://localhost"
        APP_BASE_URL: str = f"{BASE_URL}:{os.getenv('APP_PORT')}"
        API_IIIF_IMAGE_LOCAL_PORT: str = re.sub(
            r":.*", "", os.getenv("CANTALOUPE_PORT")
        )
        API_IIIF_IMAGE_PUBLIC: str = (
            f"{BASE_URL}:{API_IIIF_IMAGE_LOCAL_PORT}/iiif/{IIIF_IMG_VERSION}/"
        )
        API_IIIF_PRES: str = f"{APP_BASE_URL}/iiif/pres/"

    else:
        APP_SUBDOMAIN: Optional[str] = os.getenv("APP_SUBDOMAIN")
        BASE_URL: Optional[str] = os.getenv("BASE_URL")
        APP_BASE_URL: str = f"https://{APP_SUBDOMAIN}.{BASE_URL}"
        API_IIIF_IMAGE_PUBLIC: str = (
            f"https://cantaloupe.{BASE_URL}/iiif/{IIIF_IMG_VERSION}/"
        )
        API_IIIF_PRES: str = f"{APP_BASE_URL}/iiif/pres/"


class CeleryConfig(BaseSettings):
    """
    Celery config class.
    """

    broker_url: Optional[str] = os.getenv("CELERY_BROKER_URL")
    result_backend: Optional[str] = os.getenv("CELERY_RESULT_BACKEND")
    imports: List[str] = [
        "src.tasks.etl.task_etl_delete",
        "src.tasks.etl.task_etl_generate_single_manifest",
        "src.tasks.etl.task_etl_generate_manifests",
        "src.tasks.etl.task_etl_itemize",
        "src.tasks.etl.task_etl_load_db",
        "src.tasks.test_tasks",
    ]
    enable_utc: bool = True
    timezone: str = "Europe/Amsterdam"
    task_track_started: bool = True
    result_persistent: bool = True
    task_publish_retry: bool = True
    # The acks_late setting would be used when you need the task to be executed again
    # if the worker (for some reason) crashes mid-execution
    task_acks_late: str = "Enabled"


app_config = Config()
celery_config = CeleryConfig()
