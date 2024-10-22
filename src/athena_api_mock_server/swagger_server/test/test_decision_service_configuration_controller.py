# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.decision_service_configuration import DecisionServiceConfiguration  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.models.smart_plugin_configuration import SmartPluginConfiguration  # noqa: E501
from swagger_server.test import BaseTestCase


class TestDecisionServiceConfigurationController(BaseTestCase):
    """DecisionServiceConfigurationController integration test stubs"""

    def test_api_v1_configuration_delete(self):
        """Test case for api_v1_configuration_delete

        Delete a registered decision service configuration.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Configuration',
            method='DELETE')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_configuration_get(self):
        """Test case for api_v1_configuration_get

        Get decision service configuration.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Configuration',
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_configuration_plugin_patch(self):
        """Test case for api_v1_configuration_plugin_patch

        Patch the existing smart plugin configuration
        """
        body = SmartPluginConfiguration()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Configuration/Plugin',
            method='PATCH',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_configuration_post(self):
        """Test case for api_v1_configuration_post

        Post new decision service configuration.
        """
        body = DecisionServiceConfiguration()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Configuration',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
