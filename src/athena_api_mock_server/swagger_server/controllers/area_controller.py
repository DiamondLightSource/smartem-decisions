import connexion
import six

from swagger_server.models.area import Area  # noqa: E501
from swagger_server.models.area_type import AreaType  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server import util


def api_v1_area_post(body=None):  # noqa: E501
    """Register an area.

    Sample request:        POST      {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,        \&quot;id\&quot; : 12,        \&quot;areaType\&quot; : \&quot;gridsquare\&quot;      }        or        POST      {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,        \&quot;id\&quot; : 1213,        \&quot;areaType\&quot; : \&quot;foilhole\&quot;,        \&quot;parentId\&quot; : 12      } # noqa: E501

    :param body: The area to be registered.
    :type body: dict | bytes

    :rtype: Area
    """
    if connexion.request.is_json:
        body = Area.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_area_put(body=None):  # noqa: E501
    """Update a registered area.

    Sample request:        PUT      {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,        \&quot;areaType\&quot; : \&quot;gridsquare\&quot;,        \&quot;id\&quot; : 12      } # noqa: E501

    :param body: The area to be updated or to be registered in case not registered yet.
    :type body: dict | bytes

    :rtype: List[Area]
    """
    if connexion.request.is_json:
        body = Area.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_areas_post(body=None):  # noqa: E501
    """Register multiple areas.

    Sample request:        POST      {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,        \&quot;areaType\&quot; : \&quot;gridsquare\&quot;,        \&quot;ids\&quot; : [2, 12, 43]      } # noqa: E501

    :param body: The areas to be registered.
    :type body: list | bytes

    :rtype: List[Area]
    """
    if connexion.request.is_json:
        body = [Area.from_dict(d) for d in connexion.request.get_json()]  # noqa: E501
    return 'do some magic!'


def api_v1_areas_put(body=None):  # noqa: E501
    """Update multiple registered areas and register new ones.

    Sample request:        PUT      {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,        \&quot;areaType\&quot; : \&quot;gridsquare\&quot;,        \&quot;ids\&quot; : [2, 12, 43]      } # noqa: E501

    :param body: The areas to be updated or to be registered in case not registered yet.
    :type body: list | bytes

    :rtype: None
    """
    if connexion.request.is_json:
        body = [Area.from_dict(d) for d in connexion.request.get_json()]  # noqa: E501
    return 'do some magic!'


def api_v1_session_session_id_area_area_id_get(session_id, area_id):  # noqa: E501
    """Get the registered area for application session.

    Sample request:        ../Session/{sessionId}/Area/{areaId} # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_id: Uniquely identifies the area within the application session.
    :type area_id: int

    :rtype: Area
    """
    return 'do some magic!'


def api_v1_session_session_id_area_parent_area_id_areas_get(session_id, parent_area_id):  # noqa: E501
    """Get all the registered child areas of the given area.

    Sample request:        ../Session/{sessionId}/Area/{parentAreaId}/Areas # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param parent_area_id: Uniquely identifies the parent area in the application session.
    :type parent_area_id: int

    :rtype: List[Area]
    """
    return 'do some magic!'


def api_v1_session_session_id_areas_get(session_id, area_type=None, parent_area_id=None):  # noqa: E501
    """Get all the registered areas for application session, optionally filtered by area type or parent.

    Sample request:        ../Session/{sessionId}/Areas?areaType&#x3D;gridsquare&amp;parentAreaId&#x3D;1 # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_type: (Optional)The type of areas to retrieve.
    :type area_type: dict | bytes
    :param parent_area_id: (Optional)The parent area of the areas to retrieve.
    :type parent_area_id: int

    :rtype: List[Area]
    """
    if connexion.request.is_json:
        area_type = AreaType.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
