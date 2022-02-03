"""
Common utilities
"""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Union

import requests
import src.mappings.item_key_names as ikn
from config import app_config
from worker import logger


def fetch_json_from_url(url: str) -> Dict:
    """
    Fetch JSON data from given url
    :param ur: the url to fetch
    :return: a dict object
    """
    response = requests.get(url)
    return response.json()


def load_json(file_path: Union[str, Path]) -> Dict:
    """
    Load JSON into dict object
    :param file_path: file path
    :return: a dict object
    """
    with open(file_path, "rt", encoding="utf8") as json_file:
        json_str = json_file.read()
        return json.loads(json_str)


def count_in_dir(directory_path: str) -> int:
    """
    Count files in directory
    :param directory_path: directory path
    :return: the number of files directly under that directory
    """
    count = len(os.listdir(directory_path))
    return count


def get_dataset_output_dir(dataset_dir_name: str) -> Path:
    return Path(app_config.DATA_DIR, "output", dataset_dir_name)


def get_dirs(dataset_dir_name: str) -> List[Path]:
    """
    Retrieves the 2 data sub-directories path for a given dataset
    :param dataset_dir_name: the dataset file name
    :return: a list with the 2 Path objects
    """
    dataset_dir = get_dataset_output_dir(dataset_dir_name)
    split_dir = Path(dataset_dir, "split")
    manifest_dir = Path(dataset_dir, ikn.manif_name)
    return split_dir, manifest_dir


def get_dataset_path(dataset_dir_name: str, dataset_name: str) -> Path:
    """
    Retrieve the dataset input path
    :param dataset_dir_name: name of the directory containing the dataset
    :param dataset_name: name of the dataset file
    :return: the Path object for the retrieved file
    """
    return Path(app_config.DATA_DIR, "input", dataset_dir_name, dataset_name)


def get_mapping(dataset_dir_name: str) -> Dict:
    """
    Get the dataset mapping file
    :param dataset_dir_name: name of the directory containing the dataset
    :return: the dict object of the mapping
    """
    specific_mapping = Path(
        app_config.DATA_DIR, "input", dataset_dir_name, "mapping.json"
    )
    if specific_mapping.exists():
        return load_json(specific_mapping), "specific"

    return (
        load_json(Path(os.getcwd(), "src", "mappings", "default_mapping_csv.json")),
        "default",
    )


def check_directory(dir_list: List[Union[str, Path]]):
    """
    Check directory paths, if exists then delete and re-create it, else just create it
    :param dir_list: the list of paths to check
    :return: does its thing
    """
    for directory in dir_list:
        if directory is None:
            continue

        if directory.exists():
            shutil.rmtree(directory)
            os.mkdir(directory)
        else:
            os.mkdir(directory)


# """"""""""""""""""""""
# """ CELERY LOGGING """


def step_message_init(step_str: str, object_id: str, *args):
    """
    Logging feature - Celery task initialization
    :param step_str: step name
    :param object_id: dataset (or collection) ID
    :param args: extra args [legacy]
    :return: prints stuff in the celery logger
    """

    # [legacy]
    if step_str == "DELETE COLLECTION":
        obj_type = "collection"
    else:
        obj_type = "dataset"

    mes_sep = "============================================="
    logger.info("\n>")
    logger.info(mes_sep)
    logger.info("%s", step_str)
    mes_dataset = f"[{obj_type}: '{object_id}']"

    if not args:
        logger.info("%s --> Step initiated ...", mes_dataset)

    else:
        logger.info("%s --> Results", mes_dataset)
        for line in args[0]:  # strange position of the list ... ?
            step_message_line(line, "wait")


def step_message_line(line_str: str, *args):
    """
    Logging feature - line print function
    :param line_str: string to print
    :param args: extra args [legacy]
    :return: prints stuff in the celery logger
    """
    mes_line = f"--> {line_str}"
    if len(args) > 0:
        if args[0] == "wait":
            logger.info(mes_line)
    else:
        logger.info(mes_line)


def init_message(mes_str: str, name: str, i: int, total: int):
    """
    Logging feature - message print function
    :param mes_str: message to print
    :param name: name of the file/object
    :param i: position of the file/object
    :param total: total of files/objects
    :return: prints stuff in the celery logger
    """
    logger.info("\n")
    tuned_message = f"--> {name} #{i} / {total}  <->  {mes_str}"
    logger.info(tuned_message)
