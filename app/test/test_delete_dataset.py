"""
Tests for the delete_dataset endpoint restriction.
Only 'test_dataset/test_records.csv' may be deleted.
"""

from fastapi import status


def test_delete_allowed_dataset_succeeds(client):
    """
    Deleting 'test_dataset/test_records.csv' should return a 302 redirect.
    """
    response = client.get("/task/delete_dataset/test_dataset/test_records.csv")
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/demo"


def test_delete_wrong_dataset_name_returns_403(client):
    """
    Deleting a different file under test_dataset should return 403.
    """
    response = client.get("/task/delete_dataset/test_dataset/other.csv")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "test_dataset/test_records.csv" in response.json()["detail"]


def test_delete_wrong_dataset_dir_returns_403(client):
    """
    Deleting a dataset outside test_dataset should return 403.
    """
    response = client.get("/task/delete_dataset/production_dataset/test_records.csv")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "test_dataset/test_records.csv" in response.json()["detail"]
