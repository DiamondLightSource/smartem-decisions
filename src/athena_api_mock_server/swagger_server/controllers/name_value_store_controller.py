import connexion
import six

from swagger_server.models.name_value_record import NameValueRecord  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server import util


def api_v1_name_value_store_post(body=None):  # noqa: E501
    """Creates a new name-value record.

    Sample request:        POST      {                  \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,          \&quot;areaId\&quot;: 1,          \&quot;name\&quot;: \&quot;metadata\&quot;,          \&quot;value\&quot;: \&quot;value\&quot;,          \&quot;timestamp\&quot;: \&quot;2021-02-26T12:45:18.076Z\&quot;,          \&quot;setBy\&quot;: \&quot;Swagger\&quot;      } # noqa: E501

    :param body: The record to be inserted.
    :type body: dict | bytes

    :rtype: NameValueRecord
    """
    if connexion.request.is_json:
        body = NameValueRecord.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_name_value_store_session_id_value_id_get(session_id, id):  # noqa: E501
    """Get name-value record with provided id.

    Sample request:        ../NameValueStore/{sessionId}/Value/{id} # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param id: Name-value record id.
    :type id: int

    :rtype: NameValueRecord
    """
    return 'do some magic!'


def api_v1_name_value_store_session_id_values_get(session_id, area_id=None, name=None):  # noqa: E501
    """Get all name-value records for the given application session, optionally filtered by area type or/and name.

    Sample request:        ../NameValueStore/{sessionId}/Values?areaId&#x3D;3      ../NameValueStore/{sessionId}/Values?name&#x3D;CoordinatesInParent # noqa: E501

    :param session_id: Uniquely identifies the application session.
    :type session_id: 
    :param area_id: Uniquely identifies the area within the session.
    :type area_id: int
    :param name: The name given to the record.
    :type name: str

    :rtype: List[NameValueRecord]
    """
    return 'do some magic!'


def api_v1_name_value_stores_post(body=None):  # noqa: E501
    """Register multiple name-value records.

    Sample request:        POST      [          {              \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,              \&quot;areaId\&quot;: 1,              \&quot;name\&quot;: \&quot;name1\&quot;,              \&quot;value\&quot;: \&quot;value1\&quot;,              \&quot;setBy\&quot;: \&quot;Swagger\&quot;          },          {              \&quot;sessionId\&quot;: \&quot;3fa85f64-5717-4562-b3fc-2c963f66afa6\&quot;,               \&quot;areaId\&quot;: 1,              \&quot;name\&quot;: \&quot;name2\&quot;,              \&quot;value\&quot;: \&quot;value2\&quot;,              \&quot;setBy\&quot;: \&quot;Swagger\&quot;          }      ] # noqa: E501

    :param body: The name-value records to be registered.
    :type body: list | bytes

    :rtype: List[NameValueRecord]
    """
    if connexion.request.is_json:
        body = [NameValueRecord.from_dict(d) for d in connexion.request.get_json()]  # noqa: E501
    return 'do some magic!'
