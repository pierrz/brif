"""
Dataset load, read and delete: the Dataset model, the SQL of the dashboard table (real Postgres)
and the Celery tasks that write to it.
"""

import psycopg2.errors
import pytest
from src.db.database import (delete_row, get_db_data, insert_row,
                             load_input_dataset, update_dataset_status)
from src.db.models import Dataset, InputDataset
from src.tasks.etl.task_etl_delete import delete_dataset_task
from src.tasks.etl.task_etl_load_db import load_results_to_db

FULLNAME = "test_dataset/test_records.csv"


def an_input_dataset(fullname=FULLNAME, **kwargs):
    dir_name = fullname.split("/")[0]
    return InputDataset(
        fullname=fullname, dir_name=dir_name, mapping="default", **kwargs
    )


def a_transformed_dataset():
    return Dataset(
        fullname=FULLNAME,
        dir_name="test_dataset",
        mapping="default",
        total=3,
        valid=3,
        valid_img=6,
        status="transformed",
    )


# ---------------------------------------------------------------- model


def test_dataset_model_defaults():
    """
    'valid' and 'valid_img' are optional (a dataset is registered before it is processed).
    The order of the fields is the order of the columns of the SQL queries.
    """
    dataset = Dataset(fullname="a/b.csv", dir_name="a", mapping="default", status="x")
    assert (dataset.total, dataset.valid, dataset.valid_img) == (0, None, None)
    assert dataset.field_list() == [
        "fullname",
        "dir_name",
        "mapping",
        "total",
        "valid",
        "valid_img",
        "status",
    ]
    assert an_input_dataset().status == "unprocessed"


# ---------------------------------------------------------------- load, read


def test_load_then_read_an_input_dataset():
    load_input_dataset(an_input_dataset(total=3))
    assert get_db_data([FULLNAME]) == [
        Dataset(
            fullname=FULLNAME,
            dir_name="test_dataset",
            mapping="default",
            total=3,
            valid=None,
            valid_img=None,
            status="unprocessed",
        )
    ]


def test_read_returns_the_requested_datasets_only():
    for name in ("a/one.csv", "a/two.csv", "b/three.csv"):
        load_input_dataset(an_input_dataset(name))
    assert get_db_data([]) == []
    assert get_db_data(["unknown/none.csv"]) == []
    assert sorted(d.fullname for d in get_db_data(["a/one.csv", "b/three.csv"])) == [
        "a/one.csv",
        "b/three.csv",
    ]


def test_insert_row_stores_the_results_of_a_processed_dataset():
    insert_row(a_transformed_dataset())
    [stored] = get_db_data([FULLNAME])
    assert (stored.total, stored.valid, stored.valid_img) == (3, 3, 6)
    assert stored.status == "processed"  # whatever the status given: insert_row decides


def test_update_dataset_status():
    load_input_dataset(an_input_dataset())
    update_dataset_status(FULLNAME, "in progress")
    assert [d.status for d in get_db_data([FULLNAME])] == ["in progress"]


def test_load_results_to_db_replaces_the_previous_results():
    """
    Last step of the pipeline: it can be run again on a dataset already in the dashboard
    """
    load_input_dataset(an_input_dataset(total=3))
    results = a_transformed_dataset().dict()
    load_results_to_db(results)
    load_results_to_db(results)
    [stored] = get_db_data([FULLNAME])
    assert (stored.valid, stored.valid_img, stored.status) == (3, 6, "processed")


# ---------------------------------------------------------------- delete


def test_delete_row_removes_that_dataset_only():
    load_input_dataset(an_input_dataset("a/one.csv"))
    load_input_dataset(an_input_dataset("a/two.csv"))
    delete_row("a/one.csv")
    assert [d.fullname for d in get_db_data(["a/one.csv", "a/two.csv"])] == [
        "a/two.csv"
    ]


def test_delete_task_has_nothing_to_do_when_the_dataset_was_never_processed(data_dir):
    insert_row(a_transformed_dataset())
    delete_dataset_task("test_dataset", "test_records.csv")
    assert [d.fullname for d in get_db_data([FULLNAME])] == [FULLNAME]


@pytest.mark.xfail(
    raises=psycopg2.errors.UndefinedColumn,
    strict=True,
    reason="BUG, not fixed here: update_row() sets the column 'valid_imgs', the table has "
    "'valid_img'. Once the output files are deleted the task fails and the row is not reset. "
    "Remove this mark when update_row() is fixed.",
)
def test_delete_task_removes_the_output_and_resets_the_row(data_dir):
    output = data_dir / "output" / "test_dataset"
    (output / "manifest").mkdir(parents=True)
    insert_row(a_transformed_dataset())

    delete_dataset_task("test_dataset", "test_records.csv")

    assert not output.exists()
    [stored] = get_db_data([FULLNAME])
    assert (stored.status, stored.total, stored.valid) == ("unprocessed", None, None)
