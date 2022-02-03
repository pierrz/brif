import csv
import io
import json
import os
from pathlib import Path

import src.mappings.item_key_names as ikn
from config import app_config
from lxml import etree
from src.db.database import update_dataset_status
from src.libs.main_lib import (check_directory, count_in_dir, get_dataset_path,
                               get_dirs, get_mapping, step_message_init)
from src.libs.parser_lib import clean_string_from_char, stringify_xpath
from worker import celery


def itemize_csv(file_path, mapping, dir_split):

    with open(file_path, "r", encoding="utf8") as csv_file:

        reader = csv.DictReader(csv_file)
        for row in reader:

            file_id = clean_string_from_char(row[mapping[ikn.uri]])

            # discard empty lines or no URI
            if file_id != "":
                filename = f"{Path(dir_split, file_id)}.json"

                with open(filename, "w", encoding="utf8") as f:
                    str_data = json.dumps(
                        row,
                        indent=4,
                        sort_keys=True,
                        separators=(",", ": "),
                        ensure_ascii=False,
                    )
                    f.write(str_data)
                    f.close()


def itemize_xml(file_path, mapping, dir_split, mode="default"):

    with io.open(file_path, "r", encoding="utf8") as xml_file:
        data_xml = etree.parse(xml_file)
        root = data_xml.getroot()
        root_path = stringify_xpath(root.tag)

        if mode == "edm":
            xsl_filename = Path(
                os.getcwd(), "src", "tasks", "etl", "xslt", "itemize_v1.3.xsl"
            )  # for itemized rdf
            target_xpath = "/rdf:RDF/*"

        else:
            xsl_filename = Path(
                os.getcwd(), "src", "tasks", "etl", "xslt", "itemize_v1.4.xsl"
            )  # for itemized xml
            target_xpath = f"/{root_path}/{mapping['item_tag']}"

        # XSL template modification
        xsl_template = etree.parse(xsl_filename)
        try:
            # modify item xpath
            item_tag = xsl_template.xpath(
                "/xsl:stylesheet/xsl:param[@name='node']",
                namespaces={"xsl": "http://www.w3.org/1999/XSL/Transform"},
            )[0]
            item_tag.attrib["select"] = target_xpath

            # modify output directory
            dir_output = xsl_template.xpath(
                "/xsl:stylesheet/xsl:param[@name='directory']",
                namespaces={"xsl": "http://www.w3.org/1999/XSL/Transform"},
            )[0]
            dir_output.attrib["select"] = f"'{dir_split}'"

        except IndexError:
            print("Could not find xsl:template to update.")

        # Apply itemizing xslt on xml
        data_xml.xslt(xsl_template)


# =================================================
# Itemize dataset -> XSL transformation
@celery.task(name="itemize_dataset")
def itemize(dataset_dir_name: str, dataset_name: str):

    mes_step = "STEP 1 | ITEMIZE"
    dataset_fullname = f"{dataset_dir_name}/{dataset_name}"
    step_message_init(mes_step, dataset_fullname)
    update_dataset_status(dataset_fullname, "in progress")

    # prepare directories
    output_dir = Path(app_config.DATA_DIR, "output")
    dataset_dir = Path(output_dir, dataset_dir_name)
    split_dir, manifest_dir = get_dirs(dataset_dir_name)
    if not output_dir.exists():
        os.mkdir(output_dir)
    check_directory([dataset_dir, split_dir, manifest_dir])

    mapping_data = get_mapping(dataset_dir_name)[0]

    # itemize
    dataset_path = get_dataset_path(dataset_dir_name, dataset_name)
    file_ext = dataset_path.suffix
    if file_ext == ".csv":
        itemize_csv(dataset_path, mapping_data, split_dir)

    else:
        step_message_init(
            mes_step, dataset_fullname, ["Dataset file format currently not accepted."]
        )

    # _________________
    # Message
    count = count_in_dir(split_dir)
    mes_part1 = f"{count} objects itemised"
    step_message_init(mes_step, dataset_fullname, [mes_part1])

    # Pass to next step
    return dataset_dir_name, dataset_name
