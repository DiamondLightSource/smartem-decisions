import connexion
import six

from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server import util


def api_v1_version_get():  # noqa: E501
    """Get Decision Service version.

    Sample request:        ../Version # noqa: E501


    :rtype: str
    """
    return 'do some magic!'
