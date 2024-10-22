# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.application_state import ApplicationState  # noqa: E501
from swagger_server.models.application_state_change import ApplicationStateChange  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.test import BaseTestCase


class TestApplicationStateController(BaseTestCase):
    """ApplicationStateController integration test stubs"""

    def test_api_v1_current_application_state_get(self):
        """Test case for api_v1_current_application_state_get

        Get the current (or last known) state of the application.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/CurrentApplicationState',
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_current_application_state_post(self):
        """Test case for api_v1_current_application_state_post

        Notify the current application state.
        """
        body = ApplicationStateChange()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/CurrentApplicationState',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_application_states_get(self):
        """Test case for api_v1_session_session_id_application_states_get

        Get all the tracked application states for the given application session.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/ApplicationStates'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
