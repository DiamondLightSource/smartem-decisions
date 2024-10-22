import connexion
import six

from swagger_server.models.decision_record import DecisionRecord  # noqa: E501
from swagger_server.models.decision_type import DecisionType  # noqa: E501
from swagger_server.models.plugin_type import PluginType  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server import util


def api_v1_decision_post(body=None):  # noqa: E501
    """Register a decision.

    Sample request:        POST      {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,        \&quot;areaId\&quot; : 12,        \&quot;decisionType\&quot; : \&quot;include\&quot;,        \&quot;decisionValue\&quot; : \&quot;false\&quot;,        \&quot;decidedBy\&quot; : \&quot;web client\&quot;,        \&quot;details\&quot; : \&quot;bad gridsquare\&quot;      } # noqa: E501

    :param body: The decision to be registered.
    :type body: dict | bytes

    :rtype: DecisionRecord
    """
    if connexion.request.is_json:
        body = DecisionRecord.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_decisions_post(body=None):  # noqa: E501
    """Register multiple decisions.

    Sample request:        POST      {          [              {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,                \&quot;areaId\&quot; : 10,                \&quot;decisionType\&quot; : \&quot;include\&quot;,                \&quot;decisionValue\&quot; : \&quot;false\&quot;,                \&quot;decidedBy\&quot; : \&quot;web client\&quot;},                \&quot;details\&quot; : \&quot;bad gridsquare\&quot;              },              {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,                \&quot;areaId\&quot; : 11,                \&quot;decisionType\&quot; : \&quot;include\&quot;,                \&quot;decisionValue\&quot; : \&quot;false\&quot;,                \&quot;decidedBy\&quot; : \&quot;web client\&quot;,                \&quot;details\&quot; : \&quot;bad gridsquare\&quot;              }          ]      } # noqa: E501

    :param body: The decisions to be registered.
    :type body: list | bytes

    :rtype: List[DecisionRecord]
    """
    if connexion.request.is_json:
        body = [DecisionRecord.from_dict(d) for d in connexion.request.get_json()]  # noqa: E501
    return 'do some magic!'


def api_v1_session_session_id_all_decisions_delete(session_id):  # noqa: E501
    """Delete all decisions.

    Sample request:        ../Session/{sessionId}/AllDecisions # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 

    :rtype: None
    """
    return 'do some magic!'


def api_v1_session_session_id_decision_decision_id_get(session_id, decision_id):  # noqa: E501
    """Get a specific decision.

    Sample request:        ../Session/{sessionId}/Decision/{decisionId} # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param decision_id: The id of a specific decision record.
    :type decision_id: 

    :rtype: DecisionRecord
    """
    return 'do some magic!'


def api_v1_session_session_id_decisions_delete(session_id, area_id=None, decision_type=None):  # noqa: E501
    """Delete all matching decisions. The match is performed on SessionId, AreaId and DecisionType (the later if specified)

    Sample request:      ../Session/{sessionId}/Decisions?areaId&#x3D;12&amp;decisionType&#x3D;include # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_id: Uniquely identifies the area within the application session.
    :type area_id: int
    :param decision_type: The type of decision.
    :type decision_type: dict | bytes

    :rtype: None
    """
    if connexion.request.is_json:
        decision_type = DecisionType.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_session_session_id_decisions_get(session_id, area_ids=None, decision_type=None, plugin_type=None):  # noqa: E501
    """Get all the decisions that are available for the provided area ids, and optionally filtered by type.

    Sample request:        ../Session/{sessionId}/Decisions?areaId&#x3D;1&amp;areaId&#x3D;2      ../Session/{sessionId}/Decisions?areaId&#x3D;1&amp;areaId&#x3D;2&amp;areaId&#x3D;3&amp;decisionType&#x3D;include # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_ids: Uniquely identify the area(s) within the application session.
    :type area_ids: List[int]
    :param decision_type: The type of decision.
    :type decision_type: dict | bytes
    :param plugin_type: The plugin was used in taking the decision.
    :type plugin_type: dict | bytes

    :rtype: List[DecisionRecord]
    """
    if connexion.request.is_json:
        decision_type = DecisionType.from_dict(connexion.request.get_json())  # noqa: E501
    if connexion.request.is_json:
        plugin_type = PluginType.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_session_session_id_latest_decision_get(session_id, area_id=None, decision_type=None, plugin_type=None):  # noqa: E501
    """Get the most recent decision that is available for the given area.

    Sample request:        ../Session/{sessionId}/LatestDecision?areaId&#x3D;12&amp;decisionType&#x3D;include # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_id: Uniquely identifies the area within the application session.
    :type area_id: int
    :param decision_type: The type of decision.
    :type decision_type: dict | bytes
    :param plugin_type: The plugin was used in taking the decision.
    :type plugin_type: dict | bytes

    :rtype: DecisionRecord
    """
    if connexion.request.is_json:
        decision_type = DecisionType.from_dict(connexion.request.get_json())  # noqa: E501
    if connexion.request.is_json:
        plugin_type = PluginType.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_session_session_id_timed_decision_get(session_id, area_id=None, decision_type=None, timeout=None, plugin_type=None):  # noqa: E501
    """Get the most recent decision that is available for the given area.

    Sample request:        ../Session/{sessionId}/TimedDecision?areaId&#x3D;12&amp;timeout&#x3D;120&amp;decisionType&#x3D;include                Sample response:                     {       \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,       \&quot;areaId\&quot;: 12,       \&quot;decisionType\&quot;: \&quot;FoilHoleSelection\&quot;,       \&quot;decisionValue\&quot;: \&quot;[        {         \&quot;areaId\&quot;: 100,         \&quot;result\&quot;: \&quot;true\&quot;        },        {         \&quot;areaId\&quot;: 101,         \&quot;result\&quot;: \&quot;false\&quot;        },        {         \&quot;areaId\&quot;: 102,         \&quot;result\&quot;: \&quot;true\&quot;        }       ]\&quot;,       \&quot;decidedBy\&quot;: \&quot;FoilHoleSelection algorithm\&quot;,       \&quot;details\&quot;: \&quot;bad foilhole\&quot;      } # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_id: Uniquely identifies the area within the application session.
    :type area_id: int
    :param decision_type: The type of decision.
    :type decision_type: dict | bytes
    :param timeout: Timeout window in seconds within which a relevant decision shall be found. If timeout is reached 204 NoContent will be sent.
    :type timeout: int
    :param plugin_type: The plugin was used in taking the decision.
    :type plugin_type: dict | bytes

    :rtype: DecisionRecord
    """
    if connexion.request.is_json:
        decision_type = DecisionType.from_dict(connexion.request.get_json())  # noqa: E501
    if connexion.request.is_json:
        plugin_type = PluginType.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
