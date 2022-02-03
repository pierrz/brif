"""
Common utilities
"""


import json

import requests


def fetch_json_from_url(url):
    """Fetch JSON data from given url"""
    response = requests.get(url)
    return response.json()


def load_json(file_path):
    """Load JSON into dict object"""
    with open(file_path, "rt", encoding="utf8") as json_file:
        json_str = json_file.read()
        return json.loads(json_str)
