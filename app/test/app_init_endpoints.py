"""
All endpoints used for testing purpose. Not included in the documentation
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from src.db.database import close_db_connection  # , delete_row
from src.db.database import init_db_connection
from src.tasks.test_tasks import check_db_task, dummy_task

router = APIRouter(
    prefix="/test",
    tags=["test"],
    responses={404: {"description": "Issue with endpoint"}},
)


@router.get("/api_live", include_in_schema=False)
async def api_live() -> JSONResponse:
    """
    Check if the api is up
    :return: a basic response
    """
    return JSONResponse({"message": "Hello World"})


@router.get("/load_db", include_in_schema=False)
async def load_db() -> JSONResponse:
    """
    Load the DB with dummy data
    :return: a success message response
    """
    conn, cur = init_db_connection()
    cur.execute("CREATE TABLE test (id serial PRIMARY KEY, num integer, data varchar);")
    cur.execute("INSERT INTO test (num, data) VALUES (%s, %s)", (100, "abc'def"))
    conn.commit()
    close_db_connection(cur, conn)

    return JSONResponse({"response_db": "test data loaded"})


@router.get("/read_db", include_in_schema=False)
async def read_db() -> JSONResponse:
    """
    Read previously loaded dummy data from the DB
    :return: the retrieved data as a response
    """
    conn, cur = init_db_connection()
    cur.execute("SELECT * FROM test;")
    data = cur.fetchone()
    close_db_connection(cur, conn)

    return JSONResponse({"response_db": data})


@router.get("/check_celery", include_in_schema=False)
async def check_celery() -> JSONResponse:
    """
    Starts a dummy celery pipeline and retrieves the result from the DB
    :return: the retrieved data as a response
    """
    chain = dummy_task.s(3) | check_db_task.s()
    result = chain()
    task_result = result.get()

    return JSONResponse({"result": task_result})
