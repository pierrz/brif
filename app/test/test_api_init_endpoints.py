"""
Core test module with a dedicated test base class
"""

from test.test_base import EndpointTestBase

from fastapi.testclient import TestClient
from src.db.database import close_db_connection, init_db_connection


def test_endpoint_check_api_live(client: TestClient):
    """
    Test if the api is up
    :param client: current FastAPI test client
    :return: does its thing
    """
    EndpointTestBase(client, "api_live")


def test_endpoint_check_load_db(client: TestClient):
    """
    Test if the the DB can be loaded with data
    :param client: current FastAPI test client
    :return: does its thing
    """
    EndpointTestBase(client, "load_db")


def test_endpoint_check_read_db(client: TestClient):
    """
    Test if data can be retrieved from the DB
    :param client: current FastAPI test client
    :return: does its thing
    """
    EndpointTestBase(client, "read_db")

    # clean db after load/reads
    conn, cur = init_db_connection()
    cur.execute("DROP TABLE test;")
    conn.commit()
    close_db_connection(cur, conn)


def test_endpoint_check_celery(client: TestClient):
    """
    Test if Celery is connected and can run a data pipeline
    :param client: current FastAPI test client
    :return: does its thing
    """
    EndpointTestBase(client, "check_celery")
