from src.db.database import delete_row, insert_row
from src.db.models import dataset_from_dict
from src.libs.main_lib import step_message_init
from worker import celery, logger


@celery.task()
def load_results_to_db(results_pack):

    mes_step = "STEP 3 | STATISTICS"
    step_message_init(mes_step, results_pack["fullname"])
    logger.info("Received data: %s", results_pack)

    try:
        delete_row(results_pack["fullname"])
    except Exception:
        logger.info("No data to clean ...")

    dataset = dataset_from_dict(results_pack)
    insert_row(dataset)
    logger.info(dataset)
