"""
Module dedicated to the parsing feature of the pipeline
"""

import os
import re
from pathlib import Path

from src.libs.main_lib import load_json

namespaces = load_json(Path(os.getcwd(), "src", "mappings", "namespaces.json"))


def clean_string_from_char(string):
    """
    Punctuation replacer => all punctuation are replaced by '_' (underscore)
    :param string: input string
    :return: cleaned string
    """
    return re.sub(r"[^A-Za-z0-9]", "_", string)


def remove_regexp_from_string(this, that):
    """
    [legacy] specific string remover
    :param this: string input
    :param that: string replacement
    :return: cleaned string
    """
    return re.sub(this, "", that)


def stringify_xpath(tag, mode="default"):

    tag_str = str(tag)
    if tag_str.startswith("{"):
        for key, value in namespaces.items():
            key = f"{key}:"
            value = f"{value}"
            if value in tag_str:
                if mode == "reverse":
                    return tag_str.replace(key, value)
                return tag_str.replace(value, key)


def get_attrib_list_from_el(data, model):
    """
    Generate a list of attribute keys from xml node (manifest generator)
    :param data: node data to process
    :param model:
    :return: data model (currently only relevant for 'EDM')
    """
    output = []
    if len(data.items()) > 0:
        for key, value in data.items():
            if ":" not in key:
                att = key
            else:
                if model == "EDM":
                    att = key
                else:
                    att = stringify_xpath(str(key), mode="reverse")
            output.append({att: value})

    return output


def all_xpath_prefix(xpath):
    """
    Refine xpath string into an all-inclusive path
    :param xpath: xpath to handle
    :return: the cleaned xpath
    """
    splits = xpath.split("/")
    prefix = splits[0] + "/"
    new_xpath = "//" + remove_regexp_from_string(prefix, xpath)
    return new_xpath


def refine_xpath(xpath):
    """
    Extracts the list of xpath and attribute key from a specific node
    :param xpath: xpath to start from
    :return: list of xpath and attribute key
    """
    # if xpath with attribute
    if "/@" in xpath:
        # node
        splits = xpath.split("/")
        if splits[0] in ["edm:ProvidedCHO", "ore:Aggregation", "ore:Proxy"]:
            node = re.sub(r"/@.*", "", xpath)

        elif len(splits) > 2:
            node = all_xpath_prefix(re.sub(r"/@.*", "", xpath))

        else:
            node = "."  # tweak to make mintUri work when short xpath (root/@att)

        # @attribute
        att = re.sub(r".*/@", "", xpath)
        if ":" not in att:
            clean_att = att

        # if namespaced attributes
        else:
            clean_att = stringify_xpath(str(att), mode="reverse")
        output = [node, clean_att]

    else:
        output = [all_xpath_prefix(xpath)]

    return output
