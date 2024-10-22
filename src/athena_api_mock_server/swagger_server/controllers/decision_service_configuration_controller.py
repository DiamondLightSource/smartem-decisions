import connexion
import six

from swagger_server.models.decision_service_configuration import DecisionServiceConfiguration  # noqa: E501
from swagger_server.models.problem_details import ProblemDetails  # noqa: E501
from swagger_server.models.smart_plugin_configuration import SmartPluginConfiguration  # noqa: E501
from swagger_server import util


def api_v1_configuration_delete():  # noqa: E501
    """Delete a registered decision service configuration.

     # noqa: E501


    :rtype: None
    """
    return 'do some magic!'


def api_v1_configuration_get():  # noqa: E501
    """Get decision service configuration.

    Sample request:        ../Configuration # noqa: E501


    :rtype: DecisionServiceConfiguration
    """
    return 'do some magic!'


def api_v1_configuration_plugin_patch(body=None):  # noqa: E501
    """Patch the existing smart plugin configuration

    Sample request:        PATCH      {                \&quot;PluginName\&quot;: \&quot;StageSettlingTimePrediction\&quot;,        \&quot;CustomPluginSelection\&quot;: true      }    Sample response:        RESPONSE      {                \&quot;PluginName\&quot;: \&quot;StageSettlingTimePrediction\&quot;,        \&quot;CustomPluginSelection\&quot;: true,        \&quot;Timestamp\&quot; : \&quot;10/20/2022 14:38\&quot;      } # noqa: E501

    :param body: Smart plugin configuration.
    :type body: dict | bytes

    :rtype: SmartPluginConfiguration
    """
    if connexion.request.is_json:
        body = SmartPluginConfiguration.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_configuration_post(body=None):  # noqa: E501
    """Post new decision service configuration.

    Sample requests:                    POST      {          \&quot;SmartPluginConfigurations\&quot; : [              {                  \&quot;PluginName\&quot;: \&quot;StageSettlingTimePrediction\&quot;,                  \&quot;CustomPluginSelection\&quot;: true              },              {                  \&quot;PluginName\&quot;: \&quot;SkipGridSquarePrediction\&quot;,                  \&quot;CustomPluginSelection\&quot;: false              },              {                  \&quot;PluginName\&quot;: \&quot;SmartFocusPrediction\&quot;,                  \&quot;CustomPluginSelection\&quot;: true              },              {                  \&quot;PluginName\&quot;: \&quot;AutomaticFoilHoleSelection\&quot;,                  \&quot;CustomPluginSelection\&quot;: false              },              {                  \&quot;PluginName\&quot;: \&quot;AutomaticGridSquareSelection\&quot;,                  \&quot;CustomPluginSelection\&quot;: false              },              {                  \&quot;PluginName\&quot;: \&quot;IceThicknessFoilHolePrediction\&quot;,                  \&quot;CustomPluginSelection\&quot;: false              },              {                  \&quot;PluginName\&quot;: \&quot;AutomaticFoilHoleFinding\&quot;,                  \&quot;CustomPluginSelection\&quot;: true              }          ]      } # noqa: E501

    :param body: Decision service configuration.
    :type body: dict | bytes

    :rtype: DecisionServiceConfiguration
    """
    if connexion.request.is_json:
        body = DecisionServiceConfiguration.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
