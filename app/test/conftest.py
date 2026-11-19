"""
conftest file for pytest

The suite pins its own configuration BEFORE the app is imported (config.py reads the
environment once, at import time), so that it behaves the same on a laptop, in the
Docker image and in CI:
- Cantaloupe is a double (test/cantaloupe_double.py), started here to know its port;
- Celery uses the in-memory broker and result backend, and a worker runs in a thread
  (see the 'celery_worker' fixture): no RabbitMQ needed, task discovery and
  serialization stay real. A real broker is only checked by test_celery_broker.py;
- Postgres is real (service container in CI): the SQL of the app is built as strings,
  only a real database tells whether it is valid. Connection settings come from the
  environment, with the defaults of the CI service (trust authentication, no password). The app connects to host 'db'
  (hardcoded): PGHOSTADDR makes libpq use the address below and skip the lookup;
- DATA_DIR is left unusable on purpose: tests that touch data use the 'data_dir' fixture.
"""

import os
import shutil
import signal
import sys
from pathlib import Path
from typing import Generator

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = APP_DIR.parent
SAMPLE_INPUT_DIR = REPO_DIR / "setup" / "app" / "input_sample"

# the app resolves 'static', 'templates' and 'src/mappings' relative to the working directory
os.chdir(APP_DIR)

# pylint: disable=wrong-import-position
from test.cantaloupe_double import CantaloupeDouble  # noqa: E402

CANTALOUPE = CantaloupeDouble().start()

TEST_ENV = {
    "SECRET_KEY": "test-secret-key",
    "APP_SUBDOMAIN": "brif",
    "BASE_URL": "example.org",
    "API_IMAGE_BACKEND": CANTALOUPE.base_url,
    "CELERY_BROKER_URL": "memory://",
    "CELERY_RESULT_BACKEND": "cache+memory://",
    "DATA_DIR": "/nonexistent/brif-test-data",
}
DB_DEFAULTS = {
    "DB_NAME": "brif",
    "DB_USER": "brif",
    "DB_PASSWORD": "",  # the Postgres of CI and of scripts/test.sh uses trust authentication
    "PGHOSTADDR": "127.0.0.1",
    "PGPORT": "5432",
}
os.environ.update(TEST_ENV)
for _name, _value in DB_DEFAULTS.items():
    os.environ.setdefault(_name, _value)

from config import app_config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from src.db.database import (close_db_connection,  # noqa: E402
                             init_db_connection)

TEST_TIME_LIMIT_SECONDS = 60


def pytest_sessionfinish(session, exitstatus):  # pylint: disable=unused-argument
    CANTALOUPE.stop()


@pytest.fixture(autouse=True)
def time_limit() -> Generator:
    """
    A test stuck waiting (e.g. for a Celery result) fails after a minute instead of
    blocking the CI job: pytest-timeout is not part of the pinned dependencies.
    """

    def on_alarm(signum, frame):
        raise TimeoutError(f"test still running after {TEST_TIME_LIMIT_SECONDS}s")

    previous = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(TEST_TIME_LIMIT_SECONDS)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, previous)


@pytest.fixture(autouse=True)
def clean_db() -> Generator:
    """
    Every test starts and ends with an empty dashboard and without the scratch tables
    of the test endpoints / tasks (a crashed run must not break the next one).
    """

    def clean():
        conn, cur = init_db_connection()
        cur.execute("TRUNCATE dashboard")
        cur.execute("DROP TABLE IF EXISTS test, test_celery")
        conn.commit()
        close_db_connection(cur, conn)

    clean()
    yield
    clean()


@pytest.fixture(scope="module")
def client() -> Generator:
    """
    Init the FastAPI test client
    :return: the very client
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def page_client() -> Generator:
    """
    A test client that can render the HTML pages. With Starlette 0.14.2 the test client announces
    the 'http.response.template' extension, TemplateResponse then sends a message the
    BaseHTTPMiddleware of main.py does not expect (AssertionError). A browser does not announce it:
    the app is wrapped to do the same. Not needed with a newer Starlette.
    """

    async def without_extensions(scope, receive, send):
        await app(dict(scope, extensions={}), receive, send)

    with TestClient(without_extensions) as test_client:
        yield test_client


@pytest.fixture
def cantaloupe() -> Generator:
    """
    The Cantaloupe double, with all its images available
    """
    CANTALOUPE.requests.clear()
    saved_images = dict(CANTALOUPE.images)
    yield CANTALOUPE
    CANTALOUPE.images.clear()
    CANTALOUPE.images.update(saved_images)


@pytest.fixture
def data_dir(tmp_path, monkeypatch) -> Path:
    """
    An empty data directory (with 'input'), used by the app as DATA_DIR
    """
    (tmp_path / "input").mkdir()
    monkeypatch.setattr(app_config, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def sample_dataset(data_dir) -> Path:
    """
    The 'test_dataset' directory of the sample (3 records, 6 images), copied in the data directory
    :return: the data directory
    """
    shutil.copytree(
        SAMPLE_INPUT_DIR / "test_dataset", data_dir / "input" / "test_dataset"
    )
    return data_dir


@pytest.fixture
def quick_thread_switch() -> Generator:
    """
    The 'check_iiif_pipeline' test endpoint waits for the result of the Celery chain in a
    busy loop, which starves the worker thread (every I/O of the worker waits for the GIL:
    14 s instead of 1 s). A shorter switch interval lets the worker through.
    """
    previous = sys.getswitchinterval()
    sys.setswitchinterval(0.0001)
    yield
    sys.setswitchinterval(previous)


@pytest.fixture(scope="session")
def celery_worker() -> Generator:
    """
    A real Celery worker, in a thread, on the in-memory broker. Ask for it in the tests
    that need tasks to be actually consumed (the tasks are the real ones, found the way
    a worker finds them: through the 'imports' of the Celery config).
    """
    from celery.contrib.testing.worker import start_worker
    from worker import celery

    celery.loader.import_default_modules()
    with start_worker(celery, pool="solo", perform_ping_check=False) as worker:
        yield worker
