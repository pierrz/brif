"""
The IIIF manifest pipeline (itemize => manifests => dashboard), from the sample CSV to the manifests
served by the API, against a Cantaloupe double (see test/cantaloupe_double.py).
The expected manifest is the one of the 'check_iiif_pipeline' fixture, from a real Cantaloupe.
"""

import json
import time

from config import app_config
from src.db.database import get_db_data, load_input_dataset
from src.db.models import InputDataset
from src.libs.main_lib import load_json
from src.libs.test_lib import get_expected_results_dict
from src.tasks.etl.task_etl_generate_manifests import generate_manifests
from src.tasks.etl.task_etl_itemize import itemize

DATASET_DIR, DATASET_NAME = "test_dataset", "test_records.csv"
FULLNAME = f"{DATASET_DIR}/{DATASET_NAME}"
NIGHT = "kokoelmat_fng_fi_app_si_A_V_4460"  # the 3rd record of the sample


def expected_night_manifest():
    fixture = json.dumps(get_expected_results_dict("check_iiif_pipeline"))
    fixture = fixture.replace("<APP_BASE_URL>", app_config.APP_BASE_URL)
    return json.loads(
        fixture.replace("<API_IIIF_IMAGE_PUBLIC>", app_config.API_IIIF_IMAGE_PUBLIC)
    )


def output_dir():
    return app_config.DATA_DIR / "output" / DATASET_DIR


def wait_for_status(status, seconds=30):
    """
    The row of the dataset, once the pipeline running in the worker has given it that status
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        rows = get_db_data([FULLNAME])
        if rows and rows[0].status == status:
            return rows[0]
        time.sleep(0.1)
    raise AssertionError(
        f"'{FULLNAME}' did not get the status '{status}': {get_db_data([FULLNAME])}"
    )


# ---------------------------------------------------------------- step 1: itemize


def test_itemize_writes_one_json_file_per_record(sample_dataset):
    load_input_dataset(
        InputDataset(fullname=FULLNAME, dir_name=DATASET_DIR, mapping="default")
    )

    assert itemize(DATASET_DIR, DATASET_NAME) == (DATASET_DIR, DATASET_NAME)

    files = sorted((output_dir() / "split").iterdir())
    assert [f.name for f in files] == [
        "http___kokoelmat_fng_fi_app_si_A_V_4460.json",
        "http___kokoelmat_fng_fi_app_si_N_1998_22.json",
        "http___kokoelmat_fng_fi_app_si_N_2010_68.json",
    ]
    record = load_json(files[1])
    assert (record["dc:title"], record["dc:relation"]) == ("Untitled", "N9354201")
    assert [d.status for d in get_db_data([FULLNAME])] == ["in progress"]


# ---------------------------------------------------------------- step 2: manifests


def run_itemize_and_manifests():
    return generate_manifests(itemize(DATASET_DIR, DATASET_NAME))


def test_generate_manifests_builds_the_manifests_with_the_image_sizes(
    sample_dataset, cantaloupe
):
    results = run_itemize_and_manifests()

    assert results == {
        "fullname": FULLNAME,
        "dir_name": DATASET_DIR,
        "total": 3,
        "valid": 3,
        "valid_img": 6,
        "mapping": "default",
        "status": "transformed",
    }
    manifests = output_dir() / "manifest"
    assert sorted(p.name for p in manifests.iterdir()) == [
        "collection",
        "kokoelmat_fng_fi_app_si_A_V_4460",
        "kokoelmat_fng_fi_app_si_N_1998_22",
        "kokoelmat_fng_fi_app_si_N_2010_68",
    ]
    assert load_json(manifests / NIGHT / "manifest.json") == expected_night_manifest()
    collection = load_json(manifests / "collection" / "collection_manifest.json")
    assert len(collection["manifests"]) == 3
    # every image of the 3 records was looked up on the image server
    assert "/iiif/2/test_dataset%2FN0062500/info.json" in cantaloupe.requests


def test_images_missing_on_the_image_server_are_skipped(sample_dataset, cantaloupe):
    del cantaloupe.images["test_dataset/N9354200"]
    del cantaloupe.images["test_dataset/N9354203"]

    results = run_itemize_and_manifests()

    assert (results["valid"], results["valid_img"]) == (3, 4)


# ---------------------------------------------------------------- the whole chain, then the API


def test_processing_a_dataset_through_the_endpoint_fills_the_dashboard_and_the_api(
    client, sample_dataset, cantaloupe, celery_worker
):
    response = client.get(f"/task/process_dataset/{FULLNAME}", follow_redirects=False)
    assert response.headers["location"] == "/demo"

    processed = wait_for_status("processed")
    assert (processed.total, processed.valid, processed.valid_img) == (3, 3, 6)
    assert processed.mapping == "default"

    api = f"/iiif/pres/{DATASET_DIR}"
    manifest = client.get(f"{api}/{NIGHT}/manifest.json")
    assert manifest.status_code == 200
    assert manifest.json() == expected_night_manifest()
    collection = client.get(f"{api}/collection/collection_manifest.json")
    assert len(collection.json()["manifests"]) == 3
    canvas = client.get(f"{api}/{NIGHT}/canvas/canvas-1.json")
    assert (canvas.json()["height"], canvas.json()["width"]) == (3604, 2000)


def test_the_api_has_no_manifest_for_a_dataset_not_processed(client, data_dir):
    for path in (
        f"/iiif/pres/{DATASET_DIR}/{NIGHT}/manifest.json",
        f"/iiif/pres/{DATASET_DIR}/collection/collection_manifest.json",
        f"/iiif/pres/{DATASET_DIR}/{NIGHT}/canvas/canvas-1.json",
    ):
        response = client.get(path)
        assert (response.status_code, response.json()) == (
            404,
            {"error": "Manifest not found"},
        ), path
