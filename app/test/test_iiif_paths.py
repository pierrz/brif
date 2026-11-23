"""
The routes of the IIIF API turn the names of their URL into file paths (INFRA-258): the mapping of a dataset (input),
the manifests, the sub-levels and the collection of a dataset (output) and the three example routes. They need no login.
Each of them asks find_in_dataset() first: every name must be a plain name and the path, symbolic links resolved, must stay
inside the directory of the dataset, otherwise the answer is a 404 that says nothing about the input.
Before that '/iiif/pres/%2e%2e/mapping' answered DATA_DIR/mapping.json, a file outside the dataset.
"""

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import quote

import httpx2
import pytest
from main import app
from src.libs.router_lib import find_in_dataset
from src.tasks.etl.task_etl_generate_manifests import generate_manifests
from src.tasks.etl.task_etl_itemize import itemize

DATASET_DIR, DATASET_NAME = "test_dataset", "test_records.csv"
NIGHT = "kokoelmat_fng_fi_app_si_A_V_4460"  # the 3rd record of the sample
API = "/iiif/pres"
OUTSIDE = "OUTSIDE"  # in every file a route must not read: it is in no answer

# what a route says when it refuses, or does not find, something: nothing of what was asked
MANIFEST_NOT_FOUND = {"error": "Manifest not found"}
DATASET_NOT_FOUND = {"error": "Dataset not found"}
NO_ROUTE = {"detail": "Not Found"}

# the headers of an answer to a client that does not compress (the other ones are tested in test_app_wiring.py)
JSON_HEADERS = {"content-type": "application/json", "vary": "Accept-Encoding, Origin"}


def rendered(path):
    """
    What a route answers for a JSON file: its data, rendered the way JSONResponse does
    """
    data = json.loads(Path(path).read_text(encoding="utf8"))
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf8")


def get(client, url):
    return client.get(
        url, follow_redirects=False, headers={"Accept-Encoding": "identity"}
    )


def get_like_a_server(url):
    """
    GET through the app with the path decoded once, as uvicorn does. The Starlette test client decodes it twice
    ('%252e%252e' reaches a route as '..'), so it cannot tell a name that is decoded twice from one that is not.
    An error inside the app is a 500 here, not an exception.
    """

    async def request():
        transport = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx2.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as server:
            return await server.get(
                url, follow_redirects=False, headers={"Accept-Encoding": "identity"}
            )

    return asyncio.run(request())


def assert_nothing_outside(response):
    assert OUTSIDE not in response.text
    assert OUTSIDE not in str(response.headers)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf8")


def thumbnail_of(host):
    return {"thumbnail": {"service": {"@id": f"http://{host}.example/iiif"}}}


@pytest.fixture
def processed_dataset(sample_dataset, cantaloupe):
    """
    The manifests of the sample dataset, written by the tasks run in the test process
    """
    generate_manifests(itemize(DATASET_DIR, DATASET_NAME))
    return sample_dataset


@pytest.fixture
def outside_files(processed_dataset):
    """
    The processed dataset, and files a route could read with a '..' in its URL but must not. All of them hold OUTSIDE:
    nothing outside the directory of the dataset is served. The 'manifest' directory next to 'input' and 'output' is
    what '..' as a dataset designates, the files in 'output' what '..' as a manifest id or a sub-level designates.
    """
    data_dir = processed_dataset
    output_dir = data_dir / "output"
    secret = {"secret": OUTSIDE}
    write_json(data_dir / "mapping.json", secret)
    write_json(
        data_dir / "manifest" / "collection" / "collection_manifest.json", secret
    )
    write_json(
        data_dir / "manifest" / "OUTSIDE_m" / "manifest.json", thumbnail_of(OUTSIDE)
    )
    write_json(data_dir / "manifest" / "OUTSIDE_m" / "canvas" / "canvas-1.json", secret)
    write_json(output_dir / DATASET_DIR / "manifest.json", secret)
    write_json(output_dir / DATASET_DIR / "extra" / "outside.json", secret)
    write_json(output_dir / DATASET_DIR / "manifest" / "outside.json", secret)
    write_json(output_dir / "outside.json", secret)
    return data_dir


# ---------------------------------------------------------------- what the routes answer, unchanged


@pytest.mark.parametrize(
    "url, path",
    [
        (
            f"{API}/{DATASET_DIR}/{NIGHT}/manifest.json",
            f"output/{DATASET_DIR}/manifest/{NIGHT}/manifest.json",
        ),
        (
            f"{API}/{DATASET_DIR}/{NIGHT}/sequence/main-sequence.json",
            f"output/{DATASET_DIR}/manifest/{NIGHT}/sequence/main-sequence.json",
        ),
        (
            f"{API}/{DATASET_DIR}/{NIGHT}/canvas/canvas-1.json",
            f"output/{DATASET_DIR}/manifest/{NIGHT}/canvas/canvas-1.json",
        ),
        (
            f"{API}/{DATASET_DIR}/{NIGHT}/annotation/annotation-1.json",
            f"output/{DATASET_DIR}/manifest/{NIGHT}/annotation/annotation-1.json",
        ),
        (
            f"{API}/{DATASET_DIR}/collection/collection_manifest.json",
            f"output/{DATASET_DIR}/manifest/collection/collection_manifest.json",
        ),
    ],
)
def test_a_manifest_is_answered_with_its_file(client, processed_dataset, url, path):
    response = get(client, url)

    body = rendered(processed_dataset / path)
    assert response.status_code == 200
    assert response.content == body
    assert dict(response.headers) == {**JSON_HEADERS, "content-length": str(len(body))}


def test_what_is_not_there_is_a_404(client, processed_dataset):
    manifests_dir = processed_dataset / "output" / DATASET_DIR / "manifest"
    (manifests_dir / "broken").mkdir()
    (manifests_dir / "broken" / "manifest.json").write_text("not json")

    for url in (
        f"{API}/{DATASET_DIR}/unknown/manifest.json",
        f"{API}/unknown/{NIGHT}/manifest.json",
        f"{API}/{DATASET_DIR}/broken/manifest.json",
        f"{API}/{DATASET_DIR}/{NIGHT}/canvas/canvas-99.json",
        f"{API}/{DATASET_DIR}/{NIGHT}/unknown/canvas-1.json",
        f"{API}/unknown/collection/collection_manifest.json",
    ):
        response = get(client, url)
        assert response.status_code == 404, url
        assert response.content == b'{"error":"Manifest not found"}', url
        assert dict(response.headers) == {**JSON_HEADERS, "content-length": "30"}, url


def test_the_names_of_the_dashboard_are_found_whatever_they_hold(data_dir):
    """
    Spaces, accents, dots, a quote and a '%' in the name of a dataset or of a manifest are plain names
    """
    for dataset_dir in ("with space é", "dots.in.the.dir", "o'brien", "100% data"):
        manifest = (
            data_dir / "output" / dataset_dir / "manifest" / "m 1.2'é" / "manifest.json"
        )
        write_json(manifest, {"dataset": dataset_dir})
        write_json(data_dir / "input" / dataset_dir / "mapping.json", {"uri": "id"})
        url = f"{API}/{quote(dataset_dir, safe='')}"

        assert get_like_a_server(
            f"{url}/{quote(manifest.parent.name, safe='')}/manifest.json"
        ).content == rendered(manifest)
        assert get_like_a_server(f"{url}/mapping").json() == {"mapping": {"uri": "id"}}


def test_the_mapping_is_answered_as_before(client, data_dir):
    (data_dir / "input" / "with_mapping").mkdir()
    (data_dir / "input" / "with_mapping" / "mapping.json").write_text('{"uri": "id"}')
    (data_dir / "input" / "without_mapping").mkdir()
    default_mapping = Path("src/mappings/default_mapping_csv.json")
    default = json.loads(default_mapping.read_text(encoding="utf8"))

    provided = get(client, f"{API}/with_mapping/mapping")
    assert provided.status_code == 200
    assert provided.content == b'{"mapping":{"uri":"id"}}'
    assert dict(provided.headers) == {**JSON_HEADERS, "content-length": "24"}

    # the default one, for a dataset without a mapping and for a dataset the input directory does not hold
    body = json.dumps({"mapping": default}, ensure_ascii=False, separators=(",", ":"))
    for name in ("without_mapping", "unknown"):
        response = get(client, f"{API}/{name}/mapping")
        assert response.status_code == 200, name
        assert response.content == body.encode("utf8"), name


def test_the_example_routes_redirect_as_before(client, processed_dataset, monkeypatch):
    # the route picks a manifest at random: always the first one by name, the 3rd record of the sample
    monkeypatch.setattr(
        "src.libs.router_lib.random.choice", lambda manifests: sorted(manifests)[0]
    )
    manifest = processed_dataset / "output" / DATASET_DIR / "manifest" / NIGHT
    service = json.loads((manifest / "manifest.json").read_text(encoding="utf8"))[
        "thumbnail"
    ]["service"]["@id"]

    for route, location in (
        ("image_api_example", f"{service}/full/full/0/default.jpg"),
        ("manifest_api_example", f"{API}/{DATASET_DIR}/{NIGHT}/manifest.json"),
        ("manifest_api_example_view", f"{API}/{DATASET_DIR}/{NIGHT}/view"),
    ):
        response = get(client, f"{API}/{DATASET_DIR}/{route}")
        assert response.status_code == 307, route
        assert dict(response.headers) == {
            "content-length": "0",
            "location": location,
            "vary": "Origin",
        }, route


def test_a_symbolic_link_that_stays_inside_the_dataset_is_followed(
    client, processed_dataset
):
    dataset_dir = processed_dataset / "output" / DATASET_DIR
    record = dataset_dir / "split" / f"http___{NIGHT}.json"
    os.symlink(record, dataset_dir / "manifest" / NIGHT / "canvas" / "linked.json")
    input_dir = processed_dataset / "input" / DATASET_DIR
    (input_dir / "specific.json").write_text('{"uri": "id"}')
    os.symlink(input_dir / "specific.json", input_dir / "mapping.json")

    linked = get(client, f"{API}/{DATASET_DIR}/{NIGHT}/canvas/linked.json")
    assert linked.status_code == 200
    assert linked.content == rendered(record)
    assert get(client, f"{API}/{DATASET_DIR}/mapping").json() == {
        "mapping": {"uri": "id"}
    }


# ---------------------------------------------------------------- a name that leaves the dataset


# '..' (with capitals too), a single dot, a backslash and a null byte, in every place of a name in a route. The files
# they designate on an unchecked path exist in 'outside_files': a route that does not check does not answer a 404.
# An encoded slash is a slash for the router (the URL has the segments of another route): see the tests below.
REFUSED_URLS = {
    "mapping, the dataset is '..' (the case proven on the fixed main)": f"{API}/%2e%2e/mapping",
    "mapping, the dataset is '..' in capitals": f"{API}/%2E%2E/mapping",
    "mapping, the dataset is '..' after an encoded slash": f"{API}/%2e%2e%2fmapping",
    "mapping, the dataset is a dot": f"{API}/%2e/mapping",
    "mapping, the dataset has a backslash": f"{API}/..%5c/mapping",
    "mapping, the dataset has a null byte": f"{API}/%00/mapping",
    "collection, the dataset is '..'": f"{API}/%2e%2e/collection/collection_manifest.json",
    "collection, the dataset is a dot": f"{API}/%2e/collection/collection_manifest.json",
    "manifest, the dataset is '..'": f"{API}/%2e%2e/OUTSIDE_m/manifest.json",
    "manifest, the dataset has a backslash": f"{API}/..%5c/OUTSIDE_m/manifest.json",
    "manifest, the id is '..'": f"{API}/{DATASET_DIR}/%2e%2e/manifest.json",
    "manifest, the id is '..' in capitals": f"{API}/{DATASET_DIR}/%2E%2E/manifest.json",
    "manifest, the id is a dot": f"{API}/{DATASET_DIR}/%2e/manifest.json",
    "manifest, the id has a backslash": f"{API}/{DATASET_DIR}/..%5c/manifest.json",
    "manifest, the id has a null byte": f"{API}/{DATASET_DIR}/%00/manifest.json",
    "sub-level, the dataset is '..'": f"{API}/%2e%2e/OUTSIDE_m/canvas/canvas-1.json",
    "sub-level, the dataset has a null byte": f"{API}/%00/{NIGHT}/canvas/canvas-1.json",
    "sub-level, the manifest id is '..'": f"{API}/{DATASET_DIR}/%2e%2e/extra/outside.json",
    "sub-level, the manifest id is '..' (the records written by the pipeline)": f"{API}/{DATASET_DIR}/%2e%2e/split/http___{NIGHT}.json",
    "sub-level, the level is '..'": f"{API}/{DATASET_DIR}/{NIGHT}/%2e%2e/outside.json",
    "sub-level, the level is '..' in capitals": f"{API}/{DATASET_DIR}/{NIGHT}/%2E%2E/outside.json",
    "sub-level, the level has a backslash": f"{API}/{DATASET_DIR}/{NIGHT}/..%5c/outside.json",
    "sub-level, the manifest id and the level are '..'": f"{API}/{DATASET_DIR}/%2e%2e/%2e%2e/outside.json",
    "sub-level, the level is '..' after an encoded slash": f"{API}/{DATASET_DIR}/{NIGHT}/%2e%2e%2foutside.json",
    "sub-level, the file is '..'": f"{API}/{DATASET_DIR}/{NIGHT}/canvas/%2e%2e",
    "sub-level, the file is a dot": f"{API}/{DATASET_DIR}/{NIGHT}/canvas/%2e",
    "sub-level, the file has a null byte": f"{API}/{DATASET_DIR}/{NIGHT}/canvas/canvas-1.json%00",
    "image example, the dataset is '..'": f"{API}/%2e%2e/image_api_example",
    "image example, the dataset has a backslash": f"{API}/..%5c/image_api_example",
    "image example, the dataset has a null byte": f"{API}/%00/image_api_example",
    "manifest example, the dataset is '..'": f"{API}/%2e%2e/manifest_api_example",
    "manifest example, the dataset is a dot": f"{API}/%2e/manifest_api_example",
    "manifest example, the dataset has a null byte": f"{API}/%00/manifest_api_example",
    "manifest example view, the dataset is '..'": f"{API}/%2e%2e/manifest_api_example_view",
    "manifest example view, the dataset is '..' in capitals": f"{API}/%2E%2E/manifest_api_example_view",
    "manifest example view, the dataset has a backslash": f"{API}/..%5c/manifest_api_example_view",
}


@pytest.mark.parametrize("label", REFUSED_URLS)
def test_a_name_that_is_not_plain_is_a_404_and_reads_nothing(outside_files, label):
    """
    The answer is a 404 and tells nothing of what was asked: not the name, not a byte of a file outside the dataset
    """
    response = get_like_a_server(REFUSED_URLS[label])

    assert response.status_code == 404
    assert response.json() in (MANIFEST_NOT_FOUND, DATASET_NOT_FOUND)
    assert_nothing_outside(response)


@pytest.mark.parametrize(
    "url",
    [
        f"{API}/%2fetc%2fpasswd/mapping",  # an absolute-looking name: with an encoded slash it is four segments
        f"{API}/%2fetc%2fpasswd/image_api_example",
        f"{API}/{DATASET_DIR}/%2fetc%2fpasswd/manifest.json",
        f"{API}//mapping",  # an empty name: an empty segment is no name
        f"{API}/{DATASET_DIR}//manifest.json",
        f"{API}/{DATASET_DIR}/{NIGHT}//canvas-1.json",
        f"{API}/{DATASET_DIR}/{NIGHT}/canvas/",
        f"{API}///image_api_example",
    ],
)
def test_an_absolute_looking_or_an_empty_name_matches_no_route(outside_files, url):
    response = get_like_a_server(url)

    assert response.status_code == 404
    assert response.json() == NO_ROUTE
    assert_nothing_outside(response)


@pytest.mark.parametrize(
    "route",
    [
        "mapping",
        "collection/collection_manifest.json",
        "OUTSIDE_m/manifest.json",
        "OUTSIDE_m/canvas/canvas-1.json",
        "image_api_example",
        "manifest_api_example",
        "manifest_api_example_view",
    ],
)
def test_a_double_encoded_name_is_decoded_once_and_is_an_unknown_name(
    outside_files, route
):
    """
    '%252e%252e' reaches the route as the six characters '%2e%2e', which are no '..': nothing decodes it again, and the
    dataset it designates does not exist. A route answers it like any other unknown dataset (the 'mapping' route gives
    its default mapping, the example routes fail, both as they did before).
    """
    unknown = get_like_a_server(f"{API}/unknown/{route}")
    double_encoded = get_like_a_server(f"{API}/%252e%252e/{route}")

    assert double_encoded.status_code == unknown.status_code
    assert double_encoded.content == unknown.content
    assert_nothing_outside(double_encoded)


# ---------------------------------------------------------------- a symbolic link that leaves the dataset


@pytest.fixture
def outside_tree(processed_dataset):
    """
    DATA_DIR/outside, with a manifest, a sub-level, a collection and a mapping, and a whole dataset (in output and in input)
    """
    outside = processed_dataset / "outside"
    secret = {"secret": OUTSIDE}
    write_json(outside / "manifest.json", secret)
    write_json(outside / "canvas" / "canvas-1.json", secret)
    write_json(outside / "collection" / "collection_manifest.json", secret)
    write_json(outside / "mapping.json", secret)
    write_json(outside / "dataset" / "mapping.json", secret)
    write_json(
        outside / "dataset" / "manifest" / "collection" / "collection_manifest.json",
        secret,
    )
    write_json(
        outside / "dataset" / "manifest" / "OUTSIDE_m" / "manifest.json",
        thumbnail_of(OUTSIDE),
    )
    return outside


def test_a_symbolic_link_that_leaves_the_dataset_is_a_404(
    processed_dataset, outside_tree
):
    output_dir = processed_dataset / "output"
    input_dir = processed_dataset / "input"
    manifests_dir = output_dir / DATASET_DIR / "manifest"
    # a file, and a folder of the manifests, in the dataset
    (manifests_dir / "file_link").mkdir()
    os.symlink(
        outside_tree / "manifest.json", manifests_dir / "file_link" / "manifest.json"
    )
    os.symlink(outside_tree, manifests_dir / "dir_link")
    # the folder of the collection
    (output_dir / "linked_collection" / "manifest").mkdir(parents=True)
    os.symlink(
        outside_tree / "collection",
        output_dir / "linked_collection" / "manifest" / "collection",
    )
    # a dataset that is a link to a directory outside 'output', or outside 'input'
    os.symlink(outside_tree / "dataset", output_dir / "outside_dataset")
    os.symlink(outside_tree / "dataset", input_dir / "outside_dataset")
    # the mapping of a dataset
    (input_dir / "linked_mapping").mkdir()
    os.symlink(
        outside_tree / "mapping.json", input_dir / "linked_mapping" / "mapping.json"
    )

    for url in (
        f"{API}/{DATASET_DIR}/file_link/manifest.json",
        f"{API}/{DATASET_DIR}/dir_link/manifest.json",
        f"{API}/{DATASET_DIR}/dir_link/canvas/canvas-1.json",
        f"{API}/linked_collection/collection/collection_manifest.json",
        f"{API}/outside_dataset/collection/collection_manifest.json",
        f"{API}/outside_dataset/image_api_example",
        f"{API}/outside_dataset/manifest_api_example",
        f"{API}/outside_dataset/manifest_api_example_view",
        f"{API}/outside_dataset/mapping",
        f"{API}/linked_mapping/mapping",
    ):
        response = get_like_a_server(url)
        assert response.status_code == 404, url
        assert response.json() in (MANIFEST_NOT_FOUND, DATASET_NOT_FOUND), url
        assert_nothing_outside(response)


def test_a_symbolic_link_to_another_dataset_is_a_404(processed_dataset):
    """
    The directory of the dataset is the limit, not 'output': what is next to it is not served through it
    """
    output_dir = processed_dataset / "output"
    manifests_dir = output_dir / DATASET_DIR / "manifest"
    other = output_dir / "other" / "manifest" / "m"
    write_json(other / "manifest.json", {"secret": OUTSIDE})
    (manifests_dir / "other_file").mkdir()
    os.symlink(other / "manifest.json", manifests_dir / "other_file" / "manifest.json")
    os.symlink(other, manifests_dir / "other_dir")

    for url in (
        f"{API}/{DATASET_DIR}/other_file/manifest.json",
        f"{API}/{DATASET_DIR}/other_dir/manifest.json",
    ):
        response = get_like_a_server(url)
        assert response.status_code == 404, url
        assert response.json() == MANIFEST_NOT_FOUND, url
        assert_nothing_outside(response)
    # the other dataset itself is served
    assert get_like_a_server(f"{API}/other/m/manifest.json").content == rendered(
        other / "manifest.json"
    )


# ---------------------------------------------------------------- find_in_dataset


@pytest.fixture
def datasets(tmp_path):
    """
    A directory of datasets with a dataset (and a file below it), another dataset, a file next to them, and a file outside
    """
    root = tmp_path / "root"
    write_json(root / "ds" / "level" / "file.json", {})
    write_json(root / "other" / "level" / "file.json", {})
    write_json(root / "stray.json", {})
    write_json(tmp_path / "outside" / "file.json", {})
    return root


def test_find_in_dataset_returns_the_resolved_path(datasets):
    found = find_in_dataset(datasets, "ds", "level", "file.json")

    assert found == (datasets / "ds" / "level" / "file.json").resolve()
    assert found.is_file()
    assert find_in_dataset(datasets, "ds") == (datasets / "ds").resolve()
    # the directory of the datasets is resolved too
    unresolved = Path(datasets, "..", "root")
    assert (
        find_in_dataset(unresolved, "ds", "level")
        == (datasets / "ds" / "level").resolve()
    )


def test_find_in_dataset_does_not_need_the_path_to_exist(datasets, tmp_path):
    root = datasets.resolve()
    assert (
        find_in_dataset(datasets, "missing", "x", "y.json")
        == root / "missing" / "x" / "y.json"
    )
    assert (
        find_in_dataset(datasets, "ds", "level", "none.json")
        == root / "ds" / "level" / "none.json"
    )
    no_root = tmp_path / "no root"
    assert (
        find_in_dataset(no_root, "ds", "file.json")
        == no_root.resolve() / "ds" / "file.json"
    )


@pytest.mark.parametrize(
    "name",
    [
        "with space",
        "accents é ü 日本",
        "o'brien",
        "100% data",
        "dots.in.the.dir",
        "a..b",
        "...",
        "..a",
        "a..",
        ".hidden",
        "%2e%2e",  # nothing is decoded: this is a directory called '%2e%2e'
        "%252e%252e",
        "x" * 200,
    ],
)
def test_find_in_dataset_takes_a_plain_name_whatever_it_holds(datasets, name):
    root = datasets.resolve()
    assert find_in_dataset(datasets, name, name) == root / name / name
    assert find_in_dataset(datasets, "ds", name) == root / "ds" / name


# a name that is not plain
NOT_PLAIN = [
    "",
    ".",
    "..",
    "../ds",
    "ds/..",
    "../outside",
    "a/b",
    "ds/",
    "/ds",
    "/",
    "//",
    "/etc/passwd",
    "a\\b",
    "..\\",
    "\\",
    "\\etc\\passwd",
    "x\x00",
    "\x00",
    "x\x00y",
]


@pytest.mark.parametrize("name", NOT_PLAIN)
def test_find_in_dataset_refuses_a_name_that_is_not_plain(datasets, name):
    assert find_in_dataset(datasets, name) is None
    assert find_in_dataset(datasets, name, "level", "file.json") is None
    assert find_in_dataset(datasets, "ds", name) is None
    assert find_in_dataset(datasets, "ds", "level", name) is None
    assert find_in_dataset(datasets, "ds", name, "file.json") is None


def test_find_in_dataset_refuses_a_path_that_leaves_the_dataset_through_a_link(
    datasets, tmp_path
):
    dataset = datasets / "ds"
    os.symlink(tmp_path / "outside" / "file.json", dataset / "level" / "outside_file")
    os.symlink(tmp_path / "outside", dataset / "outside_dir")
    os.symlink(datasets / "other" / "level", dataset / "other_level")  # another dataset
    os.symlink(datasets / "stray.json", dataset / "stray")  # next to the datasets
    os.symlink(datasets, dataset / "root")  # the directory of the datasets
    os.symlink("..", dataset / "up")  # relative
    os.symlink(tmp_path / "outside", datasets / "outside_dataset")  # a dataset outside

    assert find_in_dataset(datasets, "ds", "level", "outside_file") is None
    assert find_in_dataset(datasets, "ds", "outside_dir") is None
    assert find_in_dataset(datasets, "ds", "outside_dir", "file.json") is None
    assert find_in_dataset(datasets, "ds", "other_level", "file.json") is None
    assert find_in_dataset(datasets, "ds", "stray") is None
    assert find_in_dataset(datasets, "ds", "root", "other", "level") is None
    assert find_in_dataset(datasets, "ds", "up", "other") is None
    assert find_in_dataset(datasets, "outside_dataset") is None
    assert find_in_dataset(datasets, "outside_dataset", "file.json") is None


def test_find_in_dataset_follows_a_link_that_stays_inside_the_dataset(datasets):
    dataset = datasets / "ds"
    file = (dataset / "level" / "file.json").resolve()
    os.symlink(dataset / "level" / "file.json", dataset / "alias.json")
    os.symlink("level", dataset / "short")  # relative
    os.symlink(dataset, datasets / "same")  # a dataset known by two names

    assert find_in_dataset(datasets, "ds", "alias.json") == file
    assert find_in_dataset(datasets, "ds", "short", "file.json") == file
    assert find_in_dataset(datasets, "same", "level", "file.json") == file


def test_find_in_dataset_refuses_a_name_that_is_no_file_name(datasets):
    assert find_in_dataset(datasets, "x\ud800y") is None
    assert find_in_dataset(datasets, "ds", "x\ud800y") is None


def test_find_in_dataset_does_not_fail_on_a_link_loop_or_a_long_name(datasets):
    os.symlink("loop_b", datasets / "ds" / "loop_a")
    os.symlink("loop_a", datasets / "ds" / "loop_b")

    # the route reads these, and fails as it did: finding the path is not reading it
    assert find_in_dataset(datasets, "ds", "loop_a") is not None
    assert find_in_dataset(datasets, "ds", "n" * 5000) is not None
    assert find_in_dataset(datasets, "d" * 5000, "file.json") is not None
