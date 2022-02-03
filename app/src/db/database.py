"""
All postgres database related code
"""

import psycopg2
from config import app_config
from src.db.models import Dataset, dataset_from_dict

fields = Dataset(
    fullname="tmp", dir_name="tmp", mapping="tmp", status="tmp"
).field_list()
columns = str(fields)[1:-1].replace("'", "")


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


def prepare_dashboard_table():
    """
    Create the table for the dashboard logistics
    :return:  does its thing
    """
    conn, cur = init_db_connection()
    cur.execute(
        """CREATE TABLE dashboard (
        id serial PRIMARY KEY,
        fullname varchar,
        dir_name varchar,
        mapping varchar,
        total integer,
        valid integer,
        valid_img integer,
        status varchar
        );"""
    )
    conn.commit()
    close_db_connection(cur, conn)


def insert_row(dataset: Dataset):
    conn, cur = init_db_connection()
    cur.execute(
        query=f"""INSERT INTO dashboard ({columns})
                        VALUES ('{dataset.fullname}',
                                '{dataset.dir_name}',
                                '{dataset.mapping}',
                                {dataset.total},
                                {dataset.valid},
                                {dataset.valid_img},
                                'processed'
                        );"""
    )
    conn.commit()
    close_db_connection(cur, conn)


def load_input_dataset(dataset: Dataset):
    conn, cur = init_db_connection()
    cur.execute(
        query=f"INSERT INTO dashboard (fullname, dir_name, total, mapping, status) VALUES ('{dataset.fullname}', '{dataset.dir_name}', '{dataset.total}', '{dataset.mapping}', '{dataset.status}');"
    )
    conn.commit()
    close_db_connection(cur, conn)


def update_row(dataset_fullname):
    conn, cur = init_db_connection()
    cur.execute(
        f"""UPDATE dashboard
        SET total = null
        SET valid = null
        SET valid_imgs = null
        SET status = 'unprocessed'
        WHERE fullname = '{dataset_fullname}'"""
    )
    conn.commit()
    close_db_connection(cur, conn)


def update_dataset_status(dataset_fullname: str, status: str):
    conn, cur = init_db_connection()
    cur.execute(
        f"""UPDATE dashboard
        SET status = '{status}'
        WHERE fullname = '{dataset_fullname}'"""
    )
    conn.commit()
    close_db_connection(cur, conn)


def delete_row(dataset_fullname):
    conn, cur = init_db_connection()
    cur.execute(f"DELETE FROM dashboard WHERE fullname = '{dataset_fullname}'")
    conn.commit()
    close_db_connection(cur, conn)


def get_db_data(datasets_list):

    query_str = str()
    for idx, dataset in enumerate(datasets_list):
        if idx == 0:
            query_str += f"fullname = '{dataset}'"
        else:
            query_str += f" OR fullname = '{dataset}'"

    full_query = f"SELECT {columns} FROM dashboard WHERE {query_str};"
    conn, cur = init_db_connection()
    cur.execute(full_query)
    data = cur.fetchall()
    close_db_connection(cur, conn)

    prepared_data = [dataset_from_dict(dict(zip(fields, row))) for row in data]
    return prepared_data
