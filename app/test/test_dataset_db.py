"""
Dataset load, read and delete: the Dataset model, the SQL of the dashboard table (real Postgres)
and the Celery tasks that write to it.
"""

import pytest
from src.db.database import (delete_row, get_db_data, insert_row,
                             load_input_dataset, update_dataset_status,
                             update_row)
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
    results = a_transformed_dataset().model_dump()
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


def test_delete_task_removes_the_output_and_resets_the_row(data_dir):
    output = data_dir / "output" / "test_dataset"
    (output / "manifest").mkdir(parents=True)
    insert_row(a_transformed_dataset())

    delete_dataset_task("test_dataset", "test_records.csv")

    assert not output.exists()
    [stored] = get_db_data([FULLNAME])
    assert (stored.status, stored.total, stored.valid) == ("unprocessed", None, None)


# ---------------------------------------------------------------- the values are parameters, not SQL (INFRA-255)

OTHER = "other/bystander.csv"
# the first one makes every row match, the second one ends the statement and starts another one
INJECTIONS = ["a/none.csv' OR '1'='1", "a/none.csv'; DELETE FROM dashboard; --"]
QUOTED = "it's; DROP TABLE dashboard; -- \\ %s %(x)s \"q\"/o'brien.csv"


def a_bystander():
    """
    A processed row no statement about another name may touch
    """
    insert_row(
        Dataset(
            fullname=OTHER,
            dir_name="other",
            mapping="default",
            total=7,
            valid=5,
            valid_img=9,
            status="whatever",
        )
    )
    return get_db_data([OTHER])


@pytest.mark.parametrize("injection", INJECTIONS)
@pytest.mark.parametrize(
    "write",
    [
        lambda name: update_dataset_status(name, "hacked"),
        update_row,
        delete_row,
    ],
    ids=["update_dataset_status", "update_row", "delete_row"],
)
def test_a_name_with_a_quote_changes_that_name_only(write, injection):
    before = a_bystander()
    write(injection)
    assert get_db_data([OTHER]) == before


@pytest.mark.parametrize("injection", INJECTIONS)
def test_reading_a_name_with_a_quote_finds_nothing(injection):
    a_bystander()
    load_input_dataset(an_input_dataset())
    assert get_db_data([injection]) == []
    assert [d.fullname for d in get_db_data([injection, OTHER])] == [OTHER]


@pytest.mark.parametrize("injection", INJECTIONS)
def test_the_status_is_a_value_too(injection):
    before = a_bystander()
    load_input_dataset(an_input_dataset())
    update_dataset_status(FULLNAME, injection)
    assert [d.status for d in get_db_data([FULLNAME])] == [injection]
    assert get_db_data([OTHER]) == before


@pytest.mark.parametrize("injection", INJECTIONS)
@pytest.mark.parametrize(
    "write",
    [
        lambda name: insert_row(
            Dataset(fullname=name, dir_name="a", mapping="default", status="x")
        ),
        lambda name: load_input_dataset(an_input_dataset(name)),
    ],
    ids=["insert_row", "load_input_dataset"],
)
def test_a_name_with_a_quote_is_stored_as_it_is(write, injection):
    before = a_bystander()
    write(injection)
    assert [d.fullname for d in get_db_data([injection])] == [injection]
    assert get_db_data([OTHER]) == before


def test_a_name_with_a_quote_and_a_semicolon_is_plain_text():
    """
    It is stored, read, updated, reset and deleted as the text it is; the table and the other rows are there after
    """
    before = a_bystander()

    load_input_dataset(an_input_dataset(QUOTED, total=2))
    [loaded] = get_db_data([QUOTED])
    assert (loaded.fullname, loaded.dir_name, loaded.total) == (
        QUOTED,
        QUOTED.split("/")[0],
        2,
    )

    update_dataset_status(QUOTED, "in progress")
    assert [d.status for d in get_db_data([QUOTED])] == ["in progress"]

    delete_row(QUOTED)
    insert_row(
        Dataset(
            fullname=QUOTED,
            dir_name=QUOTED.split("/")[0],
            mapping="it's",
            total=1,
            valid=1,
            valid_img=1,
            status="x",
        )
    )
    [inserted] = get_db_data([QUOTED])
    assert (inserted.fullname, inserted.mapping, inserted.status) == (
        QUOTED,
        "it's",
        "processed",
    )

    update_row(QUOTED)
    assert [d.status for d in get_db_data([QUOTED])] == ["unprocessed"]

    delete_row(QUOTED)
    assert get_db_data([QUOTED]) == []
    assert get_db_data([OTHER]) == before


def test_a_quote_in_the_name_of_a_dataset_of_the_dashboard_does_not_break_the_page(
    page_client, data_dir
):
    directory = data_dir / "input" / "o'brien"
    directory.mkdir()
    (directory / "it's data.csv").write_text(
        "dc:identifier,dc:title\nhttp://example.org/1,One\n"
    )

    response = page_client.get("/demo")

    assert response.status_code == 200
    assert [d.status for d in get_db_data(["o'brien/it's data.csv"])] == ["unprocessed"]


def test_none_is_stored_as_null_by_insert_row():
    insert_row(
        Dataset(
            fullname=FULLNAME, dir_name="test_dataset", mapping="default", status="x"
        )
    )
    [stored] = get_db_data([FULLNAME])
    assert (stored.total, stored.valid, stored.valid_img) == (0, None, None)

    delete_row(FULLNAME)
    insert_row(
        Dataset(
            fullname=FULLNAME,
            dir_name="test_dataset",
            mapping="default",
            total=None,
            status="x",
        )
    )
    [stored] = get_db_data([FULLNAME])
    assert (stored.total, stored.valid, stored.valid_img) == (None, None, None)


def test_none_is_stored_as_null_by_load_input_dataset():
    load_input_dataset(an_input_dataset(total=None))
    [stored] = get_db_data([FULLNAME])
    assert (stored.total, stored.valid, stored.valid_img) == (None, None, None)
    assert stored.status == "unprocessed"
