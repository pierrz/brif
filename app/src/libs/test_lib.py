"""
Test oriented library
"""


import os
from pathlib import Path

from src.libs.main_lib import load_json


def get_test_fixtures_path():
    """
    Retrieves the test fixtures directory path
    :return: test fixtures directory path (string)
    """
    return [os.sep, "opt", "app", "test", "fixtures"]


fixtures_path_array = get_test_fixtures_path()


def get_expected_results_dict(test_name):
    """
    Retrieve the expected test results as JSON
    :param test_name: the test name
    :return: test results as JSON
    """
    expected_results_path = Path(
        *fixtures_path_array, f"test_{test_name}_expected_results.json"
    )
    return load_json(expected_results_path)


def get_expected_results_dict_for_specific_file(filename):
    """
    Retrieve specific test results from a filename as JSON
    :param filename: the file name
    :return: test results as JSON
    """
    expected_results_path = Path(*fixtures_path_array, f"test_{filename}.json")
    return load_json(expected_results_path)
