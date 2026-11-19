"""
Tests for the delete_dataset endpoint restriction.
Only 'test_dataset/test_records.csv' may be deleted.
"""

import pytest
from fastapi import status
from src.db.database import get_db_data, load_input_dataset
from src.db.models import InputDataset
from src.routers import tasks as tasks_router


@pytest.fixture
def delete_task_calls(monkeypatch):
    """
    Records the calls to the Celery task instead of publishing them: what the endpoint
    publishes and what a worker does with it are covered in test_celery.py.
    """
    calls = []
    monkeypatch.setattr(
        tasks_router.delete_dataset_task, "delay", lambda *args: calls.append(args)
    )
    return calls


def test_delete_allowed_dataset_succeeds(client, delete_task_calls):
    """
    Deleting 'test_dataset/test_records.csv' should redirect to the dashboard,
    ask the worker to delete the output files and remove the dataset from the dashboard.
    (This test used to expect a 302 on the followed redirect, which could never pass: the
    endpoint returns Starlette's default RedirectResponse, a 307, and the client followed it.)
    """
    fullname = "test_dataset/test_records.csv"
    load_input_dataset(
        InputDataset(fullname=fullname, dir_name="test_dataset", mapping="default")
    )
    assert [d.fullname for d in get_db_data([fullname])] == [fullname]

    response = client.get(
        "/task/delete_dataset/test_dataset/test_records.csv", allow_redirects=False
    )
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == "/demo"
    assert delete_task_calls == [("test_dataset", "test_records.csv")]
    assert get_db_data([fullname]) == []


def test_delete_wrong_dataset_name_returns_403(client, delete_task_calls):
    """
    Deleting a different file under test_dataset should return 403.
    """
    response = client.get("/task/delete_dataset/test_dataset/other.csv")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "test_dataset/test_records.csv" in response.json()["detail"]
    assert delete_task_calls == []


def test_delete_wrong_dataset_dir_returns_403(client, delete_task_calls):
    """
    Deleting a dataset outside test_dataset should return 403.
    """
    response = client.get("/task/delete_dataset/production_dataset/test_records.csv")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "test_dataset/test_records.csv" in response.json()["detail"]
    assert delete_task_calls == []
