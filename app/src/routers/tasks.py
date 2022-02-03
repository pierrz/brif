from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from src.db.database import delete_row
from src.tasks.etl.task_etl_delete import delete_dataset_task
from src.tasks.etl.task_etl_generate_manifests import generate_manifests
from src.tasks.etl.task_etl_itemize import itemize
from src.tasks.etl.task_etl_load_db import load_results_to_db
from starlette_core.messages import message

router = APIRouter(
    prefix="/task",
    tags=["task"],
    responses={404: {"description": "Issue with endpoint"}},
)


@router.get("/delete_dataset/{dataset_dir}/{dataset_name}")
async def delete_dataset(request: Request, dataset_dir, dataset_name):

    delete_dataset_task.delay(dataset_dir, dataset_name)
    fullname = f"{dataset_dir}/{dataset_name}"
    delete_row(fullname)
    message(
        request, f"Transformed data was deleted for the dataset '{fullname}'", "success"
    )
    return RedirectResponse("/dashboard")


@router.get("/process_dataset/{dataset_dir}/{dataset_name}")
async def process_dataset(request: Request, dataset_dir, dataset_name):

    chain = (
        itemize.s(dataset_dir, dataset_name)
        | generate_manifests.s()
        | load_results_to_db.s()
    )
    chain()
    message(
        request,
        f"Dataset '{dataset_dir}/{dataset_name}' is getting processed ...",
        "success",
    )
    return RedirectResponse("/dashboard")
