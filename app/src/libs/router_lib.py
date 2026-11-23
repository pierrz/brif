import csv
import os
import random
from pathlib import Path
from typing import Dict, Optional, Union

import src.mappings.item_key_names as ikn
from config import app_config
from src.db.models import InputDataset
from src.libs.main_lib import get_dataset_path, load_json
from src.tasks.etl.task_etl_generate_manifests import generate_manifests
from src.tasks.etl.task_etl_itemize import itemize


def select_random_manifest(
    manifests_dir: Path, mode: str = "presentation"
) -> Union[Dict, str]:
    """
    picks the 1st document manifest, and returns either the data or the 1st image url
    :param manifests_dir: path of the manifests directory
    :param mode: either 'presentation' or 'image', depending on which API/case
    :return: data dict or url string
    """

    manifests_list = [
        man_dir.name
        for man_dir in os.scandir(manifests_dir)
        if man_dir.name != "collection"
    ]
    manifest_pick = random.choice(manifests_list)

    if mode == "image":
        file_data = load_json(
            Path(manifests_dir, manifest_pick, f"{ikn.manif_name}.json")
        )
        main_iiif_service = file_data["thumbnail"]["service"]["@id"]
        return f"{main_iiif_service}/full/full/0/default.jpg"

    return f"{manifests_dir.parent.name}/{manifest_pick}"


def prepare_input_datasets(root_dir, dataset_files):
    """
    prepares each dataset within a given directory
    :param root_dir: root directory path of the datasets
    :param dataset_files:
    :return:
    """
    count = 0
    datasets_pack = []
    mapping = "default"
    mapping_filename = "mapping.json"
    if mapping_filename in dataset_files:
        mapping = "provided"

    for dataset_file in dataset_files:
        if dataset_file != mapping_filename:
            dataset_path = Path(root_dir, dataset_file)
            with open(dataset_path, "r", encoding="utf8") as count_file:
                csv_reader = csv.reader(count_file)
                count += sum(1 for row in csv_reader) - 1  # 1 row discarded

            dataset_dir = dataset_path.parent.name
            fullname = f"{dataset_dir}/{dataset_path.name}"
            print(f"Registering dataset '{fullname}' in DB ...")
            dataset = InputDataset(
                fullname=fullname,
                dir_name=dataset_dir,
                total=count,
                mapping=mapping,
            )
            datasets_pack.append(dataset)
            print("Dataset registered.")

    return datasets_pack


def find_input_dataset(dataset_dir: str, dataset_name: str) -> Optional[Path]:
    """
    Looks for a dataset of the dashboard: a file in a directory of DATA_DIR/input.
    The two names come from a URL, nothing here trusts them: each must be a plain name (no separator,
    not '.' or '..') and the file, once its symbolic links are resolved, must be a regular file inside the input directory.
    :param dataset_dir: name of the directory containing the dataset
    :param dataset_name: name of the dataset file
    :return: the resolved path of the file, or None when the names do not designate such a file
    """
    for name in (dataset_dir, dataset_name):
        if name in ("", ".", "..") or Path(name).name != name:
            return None

    try:
        input_dir = Path(app_config.DATA_DIR, "input").resolve()
        dataset_path = get_dataset_path(dataset_dir, dataset_name).resolve()
    except (OSError, ValueError):  # a name too long, a null byte, ...
        return None

    if dataset_path.is_relative_to(input_dir) and dataset_path.is_file():
        return dataset_path
    return None


def find_in_dataset(root_dir: Path, dataset_name: str, *names: str) -> Optional[Path]:
    """
    Builds a path below the directory of a dataset (root_dir/dataset_name, e.g. DATA_DIR/output/<dataset>) for the routes
    of the API. The names come from a URL, nothing here trusts them: each must be a plain name (not empty, not '.' or '..',
    no slash, no backslash, no null byte) and the path, once its symbolic links are resolved, must be inside the directory
    of the dataset, which itself must be inside root_dir.
    Nothing is read: the path does not have to exist, a route keeps its own answer for a dataset or a file that is not there.
    :param root_dir: the directory holding the datasets, DATA_DIR/input or DATA_DIR/output
    :param dataset_name: name of the directory of the dataset
    :param names: the names to follow below the directory of the dataset
    :return: the resolved path, or None when a name is not plain or the path leaves its directory
    """
    for name in (dataset_name, *names):
        if name in ("", ".", "..") or any(char in name for char in "/\\\0"):
            return None

    try:
        root = Path(root_dir).resolve()
        dataset_dir = Path(root, dataset_name).resolve()
        path = Path(dataset_dir, *names).resolve()
    except (OSError, ValueError):  # a name that is no file name (a lone surrogate)
        return None

    if dataset_dir.is_relative_to(root) and path.is_relative_to(dataset_dir):
        return path
    return None


def init_iiif_pipeline_lite(dataset_dir, dataset_name):
    chain = itemize.s(dataset_dir, dataset_name) | generate_manifests.s()
    return chain()
