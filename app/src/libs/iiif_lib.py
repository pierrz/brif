"""
Module for IIIF data pipeline common utilities
"""


import json
import os
import re
from pathlib import Path

import requests
import src.mappings.item_key_names as ikn
from config import app_config
from src.libs import parser_lib
from src.libs.main_lib import load_json, step_message_init
from src.mappings.parameters import uri_id_prefix
from worker import logger

namespaces = load_json(Path(os.getcwd(), "src", "mappings", "namespaces.json"))

# For reference
# Resource URI Pattern
# Collection => {scheme}://{host}/{prefix}/collection/{name}
# Manifest   => {scheme}://{host}/{prefix}/{identifier}/{level_type}/{name}


def get_iiif_data_base_uri(some_id):
    """
    Mint the IIIF base uri from a given id
    :param some_id: the item id
    :return: the manifest IIIF base uri
    """
    return f"{app_config.API_IIIF_PRES}{some_id}"


def create_metadata_dict(manifest, mode, data):

    logger.info("Metadata dictionary [in progress]")

    if mode != "csv":
        logger.info("Dataset file format not accepted yet")

    items_sort = sorted(data.items())

    for key, value in items_sort:
        if len(value) > 0:
            node_name = "object_" + parser_lib.remove_regexp_from_string("_.*", key)
            if "_" in key:
                lang_val = parser_lib.remove_regexp_from_string(".*_", key)
            else:
                lang_val = "und"

            manifest.set_metadata({"label": node_name, "value": {lang_val: value}})

    logger.info("Metadata dictionary [done]")


def find_imgs(item_id, list_imgs):
    """
    Find related images from complete list
    :param item_id: current manifest id
    :param list_imgs: the complete list of images for this manifest
    :return:
    """
    imgs = []
    for img in list_imgs:
        if item_id in img:
            print(f"--> img: {img}")
            imgs.append(img)

    return sorted(imgs)


def prep_img_lists(dict_imgs):
    """
    Prepares the full image list
    :param dict_imgs: the input dictionary to handle
    :return:
    """
    imgs_list = []
    thumbs_list = []
    imgurl_dict = {}
    for key, value in dict_imgs.items():
        if "__pic" in key:
            imgs_list.append(key)
        else:
            thumbs_list.append(key)

        # dict prepared with relative paths
        rel_path_k = f"{key.split('/')[-2]}/{key.split('/')[-1]}"
        imgurl_dict[rel_path_k] = value

    return imgurl_dict, imgs_list, thumbs_list


def clean_data(data):
    """
    Removes all empty values
    :param data: input data
    :return: the cleansed data
    """

    clean_data = {}
    for key, value in data.items():
        if value != "":
            clean_data[key] = value
    return clean_data


def check_iiif_image(iiif_image_api_uri, img_id):

    # Check if image is actually here
    url_img = f"{iiif_image_api_uri}/{img_id}/info.json"
    logger.info("Check IIIF image server at url %s ...", url_img)
    resp = requests.get(url_img)

    if resp.status_code == 200:
        return True
    return False


def prepare_cantaloupe_uri(dataset_dir_name, img_id):
    return f"{dataset_dir_name}%2F{img_id}"


def generate_canvas(idx, factory, seq, orig_iiif_id):
    """
    Handles all canvases data for a given image
    :param idx: image 'index' in the previous list
    :param factory: manifest factory
    :param seq: sequence to create the canvases in
    :param orig_iiif_id: main IIIF id
    :return: 1 to register a new image
    """
    pos = idx + 1

    logger.info("Generating canvas ...")
    cvs = seq.canvas(
        ident=f"canvas-{pos}", label=f"Picture n°{pos}"
    )  # e.g. uri slug of page-1, and label of Page 1

    # Canvases Thumbs
    cvs.thumbnail = factory.image(
        orig_iiif_id, f"Thumbnail n°{pos}", iiif=True, size="400,"
    )
    cvs.thumbnail.set_hw_from_iiif()

    # Set image height and width, and canvas to same dimensions via IIIF image app
    logger.info("Generating annotation ...")
    anno = cvs.annotation(ident=f"annotation-{pos}")
    img = anno.image(orig_iiif_id, iiif=True)
    img.set_hw_from_iiif()
    cvs.height = img.height
    cvs.width = img.width

    return 1


def create_canvas_for_imgs(
    factory,
    manifest,
    dataset_dir_name,
    check_thumb,
    meta_pack,
):

    logger.info("Generating main sequence ...")

    item_thumb = meta_pack[ikn.uri_thumb]
    list_img_uris = meta_pack[ikn.list_img_uris]

    seq = manifest.sequence(ident="main-sequence")  # generic id/name
    # create n canvas/img/anno based on pictures count
    available_imgs = 0
    for idx, orig_img in enumerate(list_img_uris):

        # filenames
        orig_iiif_id = prepare_cantaloupe_uri(dataset_dir_name, orig_img)

        if check_iiif_image(factory.default_base_image_uri, orig_iiif_id) is False:
            continue

        available_imgs += generate_canvas(idx, factory, seq, orig_iiif_id)
        thumb_uri = prepare_cantaloupe_uri(dataset_dir_name, item_thumb)
        check_thumb += implement_thumbnail(
            factory, manifest, thumb_uri, check_thumb, idx
        )

    return available_imgs


def implement_thumbnail(factory, manifest, thumb_uri, check_thumb, pos=None):

    logger.info("Generate IIIF data for thumbnail ...")
    if check_thumb == 0:

        if pos is not None:
            thumb_label = f"Thumbnail {pos}"
        thumb_label = "Thumbnail"

        manifest.thumbnail = factory.image(
            f"{thumb_uri}", thumb_label, iiif=True, size="400,"
        )
        manifest.thumbnail.set_hw_from_iiif()
        return 1

    return 0


""" IIIF Manifest generator utilities"""


def mint_uri(string):
    raw_uri = re.sub(r"h?t?t?p?s?:?\/\/w*\.?", "", string)
    uri = parser_lib.clean_string_from_char(raw_uri)
    return uri


def manifest_serialize_meta_init(source, manifest, prefix, tag, model):
    """
    Serializer for the metadata section
    Prepare variables and list all children from current tag aka xpath
    used on root for custom | on core classes for EDM
    :param source: source data
    :param manifest: current manifest object
    :param prefix: prefix to use
    :param tag: current tag
    :param model: current data model
    :return: implements the constructed metadata into the manifest
    """
    list_nodes = source.findall(tag, namespaces=namespaces)
    if list_nodes is not None:
        i = 0
        for node in list_nodes:
            #  Cont. class nodes (more complete parsing)
            if prefix not in ["object", "aggregation"]:

                # create individual prefix
                i += 1
                if i == 1:
                    full_prefix = prefix + "_"
                else:
                    full_prefix = prefix + str(i) + "_"

                # include rdf:about Uri in metadata
                node_id = node.attrib[
                    "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
                ]
                node_label = full_prefix + "rdf:about"
                manifest.set_metadata({"label": node_label, "value": {"@uri": node_id}})

            # Object and Aggregation
            else:
                full_prefix = prefix + "_"

            manifest_serialize_meta(node, full_prefix, manifest, model)


def refine_attribute_name(tag_attribute):
    """
    Metadata serializer: go through all the non mandatory stuff.
    Applied on 1 node and includes the result in 'metadata'.
    :param tag_attribute: attribute to check
    :return: the list of attribute tag names
    """

    length = len(tag_attribute)
    attrib_name_list = []

    for att_d in tag_attribute:

        key, value = list(att_d.items())[0]

        if length == 1:
            if "lang" in key or "{http://www.w3.org/XML/1998/namespace}lang" in key:
                main_att = value

            elif "resource" in key:
                main_att = mint_attribute_name_with_uri(key, value)

            else:
                main_att = mint_attribute_name(key, value)

        elif length > 1:
            attrib_name_list.append((mint_attribute_name(key, value)))

    if length == 1:
        return main_att
    return attrib_name_list


def mint_attribute_name(key, value):
    att_name = "@" + key + "_" + value
    return att_name


def mint_attribute_name_with_uri(key, value):
    att_name = str()
    refined_list = []
    for string in ["uri", "resource", "about"]:

        if string in parser_lib.stringify_xpath(key):
            att_name += uri_id_prefix + parser_lib.stringify_xpath(key)
            refined_list += [att_name]
            refined_list += [value]

    if len(att_name) == 0:
        att_name = mint_attribute_name(key, value)
        refined_list += att_name

    return refined_list


def meta_for_custom_creator(data, att_dict, main_att):
    if data.text:
        if len(data.text) > 0:
            att_dict["und"] = data.text
    else:
        if not isinstance(type(main_att[0]), str):
            att_dict[main_att[0][0]] = main_att[0][1]
        else:
            att_dict[main_att[0]] = main_att[1]

    return att_dict


def meta_for_default_nodes(data, att_dict, main_att):
    if isinstance(main_att, list):
        str_attrs = str(main_att)[1:-1]
    else:
        str_attrs = main_att

    if data.text:
        if len(data.text) > 0:
            att_dict[str_attrs] = data.text
    else:
        if not isinstance(type(main_att[0]), str):
            att_dict[main_att[0][0]] = main_att[0][1]
        else:
            att_dict[main_att[0]] = main_att[1]

    return att_dict, str_attrs


def prepare_metadata_from_attributes(node_name, list_att, data, att_dict):

    # prepare att. list
    main_att = refine_attribute_name(list_att)

    if uri_id_prefix in main_att and node_name == "custom_creator":
        att_dict = meta_for_custom_creator(data, att_dict, main_att)
        return att_dict

    att_dict, str_attrs = meta_for_default_nodes(data, att_dict, main_att)
    return att_dict, str_attrs


def metadata_dict(data, node_name, list_att, manifest):

    att_dict = {}
    length = len(list_att)

    # if no attributes
    if length == 0:
        att_dict["und"] = data.text
        manifest.set_metadata({"label": node_name, "value": att_dict})
        if node_name == "custom_creator":
            return "und"

    else:

        att_dict, str_attrs = prepare_metadata_from_attributes(
            node_name, list_att, data, att_dict
        )

        for value in att_dict.values():
            # Discards empty attribute values
            if value is not None:
                manifest.set_metadata({"label": node_name, "value": att_dict})

        if node_name == "custom_creator":
            return [str_attrs, att_dict[str_attrs]]


def sort_tags(parent_node):
    """
    Sort child nodes from a parent node, and clean their tag names
    :param parent_node: the input parent node
    :return: lists of raw and cleaned tags, both sorted
    """
    tags_raw = []
    tags_sort = []
    for node in parent_node:
        tags_raw.append(node.tag)
        tags_sort.append(re.sub(r".*}", "", node.tag))
    tags_sorted = sorted(set(tags_sort))
    raw_tags = list(set(tags_raw))

    return raw_tags, tags_sorted


def manifest_serialize_meta(parent_node, prefix, manifest, model):

    raw_tags, tags_sorted = sort_tags(parent_node)

    # prepare sorted nodes list
    sorted_etree = []
    for tag_name in tags_sorted:
        for raw_tag in raw_tags:
            if tag_name in raw_tag:
                for child in parent_node.findall(raw_tag):
                    sorted_etree.append(child)
                break

    # all fields
    for data in sorted_etree:
        # include the nodes in metadata
        clean_tag = parser_lib.stringify_xpath(data.tag)  # to check with EDM
        list_att = parser_lib.get_attrib_list_from_el(data, model)
        node_name = prefix + clean_tag

        # all the rest
        metadata_dict(data, node_name, list_att, manifest)


def write_file(filepath: Path, str_data: str):
    with open(filepath, "w", encoding="utf8") as new_file:
        new_file.write(replace_cantaloupe_container_prefix(str_data))
        logger.info("- '%s' file created", filepath.name)
        new_file.close()


def write_manifest_sides(data, output_dir, filename, mode="prezi-data"):
    """
    Write manifest to specific filepath
    :param data: data to write
    :param output_dir: output directory
    :param filename: filename
    :param mode: hack to tap into the .toString method
    :return:
    """

    if mode == "prezi-data":
        str_data = data.toString(compact=False)
    else:
        str_data = json.dumps(data)

    if not Path(output_dir).exists():
        os.mkdir(output_dir)

    filepath = Path(output_dir, f"{filename}.json")
    write_file(filepath, str_data)


def write_specific_node_data(node_data, node_name, manifest_dir_path):
    """
    Initiates the writing of data files for a specific node/level
    :param node_data: data for the considered node
    :param node_name: node/level name
    :param manifest_dir_path: path to the manifest output directory
    :return: does its thing
    """
    regexp = f".*/{node_name}/"

    if node_name == "annotation":
        filename = re.sub(rf"{regexp}", "", node_data["@id"].replace(".json", ""))
    else:
        filename = re.sub(rf"{regexp}", "", node_data.id.replace(".json", ""))

    node_dir_path = Path(manifest_dir_path, node_name)

    try:
        if node_name == "annotation":
            write_manifest_sides(node_data, node_dir_path, filename, mode="anno")
        else:
            write_manifest_sides(node_data, node_dir_path, filename)
    except Exception:
        logger.info("Issue while creating annotations: %s", Exception)


def write_side_data(sequences, manifest_dir_path):
    """
    Initiates the writing of all side data files per manifest
    :param sequences: sequences data from the manifest data
    :param manifest_dir_path: path to the manifest output directory
    :return: does its thing
    """

    for seq in sequences:
        try:
            write_specific_node_data(seq, "sequence", manifest_dir_path)
        except AttributeError:
            logger.info("- /!\\ The manifest does not have any sequence.")

        canvases = seq.canvases
        for cvs in canvases:

            try:
                write_specific_node_data(cvs, "canvas", manifest_dir_path)
            except AttributeError:
                logger.info("- /!\\ The manifest does not have any canvas.")

            try:
                cvs_json = cvs.toJSON(top=True)
                annotation = cvs_json["images"][0]
                write_specific_node_data(annotation, "annotation", manifest_dir_path)
            except AttributeError:
                logger.info("- /!\\ The manifest does not have any annotation.")


def replace_cantaloupe_container_prefix(str_data):
    return str_data.replace(app_config.API_IIIF_IMAGE, app_config.API_IIIF_IMAGE_PUBLIC)


def write_manifest(data, output_dir):

    str_data = data.toString(compact=False)
    if Path(output_dir).exists() is False:
        os.mkdir(output_dir)

    filepath = Path(output_dir, f"{ikn.manif_name}.json")
    write_file(filepath, str_data)


def write_collection(manifest_dir, coll):
    coll_dir = Path(manifest_dir, ikn.coll_name)
    write_manifest_sides(coll, coll_dir, ikn.coll_manif_name)


def final_logs(mes_step, dataset_dir_name, dataset_name, total, valid, valid_imgs):
    mes_part0 = f"{total - valid} invalid manifest(s) (neither URI nor label)"
    mes_part1 = f"{valid} manifest(s) created"
    mes_part2 = f"{valid_imgs} available IIIF image(s)"
    mes_part3 = "1 collection manifest created"
    step_message_init(
        mes_step,
        f"{dataset_dir_name}/{dataset_name}",
        [mes_part0, mes_part1, mes_part2, mes_part3],
    )
