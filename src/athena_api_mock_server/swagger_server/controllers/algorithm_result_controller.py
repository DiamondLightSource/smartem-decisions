import connexion
import six

from swagger_server.models.algorithm_result_record import AlgorithmResultRecord  # noqa: E501
from swagger_server.models.algorithm_result_type import AlgorithmResultType  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server import util


def api_v1_session_session_id_algorithm_result_get(session_id, area_id=None, name=None):  # noqa: E501
    """Get algorithm result using session id, name and area id.

    Sample request:        ../Session/{sessionId}/AlgorithmResult?areaId&#x3D;12&amp;name&#x3D;motioncorrection # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_id: Uniquely identifies the area within the session.
    :type area_id: int
    :param name: Name type of the algorithm result.
    :type name: dict | bytes

    :rtype: AlgorithmResultRecord
    """
    if connexion.request.is_json:
        name = AlgorithmResultType.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_session_session_id_algorithm_results_get(session_id, parent_area_id=None, name=None):  # noqa: E501
    """Get all algorithm results using session id, name and parent area id.

    Sample request:        ../Session/{sessionId}/AlgorithmResult?parentAreaId&#x3D;12&amp;name&#x3D;motioncorrection # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param parent_area_id: Uniquely identifies the parent area within the session.
    :type parent_area_id: int
    :param name: Name of the algorithm result.
    :type name: dict | bytes

    :rtype: List[AlgorithmResultRecord]
    """
    if connexion.request.is_json:
        name = AlgorithmResultType.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_session_session_id_latest_algorithm_result_get(session_id, parent_area_id=None, name=None):  # noqa: E501
    """Get latest algorithm result using session id, name and parent area id.

    Sample request:        ../Session/{sessionId}/LatestAlgorithmResult?parentAreaId&#x3D;12&amp;name&#x3D;motioncorrection # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param parent_area_id: Uniquely identifies the parent area within the session.
    :type parent_area_id: int
    :param name: Name of the algorithm result.
    :type name: dict | bytes

    :rtype: AlgorithmResultRecord
    """
    if connexion.request.is_json:
        name = AlgorithmResultType.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
