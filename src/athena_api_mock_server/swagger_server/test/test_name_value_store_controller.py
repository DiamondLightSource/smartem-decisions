# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.name_value_record import NameValueRecord  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.test import BaseTestCase


class TestNameValueStoreController(BaseTestCase):
    """NameValueStoreController integration test stubs"""

    def test_api_v1_name_value_store_post(self):
        """Test case for api_v1_name_value_store_post

        Creates a new name-value record.
        """
        body = NameValueRecord()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/NameValueStore',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_name_value_store_session_id_value_id_get(self):
        """Test case for api_v1_name_value_store_session_id_value_id_get

        Get name-value record with provided id.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/NameValueStore/{sessionId}/Value/{id}'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d', id=56),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_name_value_store_session_id_values_get(self):
        """Test case for api_v1_name_value_store_session_id_values_get

        Get all name-value records for the given application session, optionally filtered by area type or/and name.
        """
        query_string = [('area_id', 56),
                        ('name', 'name_example')]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/NameValueStore/{sessionId}/Values'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_name_value_stores_post(self):
        """Test case for api_v1_name_value_stores_post

        Register multiple name-value records.
        """
        body = [NameValueRecord()]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/NameValueStores',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
