"""
All endpoints used for testing purpose. Not included in the documentation
"""
import shutil
from pathlib import Path

from config import app_config
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from src.db.database import close_db_connection, delete_row, init_db_connection
from src.libs.main_lib import fetch_json_from_url, load_json
from src.libs.router_lib import init_iiif_pipeline_lite

router = APIRouter(
    prefix="/test",
    tags=["test"],
    responses={404: {"description": "Issue with endpoint"}},
)


@router.get("/check_cantaloupe", include_in_schema=False)
async def check_cantaloupe() -> JSONResponse:
    """
    Checks whether Cantaloupe is up and returning the expected JSON manifest
    :return: a JSON manifest
    """

    # TODO: use the the live url and not the container route
    # url = f"{app_config.API_IIIF_IMAGE_PUBLIC}test_dataset%2FN9354201/info.json"
    url = (
        f"{app_config.API_IIIF_IMAGE}test_dataset%2FN9354201/info.json"  # docker route
    )
    json_data = fetch_json_from_url(url)
    return JSONResponse(json_data)


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


@router.get("/check_iiif_pipeline", include_in_schema=False)
async def check_iiif_pipeline() -> JSONResponse:
    """
    Starts a transformation pipeline and retrieves the transformed file
    :return: either an error or the transformed JSON manifest
    """
    print("start test pipeline ...")
    dataset_dir = "test_dataset"
    dataset_name = "test_records.csv"
    pipeline = init_iiif_pipeline_lite(dataset_dir, dataset_name)

    check = pipeline.ready()
    while check is False:
        check = pipeline.ready()

    test_filepath = Path(
        app_config.DATA_DIR,
        "output/test_dataset/manifest/kokoelmat_fng_fi_app_si_A_V_4460/manifest.json",
    )
    if test_filepath.exists():
        data = load_json(test_filepath)
        # remove transformed data & clean db
        delete_row(f"{dataset_dir}/{dataset_name}")
        shutil.rmtree(Path(app_config.DATA_DIR, "output", dataset_dir))
        print("Pipeline job succeeded.")
        return JSONResponse(data)

    return JSONResponse({"response": "error with the pipeline ..."})
