"""
The process_dataset endpoint takes a dataset of the dashboard only: a file in a directory of DATA_DIR/input.
The route needs no login and the two names of the URL end up in the Celery chain, in file paths and in the
dashboard table (INFRA-255): whatever is not a dataset is a 404 and nothing is queued.
"""

import os
from urllib.parse import quote

import pytest
from celery import canvas
from fastapi import status
from src.libs.router_lib import find_input_dataset
from src.routers.dashboard import gather_input_datasets

NOT_FOUND = {"detail": "Dataset not found in the input directory."}

# directories and files the dashboard lists: spaces, dots, accents, a quote, a mapping file next to the CSV
LISTED_DATASETS = [
    ("test_dataset", "test_records.csv", False),
    ("with mapping", "records.csv", True),
    ("dots.in.the.dir", "data.v1.2.csv", False),
    ("accents é ü", "résumé 日本.csv", True),
    ("o'brien", "it's data.csv", False),
]
RECORDS = "dc:identifier,dc:title\nhttp://example.org/1,One\n"


def write_dataset(data_dir, dir_name, file_name, mapping=False):
    directory = data_dir / "input" / dir_name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / file_name).write_text(RECORDS, encoding="utf8")
    if mapping:
        (directory / "mapping.json").write_text('{"uri": "dc:identifier"}')


def url_of(dataset_dir, dataset_name):
    return f"/task/process_dataset/{quote(dataset_dir, safe='')}/{quote(dataset_name, safe='')}"


def assert_not_found(client, url):
    response = client.get(url, follow_redirects=False)
    assert response.status_code == 404, url
    assert response.json() == NOT_FOUND, url


@pytest.fixture
def queued_chains(monkeypatch):
    """
    Records the chains the endpoint publishes instead of publishing them (what a worker does with the
    chain is covered by test_iiif_pipeline.py): one list per chain, with the name and the arguments of each task.
    """
    chains = []

    def record(chain, *args, **kwargs):
        chains.append([(task.task, task.args) for task in chain.tasks])

    monkeypatch.setattr(canvas._chain, "apply_async", record)
    return chains


# ---------------------------------------------------------------- the route


@pytest.mark.parametrize("dataset_dir, dataset_name, mapping", LISTED_DATASETS)
def test_a_dataset_of_the_dashboard_is_queued(
    client, data_dir, queued_chains, dataset_dir, dataset_name, mapping
):
    write_dataset(data_dir, dataset_dir, dataset_name, mapping)

    response = client.get(url_of(dataset_dir, dataset_name), follow_redirects=False)

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == "/demo"
    assert [chain[0] for chain in queued_chains] == [
        ("itemize_dataset", (dataset_dir, dataset_name))
    ]
    assert [name for name, _ in queued_chains[0]] == [
        "itemize_dataset",
        "src.tasks.etl.task_etl_generate_manifests.generate_manifests",
        "src.tasks.etl.task_etl_load_db.load_results_to_db",
    ]


def test_every_dataset_the_dashboard_lists_can_be_processed(
    client, data_dir, queued_chains
):
    for dataset_dir, dataset_name, mapping in LISTED_DATASETS:
        write_dataset(data_dir, dataset_dir, dataset_name, mapping)

    names, _ = gather_input_datasets(data_dir / "input")

    assert sorted(names) == sorted(f"{d}/{n}" for d, n, _ in LISTED_DATASETS)
    for fullname in names:
        dataset_dir, dataset_name = fullname.split("/")
        response = client.get(url_of(dataset_dir, dataset_name), follow_redirects=False)
        assert response.status_code == 307, fullname
    assert len(queued_chains) == len(LISTED_DATASETS)


def test_an_unknown_dataset_is_a_404_and_nothing_is_queued(
    client, sample_dataset, queued_chains
):
    for url in (
        "/task/process_dataset/test_dataset/unknown.csv",
        "/task/process_dataset/unknown_dir/test_records.csv",
        "/task/process_dataset/test_dataset/test_records.CSV",
        # the name of a directory is not a dataset
        "/task/process_dataset/test_dataset/test_dataset",
        "/task/process_dataset/input/test_dataset",
    ):
        assert_not_found(client, url)
    assert queued_chains == []


@pytest.mark.parametrize(
    "dataset_name",
    [
        "x.csv' OR '1'='1",
        "x.csv'; DELETE FROM dashboard; --",
        "test_records.csv' --",
    ],
)
def test_a_name_with_a_quote_is_a_404_and_nothing_is_queued(
    client, sample_dataset, queued_chains, dataset_name
):
    assert_not_found(client, url_of("test_dataset", dataset_name))
    assert queued_chains == []


def test_a_dot_dot_is_a_404_even_when_the_file_it_designates_exists(
    client, sample_dataset, queued_chains
):
    """
    '%2e%2e' reaches the route as '..' (the test client collapses a literal '..' in a URL before sending it, which
    makes it a route that does not exist: the helper is tested with '..' in test_find_input_dataset below).
    The files exist: 'secret.csv' next to the input directory, 'test_records.csv' in the input directory itself.
    """
    (sample_dataset / "secret.csv").write_text(RECORDS)
    (sample_dataset / "input" / "test_records.csv").write_text(RECORDS)

    for url in (
        "/task/process_dataset/%2e%2e/secret.csv",
        "/task/process_dataset/%2E%2E/secret.csv",
        "/task/process_dataset/test_dataset/%2e%2e",
        "/task/process_dataset/%2e%2e/%2e%2e",
        "/task/process_dataset/%2e/test_records.csv",  # directly in the input directory: no dataset
    ):
        assert_not_found(client, url)

    # an encoded slash is a slash for the router: three segments, no route
    response = client.get(
        "/task/process_dataset/test_dataset/%2e%2e%2ftest_records.csv",
        follow_redirects=False,
    )
    assert (response.status_code, response.json()) == (404, {"detail": "Not Found"})
    assert queued_chains == []


def test_a_null_byte_is_a_404(client, sample_dataset, queued_chains):
    assert_not_found(client, "/task/process_dataset/test_dataset/test_records.csv%00")
    assert queued_chains == []


def test_a_symbolic_link_that_leaves_the_input_directory_is_a_404(
    client, sample_dataset, queued_chains
):
    outside = sample_dataset / "outside"
    outside.mkdir()
    (outside / "secret.csv").write_text(RECORDS)
    os.symlink(
        outside / "secret.csv", sample_dataset / "input" / "test_dataset" / "link.csv"
    )
    os.symlink(outside, sample_dataset / "input" / "linked_dir")

    assert_not_found(client, url_of("test_dataset", "link.csv"))
    assert_not_found(client, url_of("linked_dir", "secret.csv"))
    assert queued_chains == []


# ---------------------------------------------------------------- the helper


def test_find_input_dataset_returns_the_file(sample_dataset):
    found = find_input_dataset("test_dataset", "test_records.csv")
    assert (
        found
        == (sample_dataset / "input" / "test_dataset" / "test_records.csv").resolve()
    )
    assert found.is_file()


@pytest.mark.parametrize("dataset_dir, dataset_name, mapping", LISTED_DATASETS)
def test_find_input_dataset_finds_what_the_dashboard_lists(
    data_dir, dataset_dir, dataset_name, mapping
):
    write_dataset(data_dir, dataset_dir, dataset_name, mapping)
    assert find_input_dataset(dataset_dir, dataset_name).name == dataset_name


@pytest.mark.parametrize(
    "dataset_dir, dataset_name",
    [
        ("test_dataset", "missing.csv"),
        ("missing", "test_records.csv"),
        ("input", "test_dataset"),
        ("test_dataset", "test_dataset"),  # a directory
        ("", "test_records.csv"),
        ("test_dataset", ""),
        ("..", "secret.csv"),  # outside, next to 'input'
        ("..", "input"),
        ("test_dataset", ".."),
        ("test_dataset", "."),
        (".", "test_records.csv"),  # directly in the input directory
        (".", "stray.csv"),
        (
            "test_dataset",
            "../test_dataset/test_records.csv",
        ),  # a real dataset by another name
        ("test_dataset/..", "test_dataset"),
        ("../input/test_dataset", "test_records.csv"),
        ("test_dataset/", "test_records.csv"),
        ("/", "etc"),
        ("/etc", "passwd"),
        ("test_dataset", "/etc/passwd"),
        ("test_dataset", "test_records.csv\x00.png"),
        ("test_dataset\x00", "test_records.csv"),
        ("test_dataset", "n" * 5000),
        ("d" * 5000, "test_records.csv"),
    ],
)
def test_find_input_dataset_returns_none_for_what_is_not_a_dataset(
    sample_dataset, dataset_dir, dataset_name
):
    (sample_dataset / "secret.csv").write_text(RECORDS)
    (sample_dataset / "input" / "stray.csv").write_text(RECORDS)
    assert find_input_dataset(dataset_dir, dataset_name) is None


def test_find_input_dataset_follows_a_symbolic_link_inside_the_input_directory_only(
    sample_dataset,
):
    dataset_dir = sample_dataset / "input" / "test_dataset"
    outside = sample_dataset / "outside.csv"
    outside.write_text(RECORDS)
    os.symlink(dataset_dir / "test_records.csv", dataset_dir / "inside.csv")
    os.symlink(outside, dataset_dir / "outside.csv")
    os.symlink("loop_b.csv", dataset_dir / "loop_a.csv")
    os.symlink("loop_a.csv", dataset_dir / "loop_b.csv")

    assert find_input_dataset("test_dataset", "inside.csv") is not None
    assert find_input_dataset("test_dataset", "outside.csv") is None
    assert find_input_dataset("test_dataset", "loop_a.csv") is None


def test_find_input_dataset_returns_none_without_an_input_directory():
    # DATA_DIR is a directory that does not exist (conftest.py)
    assert find_input_dataset("test_dataset", "test_records.csv") is None
