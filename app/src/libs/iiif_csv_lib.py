import src.mappings.item_key_names as ikn
from src.libs.iiif_lib import clean_data, mint_uri
from src.libs.main_lib import load_json
from src.libs.parser_lib import remove_regexp_from_string
from src.mappings.parameters import null_var
from worker import logger


def prepare_labels_csv(data, key, value):
    """
    sugar coating for multilingual metadata
    :param data: node data
    :param key: key
    :param value: value
    :return: the aligned metadata
    """
    node_name = remove_regexp_from_string("_.*", key)
    if value is not None:
        val = value
    else:
        for key, value in data.items():
            if node_name in key:
                val = value
                break

    if val == "":
        return "N/A"
    return val


def get_meta_pack(main_fields, mapping, data):
    meta_pack = {}
    for key in main_fields:
        if mapping[key] in data:
            meta_pack[key] = data[mapping[key]]
        elif key == "ip" and mapping[key] not in data:
            meta_pack[key] = "https://rightsstatements.org/vocab/UND/1.0/"
        else:
            meta_pack[key] = null_var
    return meta_pack


def transform_csv_item(item_path, mapping):
    data = load_json(item_path)
    data = clean_data(data)

    # MANDATORY (uri and label)
    try:
        item_uri = data[mapping[ikn.uri]]
        item_uri_raw = item_uri
        item_uri_id = mint_uri(item_uri_raw)
    except KeyError:
        logger.info("/!\\ This item is missing an URI and cannot be transformed")
        return 1

    try:
        item_label = data[mapping[ikn.label]]
        item_label = prepare_labels_csv(data, mapping[ikn.label], item_label)
    except KeyError:
        logger.info("/!\\ This item is missing a label")
        item_label = null_var

    main_fields = [ikn.uri_thumb, ikn.date, ikn.ip, ikn.provider]
    meta_pack = get_meta_pack(main_fields, mapping, data)

    list_img_uris = []
    for k in data.keys():
        if mapping[ikn.uri_image] in k and "_thumb" not in k:
            list_img_uris.append(data[k])

    meta_pack = {
        **meta_pack,
        ikn.uri: item_uri_id,
        ikn.uri_raw: item_uri_raw,
        ikn.label: item_label,
        ikn.list_img_uris: list_img_uris,
    }

    try:
        item_description = prepare_labels_csv(
            data, mapping[ikn.description], data[mapping[ikn.description]]
        )
        meta_pack[ikn.description] = item_description

    except KeyError:
        logger.info("/!\\ This item is missing a description")
        meta_pack[ikn.description] = null_var

    return data, meta_pack
