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
@router.get("/{dataset_name}/{manifest_id}/view", include_in_schema=False)
async def manifest_viewer_tify(request: Request):
    return templates.TemplateResponse(
        "viewer_tify.html", context={"request": request, "title": "Brif demo - Viewer"}
    )


# APIs
@router.get("/{dataset_name}/mapping")
async def mapping_api(dataset_name: str):
    """
    Get the json mapping provided with this dataset
    :param dataset_name: the dataset full name
    :return: the mapping JSON data
    """
    mapping_data = get_mapping(dataset_name)[0]
    return JSONResponse({"mapping": mapping_data})


@router.get("/{dataset_name}/{manifest_id}/{sub_level}/{filename}")
async def sub_manifest_api(dataset_name: str, manifest_id: str, sub_level: str, filename: str):
    """
    Get the data at a specific level e.g. sequence, canvas or annotation
    :param dataset_name: the dataset full name
    :param manifest_id: the manifest id
    :param sub_level: the level type as specified below
    :param filename: a specific filename at that level
    :return: the JSON data for this sub-level
    """
    manifest_path = Path(get_dirs(dataset_name)[1], manifest_id, sub_level, filename)
    return JSONResponse(load_json(manifest_path))


@router.get("/{dataset_name}/{manifest_id}/manifest.json")
async def manifest_api(dataset_name: str, manifest_id: str):
    """
    Get the data of a specific manifest
    :param dataset_name: the dataset full name
    :param manifest_id: the manifest id
    :return: the JSON data for this manifest
    """
    manifest_path = Path(
        get_dirs(dataset_name)[1], manifest_id, f"{ikn.manif_name}.json"
    )
    return JSONResponse(load_json(manifest_path))


@router.get("/{dataset_name}/collection/collection_manifest.json")
async def collection_manifest_api(dataset_name: str):
    """
    Get the data of the complete dataset/collection
    :param dataset_name: the dataset full name
    :return: the JSON data for this collection
    """
    coll_manifest_path = Path(
        get_dirs(dataset_name)[1], ikn.coll_name, f"{ikn.coll_manif_name}.json"
    )
    return JSONResponse(load_json(coll_manifest_path))


# Samples routes
@router.get("/{dataset_name}/image_api_example")
async def image_api_example(dataset_name: str):
    """
    Redirection to a random IIIF image from this dataset
    :param dataset_name: the dataset full name
    :return: the JSON data for this collection
    """
    manifests_dir = Path(get_dirs(dataset_name)[1])
    img_url = select_random_manifest(manifests_dir, "image")
    return RedirectResponse(img_url)


@router.get("/{dataset_name}/manifest_api_example_view", include_in_schema=False)
async def manifest_api_example_view(dataset_name: str):
    """
    Redirection to the viewer with a random IIIF image from this dataset
    :param dataset_name: the dataset full name
    :return: the JSON data for this collection
    """
    manifests_dir = Path(get_dirs(dataset_name)[1])
    view_url = f"{prefix}/{select_random_manifest(manifests_dir)}/view"
    return RedirectResponse(view_url)


@router.get("/{dataset_name}/manifest_api_example")
async def manifest_api_example(dataset_name: str):
    """
    Get the data of a random manifest from this dataset
    :param dataset_name: the dataset full name
    :return: the JSON data for the retrieved manifest
    """
    manifests_dir = Path(get_dirs(dataset_name)[1])
    manifest_url = (
        f"{prefix}/{select_random_manifest(manifests_dir)}/{ikn.manif_name}.json"
    )
    return RedirectResponse(manifest_url)
