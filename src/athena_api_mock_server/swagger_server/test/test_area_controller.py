# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.area import Area  # noqa: E501
from swagger_server.models.area_type import AreaType  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.test import BaseTestCase


class TestAreaController(BaseTestCase):
    """AreaController integration test stubs"""

    def test_api_v1_area_post(self):
        """Test case for api_v1_area_post

        Register an area.
        """
        body = Area()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Area',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_area_put(self):
        """Test case for api_v1_area_put

        Update a registered area.
        """
        body = Area()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Area',
            method='PUT',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_areas_post(self):
        """Test case for api_v1_areas_post

        Register multiple areas.
        """
        body = [Area()]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Areas',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_areas_put(self):
        """Test case for api_v1_areas_put

        Update multiple registered areas and register new ones.
        """
        body = [Area()]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Areas',
            method='PUT',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_area_area_id_get(self):
        """Test case for api_v1_session_session_id_area_area_id_get

        Get the registered area for application session.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/Area/{areaId}'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d', area_id=56),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_area_parent_area_id_areas_get(self):
        """Test case for api_v1_session_session_id_area_parent_area_id_areas_get

        Get all the registered child areas of the given area.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/Area/{parentAreaId}/Areas'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d', parent_area_id=56),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_areas_get(self):
        """Test case for api_v1_session_session_id_areas_get

        Get all the registered areas for application session, optionally filtered by area type or parent.
        """
        query_string = [('area_type', AreaType()),
                        ('parent_area_id', 56)]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/Areas'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
