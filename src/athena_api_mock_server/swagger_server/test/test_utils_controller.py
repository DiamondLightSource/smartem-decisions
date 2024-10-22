# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.test import BaseTestCase


class TestUtilsController(BaseTestCase):
    """UtilsController integration test stubs"""

    def test_api_v1_athena_status_get(self):
        """Test case for api_v1_athena_status_get

        Get status from Athena APIs.
        """
        response = self.client.open(
            '/api/smartepu/docs//api/v1/Athena/Status',
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
