# TODO: set base_url at instantiation, pass through env.
from cryoem_client.api.application_state_api import ApplicationStateApi
from cryoem_client.api.version_api import VersionApi
from cryoem_client.api.area_api import AreaApi
from cryoem_client.api.run_api import RunApi
from cryoem_client.api.utils_api import UtilsApi
from cryoem_client.api.session_api import SessionApi
from cryoem_client.api.decision_api import DecisionApi
from cryoem_client.api.session_api import SessionApi
from cryoem_client.api.algorithm_result_api import AlgorithmResultApi
from cryoem_client.api.area_state_api import AreaStateApi
from cryoem_client.api.decision_service_configuration_api import DecisionServiceConfigurationApi
from cryoem_client.api.name_value_store_api import NameValueStoreApi

# response1 = ApplicationStateApi().api_v1_current_application_state_get()
# print(response1)
# response2 = VersionApi().api_v1_version_get()
# print(response2)

"""
Higher-level abstraction around the CryoEM API (Athena)
"""


class MicroscopeService:
    pass


"""
Note: We make use of the Zocalo
processing framework to organize parts of the workflow concerning
managing data transfer from microscope
and detector systems to a facility filesystem for processing.
"""

"""

"""


class Workflow:
    def __init__(self): pass

    """
    Example of running the complete workflow
    """

    def run(self):
        """
        Current way:
        1. User manually starts the process on the microscope side
           User manually starts the filesystem watcher
        2. User manually works through the workflow until they get to the micrograph (highest res) stage
        3. A fs watcher then picks up newly generated data on the file system,
           determines what these files are, rsyncs to our fs (GPFS in out on-site datacenter) and then
           sends a notification to Murfey API (https://github.com/DiamondLightSource/python-murfey).
        4. Failure handling: everything gets logged to our graylog instance, and payloads of failed requests get dumped to RabbitMQ
           so that it can be recovered later.

        New way:
        1. User manually starts the process on the microscope side
        2. A fs watcher kicks in as soon as the Atlas is scanned (can we start it automatically? Do we need to?)
        3.
        """
        self.atlas_scanned_notification_recipient()

    """
    Scan atlas and get grid squares
    TBC: from CryoEM client API or from filesystem? See `doc/metadata_spa_acquisition`

    @param Atlas and Grid Squares (metadata and 25 * ~4k images) 
    """

    def atlas_scanned_notification_recipient(self):
        # TODO call to init scanning here?
        self.filter_grid_squares()
        self.prioritise_grid_squares()

    """
    Grid Square Decision - filter out junk

    @param list of grid squares
    @return ordered list of grid squares, ranked; possibly a dismissal threshold OR choose a percentage to reject,
      or a combo of the two
    """

    def filter_and_rank_grid_squares(self): pass

    """
    Athena API instruction - provide Athena API with our new grid square scan priorities, after which
      the user needs to manually restart the flow on the microscope side. The user could intervene at this point
      and queue up the squares in the order that's been suggested, or dismiss the suggestion
      and proceed with default routine.

    @param output of `filter_and_rank_grid_squares`
    @return None?
    """

    def prioritise_grid_squares(self):  # TODO rename method
        # invoke Athena API
        pass

    """
    At this point currently user clicks on two adjacent Foil Holes on the Grid Square to generate a grid of Foil Holes
      across the grid square and detect the rest of the foil hole positions.
    """

    def detect_foil_holes(self):
        # Foil Hole detection step?
        # self.filter_foil_holes()
        # self.prioritise_foil_holes()
        pass

    """
    Foil Hole Decision - filter out junk
    """

    def filter_and_rank_foil_holes(self): pass

    """
    Foil Hole Decision - prioritise order of capture - and feed back `scan_atlas` and `detect_foil_holes`?
    """

    def prioritise_foil_holes(self): pass

    """
    Decision on how many shots per Foil Hole they want when dictating acquisition areas, this is specified by the user
    and is out of scope for automation because "it depends" and is subjective. Once do they will resume our flow.

    Acquisition areas picked for one Foil Hole are then applied to all Foil Holes
    (so acquisition areas are basically Foil Hole coverage).
    """

    """
    Motion and CTF (Contrast Transfer Function). Already happens on our side (via Murfey API -> Data Processing),
    takes about 15-20 sec.

    @param Multi-frame movie 
    @return Always a Micrograph from the multi-frame is returned, along with annotations describing:
      - various quality metrics for the micrograph (these can influence acquisition order on the FoilHole level immediately,
        and accumulate towards changing acquisition order at the Grid Square level).
    """

    def correct_motion_and_ctf(self): pass

    """
    Particle picking.
    At this point we know if our data is useful and we can feed back up the chain decisions such as:
        - avoiding similar foil holes
    Quality metrics can fuel decisions that can be fed back to both grid square decisions and foil hole decisions

    Note: check out https://cryolo.readthedocs.io/en/stable/ but there are a number of these floating around for
    automating particle picking.
    """

    def pick_particles(self):
        # An additional step here - particle acquisition? This step can take up to 10-15 mins?
        self.filter_particles()
        self.prioritise_particles()

    """
    Particle picking decision - filter out junk
    """

    def filter_particles(self): pass

    """
    Particle picking decision - prioritise order of capture
    """

    def prioritise_particles(self): pass


# TODO: Following are data types, challenge if they need to be classes
#   refs:
#   - https://docs.python.org/3/library/typing.html
#   - https://stackoverflow.com/questions/71168274/create-custom-data-type-in-python
class Atlas: pass


class GridSquare: pass


class FoilHole: pass


class AcquisitionArea: pass


class MicrographData: pass

# Processing Pipeline deals with micrograph data, and contains a parent-child relationship between a Foil Hole and a MicroGraph

