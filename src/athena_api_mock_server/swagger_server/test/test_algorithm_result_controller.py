# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.algorithm_result_record import AlgorithmResultRecord  # noqa: E501
from swagger_server.models.algorithm_result_type import AlgorithmResultType  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.test import BaseTestCase


class TestAlgorithmResultController(BaseTestCase):
    """AlgorithmResultController integration test stubs"""

    def test_api_v1_session_session_id_algorithm_result_get(self):
        """Test case for api_v1_session_session_id_algorithm_result_get

        Get algorithm result using session id, name and area id.
        """
        query_string = [('area_id', 56),
                        ('name', AlgorithmResultType())]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/AlgorithmResult'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_algorithm_results_get(self):
        """Test case for api_v1_session_session_id_algorithm_results_get

        Get all algorithm results using session id, name and parent area id.
        """
        query_string = [('parent_area_id', 56),
                        ('name', AlgorithmResultType())]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/AlgorithmResults'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_latest_algorithm_result_get(self):
        """Test case for api_v1_session_session_id_latest_algorithm_result_get

        Get latest algorithm result using session id, name and parent area id.
        """
        query_string = [('parent_area_id', 56),
                        ('name', AlgorithmResultType())]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/LatestAlgorithmResult'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
