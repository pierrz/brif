"""
Core test module with a dedicated test base class
"""

from test.test_base import (EndpointCantaloupeTest, EndpointPipelineTest,
                            EndpointTestBase)

import pytest
from config import app_config
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


@pytest.mark.skipif(
    not app_config.LOCAL_DEV,
    reason="skipped in prod (erratic issue when connecting to Cantaloupe)",
)
def test_endpoint_check_cantaloupe(client: TestClient):
    """
    Test if Cantaloupe is connected and returns the expect data.
    Skipped in prod due to an erratic issue when connecting to Cantaloupe (sometimes passes, sometimes not).
    Not critical as the connection with Cantaloupe is tested in 'test_endpoint_check_iiif_pipeline'
    :param client: current FastAPI test client
    :return: does its thing
    """
    EndpointCantaloupeTest(client)


def test_endpoint_check_iiif_pipeline(client: TestClient):
    """
    Test the core pipeline features by triggering a Celery chain and check the transformed file
    :param client: current FastAPI test client
    :return: does its thing
    """
    EndpointPipelineTest(client)
