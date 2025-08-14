"""Athena API client for decision service integration."""

import json
import logging
import traceback
from datetime import datetime
from typing import Any
from uuid import UUID

import requests
from pydantic import BaseModel

from athena_api.model.request import (
    AlgorithmResultType,
    ApplicationStateChange,
    Area,
    AreaStateChange,
    DecisionRecord,
    DecisionServiceConfiguration,
    NameValueRecord,
    RunStart,
    RunStop,
    Session,
)
from athena_api.model.response import (
    AlgorithmResultRecord,
    ApplicationState,
    AreaState,
    Run,
)


class AthenaClient:
    """
    Athena API client for decision service interactions.

    This client provides synchronous HTTP interface for interacting with
    the Athena Decision Service API, handling sessions, areas, algorithm results,
    and decision management.
    """

    def __init__(self, base_url: str, timeout: float = 10.0, logger=None):
        """
        Initialize the Athena API client.

        Args:
            base_url: Base URL for the API
            timeout: Request timeout in seconds
            logger: Optional custom logger instance
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.timeout = timeout
        self._logger = logger or logging.getLogger(__name__)

        # Configure logger if it's the default one
        if not logger:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

        self._logger.info(f"Initialized Athena API client with base URL: {base_url}")

    def close(self) -> None:
        """Close the client connection."""
        try:
            self._session.close()
        except Exception as e:
            self._logger.error(f"Error closing session: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _request(
        self,
        method: str,
        endpoint: str,
        request_model: BaseModel | None = None,
        response_cls=None,
    ):
        """
        Make a generic API request.

        Args:
            method: HTTP method (get, post, put, delete)
            endpoint: API endpoint path
            request_model: Optional request data model
            response_cls: Optional response class to parse the response

        Returns:
            Parsed response, list of responses, or None for delete operations

        Raises:
            requests.HTTPError: If the HTTP request returns an error status code
            requests.RequestException: If there's a network error or timeout
            ValueError: If there's an error parsing the response
            Exception: For any other errors
        """
        url = f"{self.base_url}/{endpoint}"
        json_data = None

        if request_model:
            if hasattr(request_model, "model_dump"):
                # It's a Pydantic model
                json_data = request_model.model_dump(mode="json", exclude_none=True)
            else:
                # It's already a dict, but might contain datetime objects
                json_data = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in request_model.items()}
            self._logger.debug(f"Request data for {method} {url}: {json_data}")

        try:
            self._logger.debug(f"Making {method.upper()} request to {url}")
            response = self._session.request(method, url, json=json_data)
            response.raise_for_status()

            # For delete operations, return None
            if method.lower() == "delete":
                self._logger.info(f"Successfully deleted resource at {url}")
                return None

            try:
                data = response.json()
                self._logger.debug(f"Response from {url}: {data}")

                # Parse response if response_cls is provided
                if response_cls:
                    try:
                        if isinstance(data, list):
                            return [response_cls.model_validate(item) for item in data]
                        else:
                            return response_cls.model_validate(data)
                    except Exception as e:
                        self._logger.error(f"Error validating response data from {url}: {e}")
                        self._logger.debug(f"Response data that failed validation: {data}")
                        raise ValueError(f"Invalid response data: {str(e)}") from None

                return data
            except json.JSONDecodeError as e:
                self._logger.error(f"Could not parse JSON response from {url}: {e}")
                self._logger.debug(f"Raw response: {response.text}")
                raise ValueError(f"Invalid JSON response: {str(e)}") from None

        except requests.HTTPError as e:
            status_code = e.response.status_code
            error_detail = None

            # Try to extract error details from the response
            try:
                error_response = e.response.json()
                error_detail = error_response.get("detail", str(e))
            except Exception:
                error_detail = e.response.text or str(e)

            self._logger.error(f"HTTP {status_code} error for {method.upper()} {url}: {error_detail}")
            raise

        except requests.RequestException as e:
            self._logger.error(f"Request error for {method.upper()} {url}: {e}")
            self._logger.debug(f"Request error details: {traceback.format_exc()}")
            raise

        except Exception as e:
            self._logger.error(f"Unexpected error making request to {url}: {e}")
            self._logger.debug(f"Error details: {traceback.format_exc()}")
            raise

    # Algorithm Result endpoints
    def get_algorithm_result(
        self, session_id: UUID, area_id: int | None = None, name: AlgorithmResultType | None = None
    ) -> AlgorithmResultRecord:
        """Get algorithm result using session id, name and area id."""
        params = {}
        if area_id is not None:
            params["areaId"] = area_id
        if name is not None:
            params["name"] = name.value

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"api/v1/Session/{session_id}/AlgorithmResult"
        if query_string:
            endpoint += f"?{query_string}"

        return self._request("get", endpoint, response_cls=AlgorithmResultRecord)

    def get_algorithm_results(
        self, session_id: UUID, parent_area_id: int | None = None, name: AlgorithmResultType | None = None
    ) -> list[AlgorithmResultRecord]:
        """Get all algorithm results using session id, name and parent area id."""
        params = {}
        if parent_area_id is not None:
            params["parentAreaId"] = parent_area_id
        if name is not None:
            params["name"] = name.value

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"api/v1/Session/{session_id}/AlgorithmResults"
        if query_string:
            endpoint += f"?{query_string}"

        return self._request("get", endpoint, response_cls=AlgorithmResultRecord)

    def get_latest_algorithm_result(
        self, session_id: UUID, parent_area_id: int | None = None, name: AlgorithmResultType | None = None
    ) -> AlgorithmResultRecord:
        """Get latest algorithm result using session id, name and parent area id."""
        params = {}
        if parent_area_id is not None:
            params["parentAreaId"] = parent_area_id
        if name is not None:
            params["name"] = name.value

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"api/v1/Session/{session_id}/LatestAlgorithmResult"
        if query_string:
            endpoint += f"?{query_string}"

        return self._request("get", endpoint, response_cls=AlgorithmResultRecord)

    # Application State endpoints
    def get_current_application_state(self) -> ApplicationState:
        """Get the current (or last known) state of the application."""
        return self._request("get", "api/v1/CurrentApplicationState", response_cls=ApplicationState)

    def update_application_state(self, state_change: ApplicationStateChange) -> ApplicationState:
        """Notify the current application state."""
        return self._request("post", "api/v1/CurrentApplicationState", state_change, ApplicationState)

    def get_session_application_states(self, session_id: UUID) -> list[ApplicationState]:
        """Get all the tracked application states for the given application session."""
        return self._request("get", f"api/v1/Session/{session_id}/ApplicationStates", response_cls=ApplicationState)

    # Area endpoints
    def get_area(self, session_id: UUID, area_id: int) -> Area:
        """Get the registered area for application session."""
        return self._request("get", f"api/v1/Session/{session_id}/Area/{area_id}", response_cls=Area)

    def get_areas(
        self, session_id: UUID, area_type: str | None = None, parent_area_id: int | None = None
    ) -> list[Area]:
        """Get all the registered areas for application session, optionally filtered by area type or parent."""
        params = {}
        if area_type is not None:
            params["areaType"] = area_type
        if parent_area_id is not None:
            params["parentAreaId"] = parent_area_id

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"api/v1/Session/{session_id}/Areas"
        if query_string:
            endpoint += f"?{query_string}"

        return self._request("get", endpoint, response_cls=Area)

    def get_child_areas(self, session_id: UUID, parent_area_id: int) -> list[Area]:
        """Get all the registered child areas of the given area."""
        return self._request("get", f"api/v1/Session/{session_id}/Area/{parent_area_id}/Areas", response_cls=Area)

    def register_area(self, area: Area) -> Area:
        """Register an area."""
        return self._request("post", "api/v1/Area", area, Area)

    def update_area(self, area: Area) -> list[Area]:
        """Update a registered area."""
        return self._request("put", "api/v1/Area", area, Area)

    # Area State endpoints
    def get_area_state(self, session_id: UUID, area_id: int) -> AreaState:
        """Get the state of the area."""
        return self._request("get", f"api/v1/Session/{session_id}/Area/{area_id}/State", response_cls=AreaState)

    def get_area_states(self, session_id: UUID, parent_area_id: int | None = None) -> list[AreaState]:
        """Get the states of areas."""
        params = {}
        if parent_area_id is not None:
            params["parentAreaId"] = parent_area_id

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"api/v1/Session/{session_id}/AreaStates"
        if query_string:
            endpoint += f"?{query_string}"

        return self._request("get", endpoint, response_cls=AreaState)

    def update_area_state(self, area_state_change: AreaStateChange) -> AreaState:
        """Update the state of the area."""
        return self._request("post", "api/v1/AreaState", area_state_change, AreaState)

    # Decision endpoints
    def get_decisions(
        self, session_id: UUID, area_id: int | None = None, decision_type: str | None = None
    ) -> list[DecisionRecord]:
        """Get decisions."""
        params = {}
        if area_id is not None:
            params["areaId"] = area_id
        if decision_type is not None:
            params["decisionType"] = decision_type

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"api/v1/Session/{session_id}/Decisions"
        if query_string:
            endpoint += f"?{query_string}"

        return self._request("get", endpoint, response_cls=DecisionRecord)

    def record_decision(self, decision: DecisionRecord) -> DecisionRecord:
        """Record a decision."""
        return self._request("post", "api/v1/Decision", decision, DecisionRecord)

    # Session endpoints
    def register_session(self, session: Session) -> Session:
        """Register a session."""
        return self._request("post", "api/v1/Session", session, Session)

    def get_session(self, session_id: UUID) -> Session:
        """Get a session."""
        return self._request("get", f"api/v1/Session/{session_id}", response_cls=Session)

    # Run endpoints
    def start_run(self, run_start: RunStart) -> Run:
        """Start a run."""
        return self._request("post", "api/v1/Run/Start", run_start, Run)

    def stop_run(self, run_stop: RunStop) -> Run:
        """Stop a run."""
        return self._request("post", "api/v1/Run/Stop", run_stop, Run)

    def get_runs(self, session_id: UUID) -> list[Run]:
        """Get all runs for a session."""
        return self._request("get", f"api/v1/Session/{session_id}/Runs", response_cls=Run)

    # Configuration endpoints
    def get_configuration(self) -> DecisionServiceConfiguration:
        """Get the decision service configuration."""
        return self._request("get", "api/v1/Configuration", response_cls=DecisionServiceConfiguration)

    def update_configuration(self, config: DecisionServiceConfiguration) -> DecisionServiceConfiguration:
        """Update the decision service configuration."""
        return self._request("post", "api/v1/Configuration", config, DecisionServiceConfiguration)

    # Name-Value Store endpoints
    def get_name_value(
        self, session_id: UUID, area_id: int | None = None, name: str | None = None
    ) -> list[NameValueRecord]:
        """Get name-value pairs."""
        params = {}
        if area_id is not None:
            params["areaId"] = area_id
        if name is not None:
            params["name"] = name

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"api/v1/Session/{session_id}/NameValue"
        if query_string:
            endpoint += f"?{query_string}"

        return self._request("get", endpoint, response_cls=NameValueRecord)

    def set_name_value(self, name_value: NameValueRecord) -> NameValueRecord:
        """Set a name-value pair."""
        return self._request("post", "api/v1/NameValue", name_value, NameValueRecord)

    # Utility endpoints
    def get_version(self) -> dict[str, Any]:
        """Get version information."""
        return self._request("get", "api/v1/Utils/Version")
