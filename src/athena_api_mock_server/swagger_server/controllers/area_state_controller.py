import connexion
import six

from swagger_server.models.area_state import AreaState  # noqa: E501
from swagger_server.models.area_state_change import AreaStateChange  # noqa: E501
from swagger_server.models.area_type import AreaType  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server import util


def api_v1_area_state_post(body=None):  # noqa: E501
    """Notify that an area state has changed.

    Sample request:        POST      {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;              \&quot;areaId\&quot; : 12        \&quot;state\&quot; : \&quot;started\&quot;      } # noqa: E501

    :param body: The updated area state.
    :type body: dict | bytes

    :rtype: AreaState
    """
    if connexion.request.is_json:
        body = AreaStateChange.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_area_states_post(body=None):  # noqa: E501
    """Notify state changes of multiple areas.

    Sample request:        POST      {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;              \&quot;areaIds\&quot; : [12, 14]        \&quot;areaStates\&quot; : [\&quot;started\&quot;, \&quot;queued\&quot;]      } # noqa: E501

    :param body: The updated area states.
    :type body: list | bytes

    :rtype: List[AreaState]
    """
    if connexion.request.is_json:
        body = [AreaState.from_dict(d) for d in connexion.request.get_json()]  # noqa: E501
    return 'do some magic!'


def api_v1_session_session_id_area_area_id_latest_area_state_get(session_id, area_id):  # noqa: E501
    """Get the latest state of the registered area.

    Sample request:        ../Session/{sessionId}/Area/{areaId}/LatestAreaState # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_id: Uniquely identifies the area within the application session.
    :type area_id: int

    :rtype: AreaState
    """
    return 'do some magic!'


def api_v1_session_session_id_area_state_area_state_id_get(session_id, area_state_id):  # noqa: E501
    """Get a specific area state.

    Sample request:        ../Session/{sessionId}/AreaState/{areaStateId} # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_state_id: Uniquely identifies the area state within the application session.
    :type area_state_id: int

    :rtype: AreaState
    """
    return 'do some magic!'


def api_v1_session_session_id_area_states_get(session_id, area_type=None, parent_area_id=None):  # noqa: E501
    """Get multiple area states for the given application session, optionally filtered by area type or parent area id.

    Sample request:        ../Session/{sessionId}/AreaStates      ../Session/{sessionId}/AreaStates?areaType&#x3D;gridsquare      ../Session/{sessionId}/AreaStates?parentId&#x3D;123 # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_type: (Optional)The type of areas to retrieve.
    :type area_type: dict | bytes
    :param parent_area_id: (Optional)The parent area of the area states to retrieve.
    :type parent_area_id: int

    :rtype: List[AreaState]
    """
    if connexion.request.is_json:
        area_type = AreaType.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
