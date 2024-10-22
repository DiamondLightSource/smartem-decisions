import connexion
import six

from swagger_server.models.application_state import ApplicationState  # noqa: E501
from swagger_server.models.application_state_change import ApplicationStateChange  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server import util


def api_v1_current_application_state_get():  # noqa: E501
    """Get the current (or last known) state of the application.

    Sample request:                    ../CurrentApplicationState # noqa: E501


    :rtype: ApplicationState
    """
    return 'do some magic!'


def api_v1_current_application_state_post(body=None):  # noqa: E501
    """Notify the current application state.

    Sample requests:                    POST      {              \&quot;state\&quot;: \&quot;idle\&quot;,        \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;      }        or        POST      {         \&quot;state\&quot;: \&quot;running\&quot;,        \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,        \&quot;areaId\&quot; : 1213,        \&quot;details\&quot; : \&quot;running autofocus\&quot;      } # noqa: E501

    :param body: The new state of the application.
    :type body: dict | bytes

    :rtype: ApplicationState
    """
    if connexion.request.is_json:
        body = ApplicationStateChange.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_session_session_id_application_states_get(session_id):  # noqa: E501
    """Get all the tracked application states for the given application session.

    Sample request:        ../Session/{sessionId}/ApplicationStates # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 

    :rtype: List[ApplicationState]
    """
    return 'do some magic!'
