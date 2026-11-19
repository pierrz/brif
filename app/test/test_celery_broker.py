"""
The app publishes to a real RabbitMQ. Everything else in the suite uses the in-memory broker,
so this is the one check of the AMQP side (kombu / py-amqp / broker URL), which is what a Celery
upgrade is most likely to break. It runs when BRIF_TEST_AMQP_URL is set (a RabbitMQ service
container in CI) and is skipped otherwise.
"""

import os
import time
import uuid

import pytest
from worker import celery

AMQP_URL = os.getenv("BRIF_TEST_AMQP_URL")

pytestmark = pytest.mark.skipif(
    not AMQP_URL, reason="BRIF_TEST_AMQP_URL is not set (no RabbitMQ to talk to)"
)


def ready_messages(channel, queue, expected, timeout=10.0):
    """
    The publish goes out on the producer's channel and the count is read on another one: the broker may
    not have routed the message yet when the first read happens (it failed on the first push to main).
    Read again until the expected number is there or the timeout is over, and return what was last seen.
    """
    deadline = time.monotonic() + timeout
    while True:
        count = channel.queue_declare(queue, passive=True).message_count
        if count >= expected or time.monotonic() >= deadline:
            return count
        time.sleep(0.1)


def test_a_task_message_reaches_the_queue_of_a_real_rabbitmq():
    queue = f"brif-test-{uuid.uuid4().hex}"
    with celery.connection_for_write(AMQP_URL) as connection:
        connection.ensure_connection(max_retries=3)
        celery.send_task("dummy_task", args=[2], queue=queue, connection=connection)

        channel = connection.default_channel
        try:
            assert ready_messages(channel, queue, expected=1) == 1
        finally:
            channel.queue_delete(queue)
