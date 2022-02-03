import csv
import os
import random
from pathlib import Path
from typing import Dict, Union

import src.mappings.item_key_names as ikn
from src.db.models import InputDataset
from src.libs.main_lib import load_json
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


def init_iiif_pipeline_lite(dataset_dir, dataset_name):
    chain = itemize.s(dataset_dir, dataset_name) | generate_manifests.s()
    return chain()
