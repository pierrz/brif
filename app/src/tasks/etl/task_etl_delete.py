import shutil

from src.db.database import update_row
from src.libs.main_lib import get_dataset_output_dir, step_message_init
from worker import celery, logger


@celery.task()
def delete_dataset_task(dataset_dir_name, dataset_name):

    mes_step = "DELETE DATASET"
    dataset_fullname = f"{dataset_dir_name}/{dataset_name}"
    step_message_init(mes_step, dataset_fullname)

    dataset_dir_path = get_dataset_output_dir(dataset_dir_name)
    if dataset_dir_path.exists():
        logger.info("Deleting dataset ...")
        shutil.rmtree(dataset_dir_path)
        update_row(dataset_fullname)

        logger.info("Dataset output files deleted.")
    logger.info("Dataset not processed yet.")
