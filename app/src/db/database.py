"""
All postgres database related code
"""

import psycopg2
from config import app_config


def init_db_connection():
    """
    Init a connection to the DB with psychopg2.
    :return: the connection 2 main elements conn & cur
    """
    # Connect to an existing database
    conn = psycopg2.connect(
        f"dbname={app_config.DB_NAME} user={app_config.DB_USER} host=db password={app_config.DB_PASSWORD}"
    )
    # Open a cursor to perform database operations
    cur = conn.cursor()
    return conn, cur


def close_db_connection(cur, conn):
    """
    Close communication with the database.
    :param cur: psycopg2 connection cursor
    :param conn: psycopg2 connection
    :return: does its thing
    """
    cur.close()
    conn.close()
