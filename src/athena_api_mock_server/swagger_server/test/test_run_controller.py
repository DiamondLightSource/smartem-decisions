# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.models.run import Run  # noqa: E501
from swagger_server.models.run_start import RunStart  # noqa: E501
from swagger_server.models.run_stop import RunStop  # noqa: E501
from swagger_server.test import BaseTestCase


class TestRunController(BaseTestCase):
    """RunController integration test stubs"""

    def test_api_v1_run_start_post(self):
        """Test case for api_v1_run_start_post

        Notify that an application run has started.
        """
        body = RunStart()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/RunStart',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_run_stop_patch(self):
        """Test case for api_v1_run_stop_patch

        Notify that an application run has stopped.
        """
        body = RunStop()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/RunStop',
            method='PATCH',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_run_run_number_get(self):
        """Test case for api_v1_session_session_id_run_run_number_get

        Get an application run.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/Run/{runNumber}'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d', run_number=56),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_runs_get(self):
        """Test case for api_v1_session_session_id_runs_get

        Get all application runs.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/Runs'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
