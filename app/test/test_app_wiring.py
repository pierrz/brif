"""
What main.py wires around the routes and what the routes answer outside of the pipeline: the
route table, static files, the middlewares (proxy header, gzip, CORS), the flash messages of the
dashboard, the settings read from the environment and the helper routes of the API.
Meant to catch what a FastAPI / Starlette / pydantic upgrade could change silently.
"""

import json
import re
from pathlib import Path

import pytest
from config import Config, app_config, celery_config
from src.libs.main_lib import load_json
from src.routers import tasks as tasks_router
from src.tasks.etl.task_etl_generate_manifests import generate_manifests
from src.tasks.etl.task_etl_itemize import itemize

DATASET_DIR, DATASET_NAME = "test_dataset", "test_records.csv"
FULLNAME = f"{DATASET_DIR}/{DATASET_NAME}"

# ---------------------------------------------------------------- the routes

DOCUMENTED = {
    "/iiif/pres/{dataset_name}/collection/collection_manifest.json",
    "/iiif/pres/{dataset_name}/image_api_example",
    "/iiif/pres/{dataset_name}/manifest_api_example",
    "/iiif/pres/{dataset_name}/mapping",
    "/iiif/pres/{dataset_name}/{manifest_id}/manifest.json",
    "/iiif/pres/{dataset_name}/{manifest_id}/{sub_level}/{filename}",
    "/task/delete_dataset/{dataset_dir}/{dataset_name}",
    "/task/process_dataset/{dataset_dir}/{dataset_name}",
}
# one URL per route of the API, the documented ones and the others (/demo, the viewer, the examples, the tests)
ALL_URLS = [
    "/demo",
    "/iiif/pres/d/collection/collection_manifest.json",
    "/iiif/pres/d/image_api_example",
    "/iiif/pres/d/manifest_api_example",
    "/iiif/pres/d/manifest_api_example_view",
    "/iiif/pres/d/mapping",
    "/iiif/pres/d/m/manifest.json",
    "/iiif/pres/d/m/view",
    "/iiif/pres/d/m/canvas/c.json",
    "/task/delete_dataset/d/n",
    "/task/process_dataset/d/n",
    "/test/api_live",
    "/test/check_cantaloupe",
    "/test/check_iiif_pipeline",
    "/test/load_db",
    "/test/read_db",
]


@pytest.mark.parametrize("url", ALL_URLS)
def test_the_routes_of_the_api_answer_get_only(client, url):
    """
    Nothing but GET: the other methods are refused before any code of the route runs
    """
    for method in ("post", "put", "delete", "patch"):
        response = getattr(client, method)(url)
        assert response.status_code == 405, (method, url)
        assert response.json() == {"detail": "Method Not Allowed"}


def test_the_openapi_document_lists_the_documented_routes_only(client):
    """
    The other routes (/demo, the viewer, the examples views, /test/...) are not in the documentation
    """
    document = client.get("/openapi.json").json()
    assert set(document["paths"]) == DOCUMENTED
    assert all(list(methods) == ["get"] for methods in document["paths"].values())
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_an_unknown_route_is_a_404_with_a_json_detail(client):
    response = client.get("/no/such/route")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


# ---------------------------------------------------------------- static files


def test_static_files_are_served_from_the_static_directory(client):
    response = client.get("/static/css/main.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert response.content == Path("static/css/main.css").read_bytes()
    assert client.get("/static/css/missing.css").status_code == 404


# ---------------------------------------------------------------- middlewares


def test_the_forwarded_protocol_makes_the_links_of_the_pages_https(
    page_client, data_dir
):
    plain = page_client.get("/demo").text
    behind_proxy = page_client.get("/demo", headers={"X-Forwarded-Proto": "https"}).text
    assert 'href="http://testserver/static/css/main.css"' in plain
    assert 'href="https://testserver/static/css/main.css"' in behind_proxy


def test_every_origin_may_read_the_api(client):
    response = client.get("/test/api_live", headers={"Origin": "https://other.example"})
    # "*", without credentials: Starlette 1 would echo the origin and allow credentials with allow_credentials=True,
    # which the app does not want (nothing here authenticates with a cookie)
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers


def test_a_preflight_request_is_answered_for_any_method_and_header(client):
    response = client.options(
        "/test/api_live",
        headers={
            "Origin": "https://other.example",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "x-whatever",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers
    assert response.headers["access-control-allow-headers"] == "x-whatever"
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_answers_are_gzipped_when_the_client_accepts_it(client, data_dir):
    """
    The 'minimum_size' of the GZip middleware does not apply: the ProxyFix middleware (a
    BaseHTTPMiddleware) below it streams the body, so every answer is compressed, small ones too.
    """
    directory = data_dir / "input" / DATASET_DIR
    directory.mkdir()
    big_mapping = {"uri": "dc:identifier", "notes": "x" * 2000}
    (directory / "mapping.json").write_text(json.dumps(big_mapping))

    big = client.get(f"/iiif/pres/{DATASET_DIR}/mapping")
    assert big.headers["content-encoding"] == "gzip"
    assert big.json() == {"mapping": big_mapping}  # decoded by the client

    small = client.get("/test/api_live")
    assert small.headers["content-encoding"] == "gzip"
    assert small.headers["vary"] == "Accept-Encoding, Origin"  # CORS adds Origin to every answer now
    assert small.json() == {"message": "Hello World"}

    plain = client.get("/test/api_live", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers


# ---------------------------------------------------------------- flash messages


def test_a_flash_message_is_shown_on_the_next_page_once(
    page_client, data_dir, monkeypatch
):
    monkeypatch.setattr(tasks_router.delete_dataset_task, "delay", lambda *args: None)

    # the redirect to /demo is followed: the page of the redirect shows the message
    first = page_client.get(f"/task/delete_dataset/{FULLNAME}")
    assert first.status_code == 200
    assert "Transformed data was deleted for the dataset" in first.text
    assert 'class="message message-success is-success flash"' in first.text

    second = page_client.get("/demo")
    assert "Transformed data was deleted" not in second.text
    assert 'class="message ' not in second.text


# ---------------------------------------------------------------- the mapping and example routes


def test_the_mapping_of_a_dataset_is_the_default_one_unless_it_brings_its_own(
    client, data_dir
):
    (data_dir / "input" / DATASET_DIR).mkdir()
    default = load_json("src/mappings/default_mapping_csv.json")
    assert client.get(f"/iiif/pres/{DATASET_DIR}/mapping").json() == {"mapping": default}

    (data_dir / "input" / DATASET_DIR / "mapping.json").write_text('{"uri": "id"}')
    assert client.get(f"/iiif/pres/{DATASET_DIR}/mapping").json() == {
        "mapping": {"uri": "id"}
    }


@pytest.fixture
def processed_dataset(sample_dataset, cantaloupe):
    """
    The manifests of the sample dataset, written by the tasks run in the test process
    """
    generate_manifests(itemize(DATASET_DIR, DATASET_NAME))
    return sample_dataset


def test_the_example_routes_redirect_to_a_manifest_of_the_dataset(
    client, processed_dataset
):
    api = f"/iiif/pres/{DATASET_DIR}"
    manifest_id = r"kokoelmat_fng_fi_app_si_(A_V_4460|N_1998_22|N_2010_68)"

    data = client.get(f"{api}/manifest_api_example", follow_redirects=False)
    assert data.status_code == 307
    assert re.fullmatch(
        rf"/iiif/pres/{DATASET_DIR}/{manifest_id}/manifest.json", data.headers["location"]
    )

    view = client.get(f"{api}/manifest_api_example_view", follow_redirects=False)
    assert view.status_code == 307
    assert re.fullmatch(
        rf"/iiif/pres/{DATASET_DIR}/{manifest_id}/view", view.headers["location"]
    )

    image = client.get(f"{api}/image_api_example", follow_redirects=False)
    assert image.status_code == 307
    assert image.headers["location"].startswith(app_config.API_IIIF_IMAGE_PUBLIC)
    assert image.headers["location"].endswith("/full/full/0/default.jpg")


def test_the_viewer_page_embeds_tify(page_client, data_dir):
    page = page_client.get(f"/iiif/pres/{DATASET_DIR}/some_manifest/view")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert 'src="http://testserver/static/tify/tify.js"' in page.text
    assert "new Tify(" in page.text


# ---------------------------------------------------------------- settings read from the environment


def test_the_settings_are_derived_from_the_environment():
    assert app_config.SECRET_KEY == "test-secret-key"
    assert app_config.IIIF_IMG_VERSION == 2
    assert app_config.LOCAL_DEV is False
    assert app_config.API_IIIF_IMAGE.endswith("/iiif/2/")
    assert app_config.APP_BASE_URL == "https://brif.example.org"
    assert app_config.API_IIIF_PRES == "https://brif.example.org/iiif/pres/"
    assert app_config.API_IIIF_IMAGE_PUBLIC == "https://cantaloupe.example.org/iiif/2/"
    assert str(app_config.DATA_DIR) == "/nonexistent/brif-test-data"
    assert (app_config.DB_NAME, app_config.DB_USER) == ("brif", "brif")


def test_an_environment_variable_named_like_a_setting_overrides_it(monkeypatch):
    """
    The settings classes read the environment by field name (case insensitive), whatever the default
    """
    monkeypatch.setenv("IIIF_IMG_VERSION", "3")
    monkeypatch.setenv("data_dir", "/somewhere/else")
    monkeypatch.setenv("APP_BASE_URL", "https://override.example")
    monkeypatch.setenv("TIMEZONE", "UTC")
    monkeypatch.setenv("TASK_TRACK_STARTED", "false")

    config = Config()
    assert config.IIIF_IMG_VERSION == 3  # coerced to int
    assert str(config.DATA_DIR) == "/somewhere/else"  # and to a Path
    assert config.APP_BASE_URL == "https://override.example"
    assert type(config.DATA_DIR) is type(app_config.DATA_DIR)  # pylint: disable=unidiomatic-typecheck

    celery_settings = type(celery_config)()
    assert celery_settings.timezone == "UTC"
    assert celery_settings.task_track_started is False
    # untouched: the same as the module level instance
    assert celery_settings.imports == celery_config.imports
