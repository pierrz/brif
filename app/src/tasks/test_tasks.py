"""
Test related Celery tasks
"""

from typing import List, Union

import numpy as np
from src.db.database import close_db_connection, init_db_connection
from worker import celery, logger


@celery.task(name="init_check_task")
def init_check_task(*args):
    """
    Checks whether Celery receives what is expected to
    :param args: some args
    :return: the 1st 2 args (why not ...)
    """
    logger.info("This comes in : %s", args)
    for arg_el in args:
        logger.info("- '%s'", arg_el)
    return args


@celery.task(name="dummy_task")
def dummy_task(input_int: int) -> List[int]:
    """
    Dummy numpy task
    :param input_int: input number
    :return: list with input number & computed result
    """
    result = int(np.multiply(input_int, input_int))
    logger.info("=> Calculated: %s", result)

    conn, cur = init_db_connection()
    cur.execute(
        "CREATE TABLE test_celery (id serial PRIMARY KEY, input integer, result integer);"
    )
    cur.execute(
        f"INSERT INTO test_celery (input, result) VALUES ({input_int}, {result});"
    )
    conn.commit()

    logger.info(f"=> Database loaded: {result}")
    close_db_connection(cur, conn)

    return [input_int, result]


@celery.task(name="check_db")
def check_db_task(io_pack: List[int]) -> Union[List[Union[str, int]], bool]:
    """
    Checks whether the DB was properly loaded from a previous task
    :param io_pack: list gathering the input for the task (celery works better like that)
    :return: a 'success' tuple or boolean False, depending
    """
    input_int, result = io_pack

    conn, cur = init_db_connection()
    cur.execute("SELECT * FROM test_celery;")
    db_input, db_result = cur.fetchone()[1:]

    # drop celery test table
    cur.execute("DROP TABLE test_celery;")
    conn.commit()

    close_db_connection(cur, conn)
    logger.info("=> Retrieved from DB: [%s, %s]", db_input, db_result)

    if (db_input, db_result) == (input_int, result):
        return ["success", input_int, result]

    return False
