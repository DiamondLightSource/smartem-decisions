import connexion
import six

from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.models.run import Run  # noqa: E501
from swagger_server.models.run_start import RunStart  # noqa: E501
from swagger_server.models.run_stop import RunStop  # noqa: E501
from swagger_server import util


def api_v1_run_start_post(body=None):  # noqa: E501
    """Notify that an application run has started.

    Sample request:        POST      {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;      } # noqa: E501

    :param body: The information about the application session for which the run starts.
    :type body: dict | bytes

    :rtype: Run
    """
    if connexion.request.is_json:
        body = RunStart.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_run_stop_patch(body=None):  # noqa: E501
    """Notify that an application run has stopped.

    Sample request:        POST      {                \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,        \&quot;runNumber\&quot;: 1,        \&quot;reason\&quot;: \&quot;acquisition completed\&quot;      } # noqa: E501

    :param body: The information about the application session for which the run stopped.
    :type body: dict | bytes

    :rtype: Run
    """
    if connexion.request.is_json:
        body = RunStop.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_session_session_id_run_run_number_get(session_id, run_number):  # noqa: E501
    """Get an application run.

    Note that application Runs cannot be created directly on the API, but are created via the notification services.    Sample request:        ../Session/{sessionId}/Run/{runNumber} # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param run_number: The application acquisition run number.
    :type run_number: int

    :rtype: Run
    """
    return 'do some magic!'


def api_v1_session_session_id_runs_get(session_id):  # noqa: E501
    """Get all application runs.

    Sample request:        ../Session/{sessionId}/Runs # noqa: E501

    :param session_id: The id that uniquely identifies the application session.
    :type session_id: 

    :rtype: List[Run]
    """
    return 'do some magic!'
