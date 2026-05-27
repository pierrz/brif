"""
Tests for the delete_dataset endpoint restriction.
Only datasets under 'test_dataset' may be deleted.
"""

from fastapi import status


def test_delete_test_dataset_succeeds(client):
    """
    Deleting a dataset under 'test_dataset' should return a 302 redirect.
    """
    response = client.get("/task/delete_dataset/test_dataset/test_records.csv")
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/demo"


def test_delete_non_test_dataset_returns_403(client):
    """
    Deleting any dataset other than 'test_dataset' should return 403 Forbidden.
    """
    response = client.get("/task/delete_dataset/production_dataset/data.csv")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "test_dataset" in response.json()["detail"]
