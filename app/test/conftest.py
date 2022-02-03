"""
conftest file for pytest
"""

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture(scope="module")
def client() -> Generator:
    """
    Init the FastAPI test client
    :return: the very client
    """
    with TestClient(app) as test_client:
        yield test_client
