import datetime
import os
from pathlib import Path, PurePath

import src.mappings.item_key_names as ikn
from config import app_config
from iiif_prezi.factory import ManifestFactory
from src.libs.iiif_lib import final_logs, write_collection
from src.libs.main_lib import (count_in_dir, get_dataset_path, get_dirs,
                               get_mapping, init_message, step_message_init)
from src.tasks.etl.task_etl_generate_single_manifest import \
    generate_and_write_manifest
from worker import celery


def transform_input_files(
    split_dir, collection, mapping, mode, factory, dataset_dir_name
):

    # TODO: check/improve that with multithreading
    # generate all manifests
    valid = valid_imgs = pos = 0
    total = count_in_dir(split_dir)
    with os.scandir(split_dir) as iterator:
        for item in iterator:
            if not item.name.startswith(".") and item.is_file():

                pos += 1
                init_message(item.name, "Item", pos, total)

                i, available_imgs, manifest = generate_and_write_manifest(
                    item,
                    mapping,
                    mode,
                    factory,
                    dataset_dir_name,
                )
                valid += i
                valid_imgs += available_imgs

                # link manifest with the collection
                collection.add_manifest(manifest)

    return valid, valid_imgs, total


def create_and_set_factory(dataset_dir_name, manifest_dir):
    # Init factory & main dirs
    factory = ManifestFactory()
    # 'warn' -> warnings on, default level | 'error' -> warnings off | 'error_on_warning' -> warnings as errors
    factory.set_debug("warn")

    # factory settings
    factory_base_url = f"{app_config.API_IIIF_PRES}{dataset_dir_name}"
    factory.set_base_prezi_uri(
        factory_base_url
    )  # resources location on the web // prefix on main URIs
    factory.set_base_prezi_dir(str(manifest_dir))  # resources location, locally
    factory.set_base_image_uri(
        app_config.API_IIIF_IMAGE
    )  # Default Image API information
    factory.set_iiif_image_info(
        2.0, 2
    )  # Version, ComplianceLevel (not working for 3.0, needs hack)

    return factory


def create_collection(factory, dataset_dir_name):
    # collection
    coll = factory.collection(
        ident=f"{ikn.coll_name}/{ikn.coll_manif_name}",
        label=f"Collection manifest for the dataset '{dataset_dir_name}'",
    )
    coll.description = (
        f"This manifest gathers all IIIF resouces from the dataset '{dataset_dir_name}'"
    )
    coll.metadata = {"Date": datetime.date.today().isoformat()}
    return coll


@celery.task()
def generate_manifests(dataset_meta):

    mes_step = "STEP 2 | IIIF MANIFESTS"

    # main variables
    dataset_dir_name, dataset_name = dataset_meta
    dataset_fullname = f"{dataset_dir_name}/{dataset_name}"

    step_message_init(mes_step, dataset_fullname)
    dataset_path = get_dataset_path(dataset_dir_name, dataset_name)
    mapping_json, mapping_type = get_mapping(dataset_path)
    mode = dataset_path.suffix[1:]
    output_dir = Path(PurePath(os.getcwd()).parent, "data", "output")
    dataset_dir = Path(output_dir, dataset_dir_name)
    split_dir, manifest_dir = get_dirs(dataset_dir)

    # init factory & collection
    factory = create_and_set_factory(dataset_dir_name, manifest_dir)
    collection = create_collection(factory, dataset_dir_name)

    valid, valid_imgs, total = transform_input_files(
        split_dir, collection, mapping_json, mode, factory, dataset_dir_name
    )

    # write collection and final logs
    write_collection(manifest_dir, collection)
    final_logs(mes_step, dataset_dir_name, dataset_name, total, valid, valid_imgs)

    results_pack = {
        "fullname": dataset_fullname,
        "dir_name": dataset_dir_name,
        "total": total,
        "valid": valid,
        "valid_img": valid_imgs,
        "mapping": mapping_type,
        "status": "transformed",
    }

    return results_pack
