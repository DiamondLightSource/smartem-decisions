"""Athena API mock server for testing and development."""

from datetime import datetime
from uuid import UUID, uuid4

try:
    from fastapi import FastAPI, HTTPException, Query
except ImportError as e:
    raise ImportError(
        "Mock server dependencies not installed. Install with: pip install 'smartem-decisions[mock]'"
    ) from e

from athena_api.model.request import (
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


class AthenaAPIServer:
    """Mock Athena API server for testing and development."""

    def __init__(self):
        """Initialize the mock server."""
        self.app = FastAPI(
            title="Athena Decision Service API (Mock)",
            version="v1",
            description="Mock server for Athena Decision Service API",
        )

        # In-memory storage
        self._sessions: dict[UUID, Session] = {}
        self._areas: dict[int, Area] = {}
        self._area_states: dict[int, AreaState] = {}
        self._application_states: list[ApplicationState] = []
        self._algorithm_results: list[AlgorithmResultRecord] = []
        self._decisions: list[DecisionRecord] = []
        self._runs: dict[UUID, list[Run]] = {}
        self._name_values: list[NameValueRecord] = []
        self._current_app_state: ApplicationState | None = None
        self._configuration: DecisionServiceConfiguration | None = None

        self._setup_routes()

    def _setup_routes(self):
        """Set up all API routes."""

        # Algorithm Result endpoints
        @self.app.get("/api/v1/Session/{session_id}/AlgorithmResult")
        async def get_algorithm_result(
            session_id: UUID, areaId: int | None = Query(None), name: str | None = Query(None)
        ):
            """Get algorithm result using session id, name and area id."""
            results = [
                r
                for r in self._algorithm_results
                if r.sessionId == session_id
                and (areaId is None or r.areaId == areaId)
                and (name is None or r.name == name)
            ]

            if not results:
                raise HTTPException(status_code=404, detail="Algorithm result not found")
            return results[0]

        @self.app.get("/api/v1/Session/{session_id}/AlgorithmResults")
        async def get_algorithm_results(
            session_id: UUID, parentAreaId: int | None = Query(None), name: str | None = Query(None)
        ):
            """Get all algorithm results using session id, name and parent area id."""
            results = [
                r for r in self._algorithm_results if r.sessionId == session_id and (name is None or r.name == name)
            ]
            return results

        @self.app.get("/api/v1/Session/{session_id}/LatestAlgorithmResult")
        async def get_latest_algorithm_result(
            session_id: UUID, parentAreaId: int | None = Query(None), name: str | None = Query(None)
        ):
            """Get latest algorithm result using session id, name and parent area id."""
            results = [
                r for r in self._algorithm_results if r.sessionId == session_id and (name is None or r.name == name)
            ]

            if not results:
                raise HTTPException(status_code=204, detail="No latest record found")
            return max(results, key=lambda x: x.timestamp)

        # Application State endpoints
        @self.app.get("/api/v1/CurrentApplicationState")
        async def get_current_application_state():
            """Get the current (or last known) state of the application."""
            if not self._current_app_state:
                # Return a default state
                from athena_api.model.request import EngineState

                self._current_app_state = ApplicationState(id=uuid4(), state=EngineState.IDLE, timestamp=datetime.now())
            return self._current_app_state

        @self.app.post("/api/v1/CurrentApplicationState")
        async def update_application_state(state_change: ApplicationStateChange):
            """Notify the current application state."""
            new_state = ApplicationState(
                id=uuid4(),
                state=state_change.state,
                sessionId=state_change.sessionId,
                areaId=state_change.areaId,
                details=state_change.details,
                timestamp=datetime.now(),
            )
            self._current_app_state = new_state
            self._application_states.append(new_state)
            return new_state

        @self.app.get("/api/v1/Session/{session_id}/ApplicationStates")
        async def get_session_application_states(session_id: UUID):
            """Get all the tracked application states for the given application session."""
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            states = [s for s in self._application_states if s.sessionId == session_id]
            return states

        # Area endpoints
        @self.app.get("/api/v1/Session/{session_id}/Area/{area_id}")
        async def get_area(session_id: UUID, area_id: int):
            """Get the registered area for application session."""
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            if area_id not in self._areas:
                raise HTTPException(status_code=404, detail="Area not found")
            return self._areas[area_id]

        @self.app.get("/api/v1/Session/{session_id}/Areas")
        async def get_areas(
            session_id: UUID, areaType: str | None = Query(None), parentAreaId: int | None = Query(None)
        ):
            """Get all the registered areas for application session."""
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            areas = [
                a
                for a in self._areas.values()
                if a.sessionId == session_id
                and (areaType is None or a.areaType == areaType)
                and (parentAreaId is None or a.parentId == parentAreaId)
            ]
            return areas

        @self.app.get("/api/v1/Session/{session_id}/Area/{parent_area_id}/Areas")
        async def get_child_areas(session_id: UUID, parent_area_id: int):
            """Get all the registered child areas of the given area."""
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            areas = [a for a in self._areas.values() if a.sessionId == session_id and a.parentId == parent_area_id]
            return areas

        @self.app.post("/api/v1/Area")
        async def register_area(area: Area):
            """Register an area."""
            if area.sessionId not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            if area.id in self._areas:
                raise HTTPException(status_code=409, detail="Area already registered")

            self._areas[area.id] = area
            return area

        @self.app.put("/api/v1/Area")
        async def update_area(area: Area):
            """Update a registered area."""
            if area.sessionId not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            self._areas[area.id] = area
            return [area]

        # Area State endpoints
        @self.app.get("/api/v1/Session/{session_id}/Area/{area_id}/State")
        async def get_area_state(session_id: UUID, area_id: int):
            """Get the state of the area."""
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            if area_id not in self._area_states:
                raise HTTPException(status_code=404, detail="Area state not found")
            return self._area_states[area_id]

        @self.app.get("/api/v1/Session/{session_id}/AreaStates")
        async def get_area_states(session_id: UUID, parentAreaId: int | None = Query(None)):
            """Get the states of areas."""
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            states = [s for s in self._area_states.values() if s.sessionId == session_id]
            return states

        @self.app.post("/api/v1/AreaState")
        async def update_area_state(area_state_change: AreaStateChange):
            """Update the state of the area."""
            area_state = AreaState(
                id=len(self._area_states) + 1,
                sessionId=area_state_change.sessionId,
                areaId=area_state_change.areaId,
                state=area_state_change.state,
                timestamp=datetime.now(),
            )
            self._area_states[area_state_change.areaId] = area_state
            return area_state

        # Session endpoints
        @self.app.post("/api/v1/Session")
        async def register_session(session: Session):
            """Register a session."""
            if session.sessionId in self._sessions:
                raise HTTPException(status_code=409, detail="Session already exists")

            self._sessions[session.sessionId] = session
            return session

        @self.app.get("/api/v1/Session/{session_id}")
        async def get_session(session_id: UUID):
            """Get a session."""
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            return self._sessions[session_id]

        # Run endpoints
        @self.app.post("/api/v1/Run/Start")
        async def start_run(run_start: RunStart):
            """Start a run."""
            if run_start.sessionId not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            if run_start.sessionId not in self._runs:
                self._runs[run_start.sessionId] = []

            run_number = len(self._runs[run_start.sessionId]) + 1
            run = Run(sessionId=run_start.sessionId, runNumber=run_number, startTime=datetime.now())
            self._runs[run_start.sessionId].append(run)
            return run

        @self.app.post("/api/v1/Run/Stop")
        async def stop_run(run_stop: RunStop):
            """Stop a run."""
            if run_stop.sessionId not in self._runs:
                raise HTTPException(status_code=404, detail="No runs found for session")

            runs = self._runs[run_stop.sessionId]
            target_run = next((r for r in runs if r.runNumber == run_stop.runNumber), None)

            if not target_run:
                raise HTTPException(status_code=404, detail="Run not found")

            target_run.stopTime = datetime.now()
            target_run.stopReason = run_stop.reason
            return target_run

        @self.app.get("/api/v1/Session/{session_id}/Runs")
        async def get_runs(session_id: UUID):
            """Get all runs for a session."""
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            return self._runs.get(session_id, [])

        # Configuration endpoints
        @self.app.get("/api/v1/Configuration")
        async def get_configuration():
            """Get the decision service configuration."""
            if not self._configuration:
                self._configuration = DecisionServiceConfiguration(id=uuid4(), timestamp=datetime.now())
            return self._configuration

        @self.app.post("/api/v1/Configuration")
        async def update_configuration(config: DecisionServiceConfiguration):
            """Update the decision service configuration."""
            self._configuration = config
            return config

        # Name-Value Store endpoints
        @self.app.get("/api/v1/Session/{session_id}/NameValue")
        async def get_name_value(session_id: UUID, areaId: int | None = Query(None), name: str | None = Query(None)):
            """Get name-value pairs."""
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            results = [
                nv
                for nv in self._name_values
                if nv.sessionId == session_id
                and (areaId is None or nv.areaId == areaId)
                and (name is None or nv.name == name)
            ]
            return results

        @self.app.post("/api/v1/NameValue")
        async def set_name_value(name_value: NameValueRecord):
            """Set a name-value pair."""
            # Remove existing record with same key if it exists
            self._name_values = [
                nv
                for nv in self._name_values
                if not (
                    nv.sessionId == name_value.sessionId
                    and nv.areaId == name_value.areaId
                    and nv.name == name_value.name
                )
            ]
            self._name_values.append(name_value)
            return name_value

        # Decision endpoints
        @self.app.get("/api/v1/Session/{session_id}/Decisions")
        async def get_decisions(
            session_id: UUID, areaId: int | None = Query(None), decisionType: str | None = Query(None)
        ):
            """Get decisions."""
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            results = [
                d
                for d in self._decisions
                if d.sessionId == session_id
                and (areaId is None or d.areaId == areaId)
                and (decisionType is None or d.decisionType == decisionType)
            ]
            return results

        @self.app.post("/api/v1/Decision")
        async def record_decision(decision: DecisionRecord):
            """Record a decision."""
            self._decisions.append(decision)
            return decision

        # Utility endpoints
        @self.app.get("/api/v1/Utils/Version")
        async def get_version():
            """Get version information."""
            return {"version": "1.0.0-mock", "build": "mock-build", "timestamp": datetime.now().isoformat()}

    def run(self, host: str = "127.0.0.1", port: int = 8000, **kwargs):
        """Run the mock server."""
        try:
            import uvicorn

            uvicorn.run(self.app, host=host, port=port, **kwargs)
        except ImportError as e:
            raise ImportError("uvicorn not installed. Install with: pip install 'smartem-decisions[mock]'") from e


if __name__ == "__main__":
    server = AthenaAPIServer()
    server.run()
