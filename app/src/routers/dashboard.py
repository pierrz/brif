"""
Module dedicated to the dashboard page
"""

import os
from pathlib import Path

from config import app_config
from fastapi import APIRouter, Request
from src.db.database import get_db_data, load_input_dataset
from src.libs.router_lib import prepare_input_datasets
from templates.frontend_templates import templates

router = APIRouter(
    tags=["brif"],
    responses={404: {"description": "Issue with endpoint"}},
)


def gather_input_datasets(input_dir):

    input_data = []
    input_dataset_names = []

    # walk over all input dirs
    for root_dir, subdirs, dataset_files in os.walk(input_dir):
        if root_dir != str(input_dir):

            # check all datasets file within a directory, using either a default mapping or a provided one
            datasets_pack = prepare_input_datasets(root_dir, dataset_files)

            # flatten data
            for dataset in datasets_pack:
                input_data.append(dataset)
                input_dataset_names.append(dataset.fullname)

    return input_dataset_names, input_data


def sync_datasets_with_db(input_dataset_names, input_data):

    available_data = get_db_data(input_dataset_names)

    if len(input_dataset_names) > len(available_data):
        processed_datasets_list = [
            processed_d.fullname for processed_d in available_data
        ]
        datasets_to_create = [
            input_data[idx]
            for idx, dataset in enumerate(input_dataset_names)
            if dataset not in processed_datasets_list
        ]
        for dataset in datasets_to_create:
            load_input_dataset(dataset)


@router.get("/dashboard", include_in_schema=False)
async def dashboard(request: Request):

    input_dir = Path(app_config.DATA_DIR, "input")
    input_dataset_names, input_data = gather_input_datasets(input_dir)

    # udpate the database then retrieve data from it
    sync_datasets_with_db(input_dataset_names, input_data)
    data = get_db_data(input_dataset_names)

    return templates.TemplateResponse(
        "dashboard.html",
        context={"request": request, "data": data, "title": "Brif demo - Dashboard"},
    )
