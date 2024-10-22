# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.test import BaseTestCase


class TestVersionController(BaseTestCase):
    """VersionController integration test stubs"""

    def test_api_v1_version_get(self):
        """Test case for api_v1_version_get

        Get Decision Service version.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Version',
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
