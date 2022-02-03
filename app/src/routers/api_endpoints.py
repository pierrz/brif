from pathlib import Path

import src.mappings.item_key_names as ikn
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from src.libs.main_lib import get_dirs, get_mapping, load_json
from src.libs.router_lib import select_random_manifest
from templates.backend_templates import templates

prefix = "/iiif/pres"
router = APIRouter(
    prefix=prefix,
    tags=["iiif"],
    responses={404: {"description": "Issue with endpoint"}},
)


# Viewer
@router.get("/{dataset_name}/{manifest_id}/view")
async def manifest_viewer_tify(request: Request):
    return templates.TemplateResponse(
        "viewer_tify.html", context={"request": request, "title": "Brif demo - Viewer"}
    )


# APIs
@router.get("/{dataset_name}/mapping")
async def mapping_api(dataset_name):
    mapping_data = get_mapping(dataset_name)[0]
    return JSONResponse({"mapping": mapping_data})


@router.get("/{dataset_name}/{manifest_id}/{sub_level}/{filename}")
async def sub_manifest_api(dataset_name, manifest_id, sub_level, filename):
    manifest_path = Path(get_dirs(dataset_name)[1], manifest_id, sub_level, filename)
    return JSONResponse(load_json(manifest_path))


@router.get("/{dataset_name}/{manifest_id}/manifest.json")
async def manifest_api(dataset_name, manifest_id):
    manifest_path = Path(
        get_dirs(dataset_name)[1], manifest_id, f"{ikn.manif_name}.json"
    )
    return JSONResponse(load_json(manifest_path))


@router.get("/{dataset_name}/collection/collection_manifest.json")
async def collection_manifest_api(dataset_name):
    coll_manifest_path = Path(
        get_dirs(dataset_name)[1], ikn.coll_name, f"{ikn.coll_manif_name}.json"
    )
    return JSONResponse(load_json(coll_manifest_path))


# Samples routes
@router.get("/{dataset_name}/image_api_example")
async def image_api_example(dataset_name: str):
    manifests_dir = Path(get_dirs(dataset_name)[1])
    img_url = select_random_manifest(manifests_dir, "image")
    return RedirectResponse(img_url)


@router.get("/{dataset_name}/manifest_api_example_view")
async def manifest_api_example_view(dataset_name: str):
    manifests_dir = Path(get_dirs(dataset_name)[1])
    view_url = f"{prefix}/{select_random_manifest(manifests_dir)}/view"
    return RedirectResponse(view_url)


@router.get("/{dataset_name}/manifest_api_example")
async def manifest_api_example(dataset_name: str):
    manifests_dir = Path(get_dirs(dataset_name)[1])
    manifest_url = (
        f"{prefix}/{select_random_manifest(manifests_dir)}/{ikn.manif_name}.json"
    )
    return RedirectResponse(manifest_url)
