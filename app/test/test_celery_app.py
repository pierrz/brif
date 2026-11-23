"""
Celery app: configuration, task discovery and result handling.
Meant to catch what a Celery (or kombu, or Python) upgrade could change silently.
The tasks run in a real worker thread on the in-memory broker (see conftest.py).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from config import celery_config
from src.libs.test_lib import get_expected_results_dict
from src.tasks.test_tasks import check_db_task, dummy_task, init_check_task
from worker import celery

APP_DIR = Path(__file__).resolve().parents[1]

# One name per task of the app. A new task has to be added here, on purpose.
EXPECTED_TASKS = {
    "itemize_dataset",
    "init_check_task",
    "dummy_task",
    "check_db",
    "src.tasks.etl.task_etl_delete.delete_dataset_task",
    "src.tasks.etl.task_etl_generate_manifests.generate_manifests",
    "src.tasks.etl.task_etl_generate_single_manifest.generate_and_write_manifest",
    "src.tasks.etl.task_etl_load_db.load_results_to_db",
}


# ------------------------------------------------------------------ discovery


def test_a_fresh_worker_registers_every_task():
    """
    The worker is started with 'celery --app=worker.celery worker': it only imports 'worker.py',
    the tasks come from the 'imports' of the config. A fresh interpreter tells what it finds
    (in this process the routers have imported all the tasks already).
    """
    code = (
        "import json; from worker import celery; celery.loader.import_default_modules(); "
        "print(json.dumps(sorted(celery.tasks)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=APP_DIR,
        env=os.environ,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    registered = set(json.loads(result.stdout.splitlines()[-1]))
    assert {
        name for name in registered if not name.startswith("celery.")
    } == EXPECTED_TASKS


def test_config_imports_are_the_task_modules():
    assert len(celery_config.imports) == len(set(celery_config.imports))
    assert {task.rsplit(".", 1)[0] for task in EXPECTED_TASKS if "." in task} <= set(
        celery_config.imports
    )


# ------------------------------------------------------------ configuration


def test_broker_and_result_backend_come_from_the_environment():
    assert celery.conf.broker_url == os.environ["CELERY_BROKER_URL"]
    assert celery.conf.result_backend == os.environ["CELERY_RESULT_BACKEND"]


def test_settings_of_the_app():
    conf = celery.conf
    assert conf.enable_utc is True
    assert conf.timezone == "Europe/Amsterdam"
    assert conf.task_track_started is True
    assert conf.result_persistent is True
    assert conf.task_publish_retry is True
    assert (
        conf.task_acks_late
    )  # the value is the string "Enabled", whatever works as True


def test_the_configuration_can_be_listed():
    """
    Flower (worker 'inspect conf') and 'celery inspect conf' read the whole configuration with table() (INFRA-256).
    Handing Celery the settings object itself made it fail: it lists the attributes with dir() and pydantic
    puts a '__signature__' there that raises on an instance.
    """
    table = celery.conf.table(censored=False)
    assert table["broker_url"] == os.environ["CELERY_BROKER_URL"]
    assert table["result_backend"] == os.environ["CELERY_RESULT_BACKEND"]
    assert table["imports"] == celery_config.imports
    assert table["task_acks_late"] == celery_config.task_acks_late
    assert table["timezone"] == "Europe/Amsterdam"
    assert not [name for name in table if name.startswith("__")]


def test_messages_are_json():
    """
    Arguments and results go through JSON: tuples come back as lists (see below)
    """
    conf = celery.conf
    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"
    assert list(conf.accept_content) == ["json"]


def test_every_task_goes_to_the_default_queue():
    """
    The worker of the compose file runs without '-Q': it only consumes the default queue
    """
    assert celery.conf.task_default_queue == "celery"
    for name in EXPECTED_TASKS:
        route = celery.amqp.router.route({}, name)
        assert route["queue"].name == "celery", name


# ------------------------------------------------------------ result handling


def test_a_task_result_comes_back_as_json(celery_worker):
    result = init_check_task.delay("a", 2, ["b"])
    assert result.get(timeout=20) == ["a", 2, ["b"]]  # a tuple in, a list out
    assert result.state == "SUCCESS"


def test_chain_of_tasks_passes_results_and_uses_the_database(celery_worker):
    """
    dummy_task writes a squared number in Postgres, check_db_task reads it back
    """
    result = (dummy_task.s(3) | check_db_task.s()).delay()
    assert {"result": result.get(timeout=20)} == get_expected_results_dict(
        "check_celery"
    )
    assert result.parent.get(timeout=20) == [3, 9]


def test_a_failing_task_ends_in_failure_with_its_error(celery_worker):
    result = check_db_task.delay([3, 9])  # no 'test_celery' table to read
    with pytest.raises(Exception, match="test_celery"):
        result.get(timeout=20)
    assert result.state == "FAILURE"
