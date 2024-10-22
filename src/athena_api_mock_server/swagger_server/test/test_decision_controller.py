# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.decision_record import DecisionRecord  # noqa: E501
from swagger_server.models.decision_type import DecisionType  # noqa: E501
from swagger_server.models.plugin_type import PluginType  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.test import BaseTestCase


class TestDecisionController(BaseTestCase):
    """DecisionController integration test stubs"""

    def test_api_v1_decision_post(self):
        """Test case for api_v1_decision_post

        Register a decision.
        """
        body = DecisionRecord()
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Decision',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_decisions_post(self):
        """Test case for api_v1_decisions_post

        Register multiple decisions.
        """
        body = [DecisionRecord()]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Decisions',
            method='POST',
            data=json.dumps(body),
            content_type='application/json-patch+json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_all_decisions_delete(self):
        """Test case for api_v1_session_session_id_all_decisions_delete

        Delete all decisions.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/AllDecisions'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='DELETE')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_decision_decision_id_get(self):
        """Test case for api_v1_session_session_id_decision_decision_id_get

        Get a specific decision.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/Decision/{decisionId}'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d', decision_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_decisions_delete(self):
        """Test case for api_v1_session_session_id_decisions_delete

        Delete all matching decisions. The match is performed on SessionId, AreaId and DecisionType (the later if specified)
        """
        query_string = [('area_id', 56),
                        ('decision_type', DecisionType())]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/Decisions'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='DELETE',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_decisions_get(self):
        """Test case for api_v1_session_session_id_decisions_get

        Get all the decisions that are available for the provided area ids, and optionally filtered by type.
        """
        query_string = [('area_ids', 56),
                        ('decision_type', DecisionType()),
                        ('plugin_type', PluginType())]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/Decisions'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_latest_decision_get(self):
        """Test case for api_v1_session_session_id_latest_decision_get

        Get the most recent decision that is available for the given area.
        """
        query_string = [('area_id', 56),
                        ('decision_type', DecisionType()),
                        ('plugin_type', PluginType())]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/LatestDecision'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_session_session_id_timed_decision_get(self):
        """Test case for api_v1_session_session_id_timed_decision_get

        Get the most recent decision that is available for the given area.
        """
        query_string = [('area_id', 56),
                        ('decision_type', DecisionType()),
                        ('timeout', 56),
                        ('plugin_type', PluginType())]
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Session/{sessionId}/TimedDecision'.format(session_id='38400000-8cf0-11bd-b23e-10b96e4ef00d'),
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
