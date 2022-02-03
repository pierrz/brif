"""
Module gathering the base classes used for testing purpose
"""
from dataclasses import dataclass
from typing import Dict

from config import app_config
from src.libs.test_lib import (get_expected_results_dict,
                               get_expected_results_dict_for_specific_file)


@dataclass
class EndpointTestBase:
    """
    Base test class to check whether all the endpoints are up and running
    """

    test_name: str

    def __init__(self, client, test_name: str):
        self.test_name = test_name
        self._check_endpoint(client)

    def _get_test_parts(self, client):
        url = f"http://api_test/test/{self.test_name}"
        print(f"TEST: {self.test_name}")
        print(f"=> url: {url}")
        expected_response = get_expected_results_dict(f"{self.test_name}")
        response = client.get(url)
        return response, expected_response

    def _check_endpoint(self, client):
        response, expected_response = self._get_test_parts(client)
        assert response.status_code == 200
        assert response.json() == expected_response


# TODO: discard this class and directly use json instead of string (probably an issue with the encoding)
@dataclass
class EndpointWithAdhocFixtureTestBase(EndpointTestBase):
    @staticmethod
    def replace_app_url(
        json_data: Dict, string_to_replace: str, replacement_param_string: str
    ):
        return str(json_data).replace(string_to_replace, replacement_param_string)


@dataclass
class EndpointCantaloupeTest(EndpointWithAdhocFixtureTestBase):
    """
    Specific implementation covering for erratic responses from Cantaloupe
    (either "extraFormats": ["tif", "gif"] attribute, from V3 or formats attribute with values in different order)
    """

    test_name = "check_cantaloupe"

    def __init__(self, client):
        self._check_endpoint(client)

    def _check_endpoint(self, client):
        response, expected_response = self._get_test_parts(client)
        assert response.status_code == 200

        received_data = response.json()
        # check the order of the 'formats' list:
        if (
            received_data["profile"][1]["formats"]
            == expected_response["profile"][1]["formats"]
        ):
            assert str(received_data) == self.replace_app_url(
                expected_response, "<API_IIIF_IMAGE>", app_config.API_IIIF_IMAGE
            )
        else:
            different_expected_response = get_expected_results_dict_for_specific_file(
                f"{self.test_name}_expected_results_format-order-v2"
            )
            assert str(received_data) == self.replace_app_url(
                different_expected_response,
                "<API_IIIF_IMAGE>",
                app_config.API_IIIF_IMAGE,
            )


@dataclass
class EndpointPipelineTest(EndpointWithAdhocFixtureTestBase):
    """
    Specific implementation for Celery to cover for the APP_BASE_URL param
    """

    test_name = "check_iiif_pipeline"

    def __init__(self, client):
        self._check_endpoint(client)

    def _check_endpoint(self, client):
        response, expected_response = self._get_test_parts(client)
        assert response.status_code == 200
        prepared_string_result = self.replace_app_url(
            expected_response, "<APP_BASE_URL>", app_config.APP_BASE_URL
        ).replace("<API_IIIF_IMAGE_PUBLIC>", app_config.API_IIIF_IMAGE_PUBLIC)
        assert str(response.json()) == prepared_string_result
