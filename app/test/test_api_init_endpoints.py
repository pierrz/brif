"""
Core test module with a dedicated test base class
"""

from test.test_base import (EndpointCantaloupeTest, EndpointPipelineTest,
                            EndpointTestBase)

from fastapi.testclient import TestClient


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
    (loads the data first, the 'clean_db' fixture drops the table afterwards)
    :param client: current FastAPI test client
    :return: does its thing
    """
    EndpointTestBase(client, "load_db")
    EndpointTestBase(client, "read_db")


def test_endpoint_check_cantaloupe(client: TestClient, cantaloupe):
    """
    Test if the app reads the expected 'info.json' from the image server.
    The image server is a double (a real Cantaloupe answered erratically, and the
    test was skipped anyway: 'LOCAL_DEV' is hardcoded to False in config.py).
    :param client: current FastAPI test client
    :param cantaloupe: the Cantaloupe double
    :return: does its thing
    """
    EndpointCantaloupeTest(client)
    assert cantaloupe.requests == ["/iiif/2/test_dataset%2FN9354201/info.json"]


def test_endpoint_check_iiif_pipeline(
    client: TestClient, sample_dataset, cantaloupe, celery_worker, quick_thread_switch
):
    """
    Test the core pipeline features by triggering a Celery chain and check the transformed file.
    The tasks run in a real worker (thread, in-memory broker), the images come from a Cantaloupe double.
    :param client: current FastAPI test client
    :param sample_dataset: data directory with the sample dataset as input
    :param cantaloupe: the Cantaloupe double
    :param celery_worker: a running Celery worker
    :param quick_thread_switch: lets the worker thread through the busy loop of the endpoint
    :return: does its thing
    """
    EndpointPipelineTest(client)
