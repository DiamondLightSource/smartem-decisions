# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.area_state import AreaState  # noqa: E501
from swagger_server.models.area_state_change import AreaStateChange  # noqa: E501
from swagger_server.models.area_type import AreaType  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.test import BaseTestCase


class TestAreaStateController(BaseTestCase):
    """AreaStateController integration test stubs"""

    def test_api_v1_area_state_post(self):
        """Test case for api_v1_area_state_post

        Notify that an area state has changed.
        """
        body = AreaStateChange()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/AreaState',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_area_states_post(self):
        """Test case for api_v1_area_states_post

        Notify state changes of multiple areas.
        """
        body = [AreaState()]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/AreaStates',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_area_area_id_latest_area_state_get(self):
        """Test case for api_v1_session_session_id_area_area_id_latest_area_state_get

        Get the latest state of the registered area.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/Area/{areaId}/LatestAreaState'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d', area_id=56),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_area_state_area_state_id_get(self):
        """Test case for api_v1_session_session_id_area_state_area_state_id_get

        Get a specific area state.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/AreaState/{areaStateId}'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d', area_state_id=56),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_area_states_get(self):
        """Test case for api_v1_session_session_id_area_states_get

        Get multiple area states for the given application session, optionally filtered by area type or parent area id.
        """
        query_string = [('area_type', AreaType()),
                        ('parent_area_id', 56)]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/AreaStates'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
