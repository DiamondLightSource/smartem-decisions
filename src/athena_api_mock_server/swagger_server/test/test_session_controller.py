# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.models.session import Session  # noqa: E501
from swagger_server.test import BaseTestCase


class TestSessionController(BaseTestCase):
    """SessionController integration test stubs"""

    def test_api_v1_session_get(self):
        """Test case for api_v1_session_get

        Get a session filtered by session name.
        """
        query_string = [('session_name', 'session_name_example')]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session',
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_id_delete(self):
        """Test case for api_v1_session_id_delete

        Delete a registered application Session from the decision store.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{id}'.format(id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='DELETE')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_id_get(self):
        """Test case for api_v1_session_id_get

        Get an application session.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{id}'.format(id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_id_is_registered_get(self):
        """Test case for api_v1_session_id_is_registered_get

        Check if a session with given id has been registered.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{id}/IsRegistered'.format(id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_post(self):
        """Test case for api_v1_session_post

        Register an application session.
        """
        body = Session()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_sessions_get(self):
        """Test case for api_v1_sessions_get

        Get all registered sessions.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Sessions',
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
