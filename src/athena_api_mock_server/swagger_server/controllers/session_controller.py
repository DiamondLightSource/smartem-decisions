import connexion
import six

from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.models.session import Session  # noqa: E501
from swagger_server import util


def api_v1_session_get(session_name=None):  # noqa: E501
    """Get a session filtered by session name.

    Sample request:        ../Sessions?sessionName&#x3D;mySession # noqa: E501

    :param session_name: The application session name.
    :type session_name: str

    :rtype: Session
    """
    return 'do some magic!'


def api_v1_session_id_delete(id):  # noqa: E501
    """Delete a registered application Session from the decision store.

     # noqa: E501

    :param id: The application session id.
    :type id: 

    :rtype: Session
    """
    return 'do some magic!'


def api_v1_session_id_get(id):  # noqa: E501
    """Get an application session.

    Sample request:        ../Session/{id} # noqa: E501

    :param id: The application session id.
    :type id: 

    :rtype: Session
    """
    return 'do some magic!'


def api_v1_session_id_is_registered_get(id):  # noqa: E501
    """Check if a session with given id has been registered.

     # noqa: E501

    :param id: The application session id.
    :type id: 

    :rtype: bool
    """
    return 'do some magic!'


def api_v1_session_post(body=None):  # noqa: E501
    """Register an application session.

    Sample request:        POST      {                \&quot;sessionName\&quot;: \&quot;My Session\&quot;                \&quot;sessionId\&quot; : \&quot;b5cdbfb9-bd0f-414e-93f8-0abca3331f8e\&quot;      }        or, to auto-generate a session id            POST      {                \&quot;sessionName\&quot;: \&quot;My Session\&quot;              } # noqa: E501

    :param body: The application Session to register; sessionName is mandatory. If sessionId is not specified, it&#x27;s auto-generated.
    :type body: dict | bytes

    :rtype: Session
    """
    if connexion.request.is_json:
        body = Session.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_sessions_get():  # noqa: E501
    """Get all registered sessions.

    Sample request:        ../Sessions # noqa: E501


    :rtype: List[Session]
    """
    return 'do some magic!'
