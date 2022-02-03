from pathlib import Path, PurePath

import src.mappings.item_key_names as ikn
from config import app_config
from src.libs.iiif_csv_lib import transform_csv_item
from src.libs.iiif_lib import (check_iiif_image, create_canvas_for_imgs,
                               create_metadata_dict, implement_thumbnail,
                               prepare_cantaloupe_uri, write_manifest,
                               write_side_data)
from src.libs.main_lib import get_dirs
from worker import celery, logger


def generate_manifest(factory, data, meta_pack, mode, dataset_dir_name):

    try:
        manifest_base_uri = (
            f"{app_config.API_IIIF_PRES}{dataset_dir_name}/{meta_pack[ikn.uri]}"
        )
        factory.set_base_prezi_uri(manifest_base_uri)
        logger.info("---- manifest base URI is '%s' ----", manifest_base_uri)

        # create manifest object with generic name (id based on base_prezi_uri)
        manifest = factory.manifest(
            ident=f"{ikn.manif_name}", label=meta_pack[ikn.label]
        )
        logger.info(
            "Manifest '%s/%s - %s' [in progress]",
            dataset_dir_name,
            meta_pack[ikn.uri],
            meta_pack[ikn.label],
        )

        # Main fields
        if meta_pack[ikn.uri_raw].startswith("http"):
            manifest.related = meta_pack[ikn.uri_raw]
        if ikn.description in meta_pack:
            manifest.description = meta_pack[ikn.description]
        if ikn.date in meta_pack:
            manifest.navDate = meta_pack[ikn.date]
        if ikn.provider in meta_pack:
            manifest.attribution = meta_pack[ikn.provider]

        # metadata & technical fields
        create_metadata_dict(manifest, mode, data)
        manifest.viewingDirection = "left-to-right"
        manifest.viewingHint = "individuals"

        # Thumb (if provided)
        check_thumb = 0
        thumb_uri = prepare_cantaloupe_uri(dataset_dir_name, meta_pack[ikn.uri_thumb])
        if check_iiif_image(factory.default_base_image_uri, thumb_uri):
            check_thumb += implement_thumbnail(
                factory,
                manifest,
                thumb_uri,
                check_thumb,
            )

        # Pictures
        available_imgs = create_canvas_for_imgs(
            factory, manifest, dataset_dir_name, check_thumb, meta_pack
        )

        return manifest, available_imgs

    except Exception:
        logger.info("/!\\ ISSUE WITH DATA/MANIFEST")
        logger.info(Exception)
        return None


@celery.task()
def generate_and_write_manifest(
    item,
    mapping,
    mode,
    factory,
    dataset_dir_name,
):

    item_path = PurePath(item)

    if mode == "csv":
        data, meta_pack = transform_csv_item(item_path, mapping)

    manifest, available_imgs = generate_manifest(
        factory, data, meta_pack, mode, dataset_dir_name
    )

    if manifest is not None:

        # write manifest
        logger.info("Writing manifest and side data ...")
        manifest_output_dir = Path(get_dirs(dataset_dir_name)[1], meta_pack[ikn.uri])
        write_manifest(manifest, manifest_output_dir)
        logger.info(
            "--> Manifest '%s/manifest.json' successfully created.", meta_pack[ikn.uri]
        )

        # write side files
        write_side_data(manifest.sequences, manifest_output_dir)
        logger.info("-->  All related data files successfully created.")

        return 1, available_imgs, manifest

    return 0
