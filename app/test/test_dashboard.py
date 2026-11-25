"""
The dashboard: it walks DATA_DIR/input, registers each dataset (a CSV file in a directory) in
the 'dashboard' table and lists them with the action that fits their status.
"""

import json

from src.db.database import get_db_data, insert_row, load_input_dataset
from src.db.models import Dataset, InputDataset
from src.routers.dashboard import gather_input_datasets, sync_datasets_with_db
from src.tasks.etl.task_etl_delete import delete_dataset_task

FULLNAME = "test_dataset/test_records.csv"
RECORDS_HEADER = "dc:identifier,dc:title\n"


def write_dataset(data_dir, dir_name, file_name, records=2, mapping=False):
    directory = data_dir / "input" / dir_name
    directory.mkdir(parents=True, exist_ok=True)
    rows = "".join(f"http://example.org/{n},Record {n}\n" for n in range(records))
    (directory / file_name).write_text(RECORDS_HEADER + rows, encoding="utf8")
    if mapping:
        (directory / "mapping.json").write_text(json.dumps({"uri": "dc:identifier"}))


# ---------------------------------------------------------------- walking the input directory


def test_the_sample_dataset_is_found_with_its_record_count(sample_dataset):
    names, datasets = gather_input_datasets(sample_dataset / "input")
    assert names == [FULLNAME]
    assert datasets == [
        InputDataset(
            fullname=FULLNAME,
            dir_name="test_dataset",
            mapping="default",
            total=3,
            status="unprocessed",
        )
    ]


def test_each_csv_file_of_each_directory_is_a_dataset(data_dir):
    write_dataset(data_dir, "first", "one.csv", records=4)
    write_dataset(data_dir, "second", "two.csv", records=1)
    names, datasets = gather_input_datasets(data_dir / "input")
    assert sorted(names) == ["first/one.csv", "second/two.csv"]
    assert {d.fullname: d.total for d in datasets} == {
        "first/one.csv": 4,
        "second/two.csv": 1,
    }


def test_a_mapping_file_makes_the_mapping_provided_and_is_not_a_dataset(data_dir):
    write_dataset(data_dir, "with_mapping", "data.csv", mapping=True)
    write_dataset(data_dir, "without_mapping", "data.csv")
    names, datasets = gather_input_datasets(data_dir / "input")
    assert sorted(names) == ["with_mapping/data.csv", "without_mapping/data.csv"]
    assert {d.dir_name: d.mapping for d in datasets} == {
        "with_mapping": "provided",
        "without_mapping": "default",
    }


def test_files_directly_in_the_input_directory_are_not_datasets(data_dir):
    (data_dir / "input" / "stray.csv").write_text(RECORDS_HEADER)
    assert gather_input_datasets(data_dir / "input") == ([], [])


# ---------------------------------------------------------------- syncing with the database


def test_new_datasets_are_registered_once_as_unprocessed(sample_dataset):
    names, datasets = gather_input_datasets(sample_dataset / "input")
    sync_datasets_with_db(names, datasets)
    sync_datasets_with_db(names, datasets)
    [stored] = get_db_data(names)
    assert (stored.fullname, stored.status, stored.total) == (
        FULLNAME,
        "unprocessed",
        3,
    )


def test_known_datasets_keep_their_status_and_results(sample_dataset):
    insert_row(
        Dataset(
            fullname=FULLNAME,
            dir_name="test_dataset",
            mapping="default",
            total=3,
            valid=3,
            valid_img=6,
            status="whatever",
        )
    )
    names, datasets = gather_input_datasets(sample_dataset / "input")
    sync_datasets_with_db(names, datasets)
    [stored] = get_db_data(names)
    assert (stored.status, stored.valid, stored.valid_img) == ("processed", 3, 6)


# ---------------------------------------------------------------- the page


def test_page_lists_a_new_dataset_with_the_process_action(page_client, sample_dataset):
    response = page_client.get("/demo")
    assert response.status_code == 200
    page = response.text
    assert FULLNAME in page
    assert "unprocessed" in page
    assert f'href="/task/process_dataset/{FULLNAME}"' in page
    assert "/task/delete_dataset/" not in page
    assert [d.status for d in get_db_data([FULLNAME])] == ["unprocessed"]


def test_page_lists_a_processed_dataset_with_its_apis_and_the_delete_action(
    page_client, sample_dataset
):
    insert_row(
        Dataset(
            fullname=FULLNAME,
            dir_name="test_dataset",
            mapping="default",
            total=3,
            valid=3,
            valid_img=6,
            status="processed",
        )
    )
    page = page_client.get("/demo").text
    assert "/iiif/pres/test_dataset/collection/collection_manifest.json" in page
    assert "/iiif/pres/test_dataset/image_api_example" in page
    assert (
        '<a href="/iiif/pres/test_dataset/manifest_api_example_view">viewer</a>' in page
    )
    assert ">view</a>" not in page
    assert f'href="/task/delete_dataset/{FULLNAME}"' in page
    assert "/task/process_dataset/" not in page


def test_page_offers_to_process_a_dataset_again_once_its_output_is_deleted(
    page_client, sample_dataset
):
    (sample_dataset / "output" / "test_dataset" / "manifest").mkdir(parents=True)
    insert_row(
        Dataset(
            fullname=FULLNAME,
            dir_name="test_dataset",
            mapping="default",
            total=3,
            valid=3,
            valid_img=6,
            status="processed",
        )
    )
    delete_dataset_task("test_dataset", "test_records.csv")
    response = page_client.get("/demo")
    assert response.status_code == 200
    assert f'href="/task/process_dataset/{FULLNAME}"' in response.text
    assert "/task/delete_dataset/" not in response.text


def test_page_does_not_list_datasets_that_are_gone_from_the_input_directory(
    page_client, data_dir
):
    load_input_dataset(
        InputDataset(fullname=FULLNAME, dir_name="test_dataset", mapping="default")
    )
    assert FULLNAME not in page_client.get("/demo").text
