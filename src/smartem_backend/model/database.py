from datetime import datetime
from typing import Optional

from sqlalchemy import Column, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, Relationship, SQLModel
from sqlmodel import Session as SQLModelSession

from smartem_backend.model.entity_status import (
    AcquisitionStatusType,
    FoilHoleStatusType,
    GridSquareStatusType,
    GridStatusType,
    MicrographStatusType,
    ModelLevelType,
)
from smartem_backend.utils import logger, setup_postgres_connection
from smartem_common.entity_status import (
    AcquisitionStatus,
    FoilHoleStatus,
    GridSquareStatus,
    GridStatus,
    MicrographStatus,
    ModelLevel,
)


class Acquisition(SQLModel, table=True, table_name="acquisition"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    id: str | None = Field(default=None)
    name: str = Field(default="Unknown")
    status: AcquisitionStatus = Field(default=AcquisitionStatus.PLANNED, sa_column=Column(AcquisitionStatusType()))
    start_time: datetime | None = Field(default=None)
    end_time: datetime | None = Field(default=None)
    paused_time: datetime | None = Field(default=None)
    storage_path: str | None = Field(default=None)
    atlas_path: str | None = Field(default=None)
    clustering_mode: str | None = Field(default=None)
    clustering_radius: str | None = Field(default=None)
    instrument_model: str | None = Field(default=None)
    instrument_id: str | None = Field(default=None)
    computer_name: str | None = Field(default=None)
    grids: list["Grid"] = Relationship(sa_relationship_kwargs={"back_populates": "acquisition"}, cascade_delete=True)
    agent_sessions: list["AgentSession"] = Relationship(
        sa_relationship_kwargs={"back_populates": "acquisition"}, cascade_delete=True
    )


class Atlas(SQLModel, table=True, table_name="atlas"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    atlas_id: str = Field(default="")
    grid_uuid: str | None = Field(default=None, foreign_key="grid.uuid")
    acquisition_date: datetime | None = Field(default=None)
    storage_folder: str | None = Field(default=None)
    description: str | None = Field(default=None)
    name: str = Field(default="")
    grid: Optional["Grid"] = Relationship(sa_relationship_kwargs={"back_populates": "atlas"})
    atlastiles: list["AtlasTile"] = Relationship(
        sa_relationship_kwargs={"back_populates": "atlas"}, cascade_delete=True
    )


class Grid(SQLModel, table=True, table_name="grid"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    acquisition_uuid: str | None = Field(default=None, foreign_key="acquisition.uuid")
    status: GridStatus = Field(default=GridStatus.NONE, sa_column=Column(GridStatusType()))
    name: str
    data_dir: str | None = Field(default=None)
    atlas_dir: str | None = Field(default=None)
    scan_start_time: datetime | None = Field(default=None)
    scan_end_time: datetime | None = Field(default=None)
    prediction_updated_time: datetime = Field(default_factory=datetime.now)
    acquisition: Acquisition = Relationship(sa_relationship_kwargs={"back_populates": "grids"})
    gridsquares: list["GridSquare"] = Relationship(
        sa_relationship_kwargs={"back_populates": "grid"}, cascade_delete=True
    )
    atlas: Optional["Atlas"] = Relationship(sa_relationship_kwargs={"back_populates": "grid"})
    quality_model_parameters: list["QualityPredictionModelParameter"] = Relationship(
        back_populates="grid", cascade_delete=True
    )
    quality_model_weights: list["QualityPredictionModelWeight"] = Relationship(
        back_populates="grid", cascade_delete=True
    )
    current_quality_predictions: list["CurrentQualityPrediction"] = Relationship(
        back_populates="grid", cascade_delete=True
    )
    current_quality_model_weights: list["CurrentQualityPredictionModelWeight"] = Relationship(
        back_populates="grid", cascade_delete=True
    )
    current_metric_statistics: list["QualityMetricStatistics"] = Relationship(
        back_populates="grid", cascade_delete=True
    )
    overall_predictions: list["OverallQualityPrediction"] = Relationship(back_populates="grid", cascade_delete=True)


class AtlasTile(SQLModel, table=True, table_name="atlastile"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    atlas_uuid: str | None = Field(default=None, foreign_key="atlas.uuid")
    tile_id: str = Field(default="")
    position_x: int | None = Field(default=None)
    position_y: int | None = Field(default=None)
    size_x: int | None = Field(default=None)
    size_y: int | None = Field(default=None)
    file_format: str | None = Field(default=None)
    base_filename: str | None = Field(default=None)
    gridsquare_positions: list["AtlasTileGridSquarePosition"] = Relationship(
        sa_relationship_kwargs={"back_populates": "atlastile"}, cascade_delete=True
    )
    atlas: Optional["Atlas"] = Relationship(sa_relationship_kwargs={"back_populates": "atlastiles"})


class AtlasTileGridSquarePosition(SQLModel, table=True, table_name="atlastilegridsquareposition"):
    __table_args__ = {"extend_existing": True}
    atlastile_uuid: str = Field(primary_key=True, foreign_key="atlastile.uuid")
    gridsquare_uuid: str = Field(primary_key=True, foreign_key="gridsquare.uuid")
    center_x: int
    center_y: int
    size_width: int
    size_height: int
    atlastile: AtlasTile | None = Relationship(sa_relationship_kwargs={"back_populates": "gridsquare_positions"})
    gridsquare: Optional["GridSquare"] = Relationship(sa_relationship_kwargs={"back_populates": "atlastile_positions"})


class GridSquare(SQLModel, table=True, table_name="gridsquare"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    grid_uuid: str | None = Field(default=None, foreign_key="grid.uuid")
    status: GridSquareStatus = Field(default=GridSquareStatus.NONE, sa_column=Column(GridSquareStatusType()))
    gridsquare_id: str = Field(default="")
    data_dir: str | None = Field(default=None)
    atlas_node_id: int | None = Field(default=None)
    state: str | None = Field(default=None)
    rotation: float | None = Field(default=None)
    image_path: str | None = Field(default=None)
    selected: bool | None = Field(default=None)
    unusable: bool | None = Field(default=None)
    stage_position_x: float | None = Field(default=None)
    stage_position_y: float | None = Field(default=None)
    stage_position_z: float | None = Field(default=None)
    center_x: int | None = Field(default=None)
    center_y: int | None = Field(default=None)
    physical_x: float | None = Field(default=None)
    physical_y: float | None = Field(default=None)
    size_width: int | None = Field(default=None)
    size_height: int | None = Field(default=None)
    acquisition_datetime: datetime | None = Field(default=None)
    defocus: float | None = Field(default=None)
    magnification: float | None = Field(default=None)
    pixel_size: float | None = Field(default=None)
    detector_name: str | None = Field(default=None)
    applied_defocus: float | None = Field(default=None)
    grid: Grid = Relationship(sa_relationship_kwargs={"back_populates": "gridsquares"})
    atlastile_positions: list[AtlasTileGridSquarePosition] = Relationship(
        sa_relationship_kwargs={"back_populates": "gridsquare"}, cascade_delete=True
    )
    foilholes: list["FoilHole"] = Relationship(
        sa_relationship_kwargs={"back_populates": "gridsquare"}, cascade_delete=True
    )
    prediction: list["QualityPrediction"] = Relationship(back_populates="gridsquare", cascade_delete=True)
    current_prediction: list["CurrentQualityPrediction"] = Relationship(
        back_populates="gridsquare", cascade_delete=True
    )
    overall_prediction: list["OverallQualityPrediction"] = Relationship(
        back_populates="gridsquare", cascade_delete=True
    )


class FoilHole(SQLModel, table=True, table_name="foilhole"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    foilhole_id: str = Field(default="")  # Natural ID of the foilhole set at data source
    gridsquare_uuid: str | None = Field(default=None, foreign_key="gridsquare.uuid")
    gridsquare_id: str | None = Field(default=None)  # Natural parent ID set at data source
    status: FoilHoleStatus = Field(default=FoilHoleStatus.NONE, sa_column=Column(FoilHoleStatusType()))
    center_x: float | None = Field(default=None)
    center_y: float | None = Field(default=None)
    quality: float | None = Field(default=None)
    rotation: float | None = Field(default=None)
    size_width: float | None = Field(default=None)
    size_height: float | None = Field(default=None)
    x_location: int | None = Field(default=None)
    y_location: int | None = Field(default=None)
    x_stage_position: float | None = Field(default=None)
    y_stage_position: float | None = Field(default=None)
    diameter: int | None = Field(default=None)
    is_near_grid_bar: bool = Field(default=False)
    gridsquare: GridSquare = Relationship(sa_relationship_kwargs={"back_populates": "foilholes"})
    micrographs: list["Micrograph"] = Relationship(
        sa_relationship_kwargs={"back_populates": "foilhole"}, cascade_delete=True
    )
    prediction: list["QualityPrediction"] = Relationship(back_populates="foilhole", cascade_delete=True)
    current_prediction: list["CurrentQualityPrediction"] = Relationship(back_populates="foilhole", cascade_delete=True)
    overall_prediction: list["OverallQualityPrediction"] = Relationship(back_populates="foilhole", cascade_delete=True)


class Micrograph(SQLModel, table=True, table_name="micrograph"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    micrograph_id: str = Field(default="")
    foilhole_uuid: str | None = Field(default=None, foreign_key="foilhole.uuid")
    foilhole_id: str = Field(default="")
    location_id: str | None = Field(default=None)
    status: MicrographStatus = Field(default=MicrographStatus.NONE, sa_column=Column(MicrographStatusType()))
    high_res_path: str | None = Field(default=None)
    manifest_file: str | None = Field(default=None)
    acquisition_datetime: datetime | None = Field(default=None)
    defocus: float | None = Field(default=None)
    detector_name: str | None = Field(default=None)
    energy_filter: bool | None = Field(default=None)
    phase_plate: bool | None = Field(default=None)
    image_size_x: int | None = Field(default=None)
    image_size_y: int | None = Field(default=None)
    binning_x: int | None = Field(default=None)
    binning_y: int | None = Field(default=None)
    total_motion: float | None = Field(default=None)
    average_motion: float | None = Field(default=None)
    ctf_max_resolution_estimate: float | None = Field(default=None)
    number_of_particles_selected: int | None = Field(default=None)
    number_of_particles_rejected: int | None = Field(default=None)
    selection_distribution: str | None = Field(default=None)
    number_of_particles_picked: int | None = Field(default=None)
    pick_distribution: str | None = Field(default=None)
    foilhole: FoilHole = Relationship(sa_relationship_kwargs={"back_populates": "micrographs"})
    quality_model_weights: list["QualityPredictionModelWeight"] = Relationship(
        back_populates="micrograph", cascade_delete=True
    )


class QualityPredictionModel(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    name: str = Field(primary_key=True)
    description: str = ""
    level: ModelLevel = Field(default=ModelLevel.GRIDSQUARE, sa_column=Column(ModelLevelType))
    parameters: list["QualityPredictionModelParameter"] = Relationship(back_populates="model", cascade_delete=True)
    weights: list["QualityPredictionModelWeight"] = Relationship(back_populates="model", cascade_delete=True)
    predictions: list["QualityPrediction"] = Relationship(back_populates="model", cascade_delete=True)
    current_weights: list["CurrentQualityPredictionModelWeight"] = Relationship(
        back_populates="model", cascade_delete=True
    )
    current_predictions: list["CurrentQualityPrediction"] = Relationship(back_populates="model", cascade_delete=True)


class QualityMetric(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    name: str = Field(primary_key=True)
    description: str = ""
    parameters: list["QualityPredictionModelParameter"] = Relationship(back_populates="metric", cascade_delete=True)
    weights: list["QualityPredictionModelWeight"] = Relationship(back_populates="metric", cascade_delete=True)
    current_weights: list["CurrentQualityPredictionModelWeight"] = Relationship(
        back_populates="metric", cascade_delete=True
    )
    predictions: list["QualityPrediction"] = Relationship(back_populates="metric", cascade_delete=True)
    current_predictions: list["CurrentQualityPrediction"] = Relationship(back_populates="metric", cascade_delete=True)
    statistics: list["QualityMetricStatistics"] = Relationship(back_populates="metric", cascade_delete=True)


class QualityMetricStatistics(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    name: str = Field(foreign_key="qualitymetric.name", primary_key=True)
    grid_uuid: str = Field(foreign_key="grid.uuid", primary_key=True)
    count: int
    value_sum: float
    squared_value_sum: float
    metric: QualityMetric | None = Relationship(back_populates="statistics")
    grid: Grid | None = Relationship(back_populates="quality_metric_statistics")


class QualityPredictionModelParameter(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_uuid: str = Field(foreign_key="grid.uuid")
    timestamp: datetime = Field(default_factory=datetime.now)
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    key: str
    value: float
    group: str = ""
    metric_name: str | None = Field(foreign_key="qualitymetric.name", default=None)
    model: QualityPredictionModel | None = Relationship(back_populates="parameters")
    metric: QualityMetric | None = Relationship(back_populates="parameters")
    grid: Grid | None = Relationship(back_populates="quality_model_parameters")


class QualityPredictionModelWeight(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_uuid: str = Field(foreign_key="grid.uuid")
    micrograph_uuid: str | None = Field(default=None, foreign_key="micrograph.uuid")
    micrograph_quality: bool | None = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    metric_name: str | None = Field(foreign_key="qualitymetric.name", default=None)
    weight: float
    model: QualityPredictionModel | None = Relationship(back_populates="weights")
    metric: QualityMetric | None = Relationship(back_populates="weights")
    grid: Grid | None = Relationship(back_populates="quality_model_weights")
    micrograph: Micrograph | None = Relationship(back_populates="quality_model_weights")


class CurrentQualityPredictionModelWeight(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_uuid: str = Field(foreign_key="grid.uuid")
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    metric_name: str | None = Field(foreign_key="qualitymetric.name", default=None)
    weight: float
    model: QualityPredictionModel | None = Relationship(back_populates="current_weights")
    metric: QualityMetric | None = Relationship(back_populates="current_weights")
    grid: Grid | None = Relationship(back_populates="current_quality_model_weights")


class QualityPrediction(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now)
    value: float
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    metric_name: str | None = Field(foreign_key="qualitymetric.name", default=None)
    foilhole_uuid: str | None = Field(default=None, foreign_key="foilhole.uuid")
    gridsquare_uuid: str | None = Field(default=None, foreign_key="gridsquare.uuid")
    foilhole: FoilHole | None = Relationship(back_populates="prediction")
    gridsquare: GridSquare | None = Relationship(back_populates="prediction")
    model: QualityPredictionModel | None = Relationship(back_populates="predictions")
    metric: QualityMetric | None = Relationship(back_populates="predictions")


class CurrentQualityPrediction(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_uuid: str = Field(foreign_key="grid.uuid")
    value: float
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    metric_name: str | None = Field(foreign_key="qualitymetric.name", default=None)
    foilhole_uuid: str | None = Field(default=None, foreign_key="foilhole.uuid")
    gridsquare_uuid: str | None = Field(default=None, foreign_key="gridsquare.uuid")
    foilhole: FoilHole | None = Relationship(back_populates="prediction")
    gridsquare: GridSquare | None = Relationship(back_populates="prediction")
    model: QualityPredictionModel | None = Relationship(back_populates="predictions")
    metric: QualityMetric | None = Relationship(back_populates="current_predictions")
    grid: Grid | None = Relationship(back_populates="current_quality_predictions")


class OverallQualityPrediction(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    value: float
    foilhole_uuid: str = Field(foreign_key="foilhole.uuid")
    grid_uuid: str = Field(foreign_key="grid.uuid")
    gridsquare_uuid: str = Field(foreign_key="gridsquare.uuid")
    foilhole: FoilHole | None = Relationship(back_populates="overall_prediction")
    gridsquare: GridSquare | None = Relationship(back_populates="overall_prediction")
    grid: Grid | None = Relationship(back_populates="overall_predictions")


# ============ Agent Communication Tables ============


class AgentSession(SQLModel, table=True):
    """
    Represents a microscopy session conducted by an agent.
    Sessions group related instructions and provide experimental context.
    Backend-originated entity using BIGSERIAL primary key for scalability.
    """

    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(unique=True, index=True)  # Keep for backward compatibility and external references
    agent_id: str = Field(index=True)
    acquisition_uuid: str | None = Field(default=None, foreign_key="acquisition.uuid", index=True)
    name: str | None = Field(default=None)
    description: str | None = Field(default=None)
    experimental_parameters: dict | None = Field(default=None, sa_column=Column(JSONB))
    status: str = Field(default="active", index=True)
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    started_at: datetime | None = Field(default=None)
    ended_at: datetime | None = Field(default=None)
    last_activity_at: datetime = Field(default_factory=datetime.now, index=True)

    # Relationships
    acquisition: Optional["Acquisition"] = Relationship(sa_relationship_kwargs={"back_populates": "agent_sessions"})
    instructions: list["AgentInstruction"] = Relationship(
        sa_relationship_kwargs={"back_populates": "session"}, cascade_delete=True
    )
    connections: list["AgentConnection"] = Relationship(
        sa_relationship_kwargs={"back_populates": "session"}, cascade_delete=True
    )


class AgentInstruction(SQLModel, table=True):
    """
    Represents instructions sent to microscopy agents with full lifecycle tracking.
    Instructions contain the command payload and track delivery/acknowledgement status.
    Backend-originated entity using BIGSERIAL primary key for scalability.
    """

    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    instruction_id: str = Field(unique=True, index=True)  # Keep for backward compatibility and external references
    session_id: str = Field(foreign_key="agentsession.session_id", index=True)
    agent_id: str = Field(index=True)
    instruction_type: str = Field(index=True)
    payload: dict = Field(sa_column=Column(JSONB))
    sequence_number: int | None = Field(default=None, index=True)
    priority: str = Field(default="normal", index=True)
    status: str = Field(default="pending", index=True)
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    sent_at: datetime | None = Field(default=None, index=True)
    acknowledged_at: datetime | None = Field(default=None, index=True)
    expires_at: datetime | None = Field(default=None, index=True)
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    instruction_metadata: dict | None = Field(default=None, sa_column=Column(JSONB))

    # Relationships
    session: "AgentSession" = Relationship(sa_relationship_kwargs={"back_populates": "instructions"})
    acknowledgements: list["AgentInstructionAcknowledgement"] = Relationship(
        sa_relationship_kwargs={"back_populates": "instruction"}, cascade_delete=True
    )


class AgentConnection(SQLModel, table=True):
    """
    Tracks active SSE connections from agents.
    Used for connection health monitoring and cleanup.
    Backend-originated entity using BIGSERIAL primary key for scalability.
    """

    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    connection_id: str = Field(unique=True, index=True)  # Keep for backward compatibility and external references
    session_id: str = Field(foreign_key="agentsession.session_id", index=True)
    agent_id: str = Field(index=True)
    connection_type: str = Field(default="sse")
    client_info: dict | None = Field(default=None, sa_column=Column(JSONB))
    status: str = Field(default="active", index=True)
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    last_heartbeat_at: datetime = Field(default_factory=datetime.now, index=True)
    closed_at: datetime | None = Field(default=None)
    close_reason: str | None = Field(default=None)

    # Relationships
    session: "AgentSession" = Relationship(sa_relationship_kwargs={"back_populates": "connections"})


class AgentInstructionAcknowledgement(SQLModel, table=True):
    """
    Stores the history of instruction acknowledgements from agents.
    Provides audit trail for instruction processing and scientific reproducibility.
    Agent-originated entity using UUID primary key for distributed creation.
    """

    __table_args__ = {"extend_existing": True}
    acknowledgement_id: str = Field(
        sa_column=Column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    )
    instruction_id: str = Field(foreign_key="agentinstruction.instruction_id", index=True)
    agent_id: str = Field(index=True)
    session_id: str = Field(index=True)
    status: str = Field(index=True)  # received, processed, failed, declined
    result: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    processing_time_ms: int | None = Field(default=None)
    acknowledgement_metadata: dict | None = Field(default=None, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    processed_at: datetime | None = Field(default=None, index=True)

    # Relationships
    instruction: "AgentInstruction" = Relationship(sa_relationship_kwargs={"back_populates": "acknowledgements"})


def _create_db_and_tables(engine):
    # First drop all tables and enums
    with SQLModelSession(engine) as sess:
        teardown_query = text("""
            DO $$
            DECLARE
                drop_statement text;
            BEGIN
                FOR drop_statement IN
                    SELECT 'DROP TABLE IF EXISTS "' || table_name || '" CASCADE;'
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                LOOP
                    EXECUTE drop_statement;
                END LOOP;
                -- Drop the enum type if it exists
                DROP TYPE IF EXISTS acquisitionstatus CASCADE;
                DROP TYPE IF EXISTS gridstatus CASCADE;
                DROP TYPE IF EXISTS gridsquarestatus CASCADE;
                DROP TYPE IF EXISTS foilholestatus CASCADE;
                DROP TYPE IF EXISTS micrographstatus CASCADE;
            END $$;
        """)
        sess.execute(teardown_query)
        sess.commit()

    # Create all tables using SQLModel
    SQLModel.metadata.create_all(engine)

    # Create separate small SQL statements for each index to avoid batch failures
    with SQLModelSession(engine) as sess:
        try:
            # acquisition indexes
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_acquisition_id_pattern ON acquisition (uuid text_pattern_ops);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_acquisition_id_hash ON acquisition USING hash (uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_acquisition_name ON acquisition (name);"))

            # atlas indexes
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_atlas_id_pattern ON atlas (uuid text_pattern_ops);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_atlas_grid_uuid ON atlas (grid_uuid);"))

            # grid indexes
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_grid_uuid_pattern ON grid (uuid text_pattern_ops);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_grid_uuid_hash ON grid USING hash (uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_grid_acquisition_id ON grid (acquisition_uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_grid_name ON grid (name);"))

            # gridsquare indexes
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_gridsquare_id_pattern ON gridsquare (uuid text_pattern_ops);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_gridsquare_id_hash ON gridsquare USING hash (uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_gridsquare_grid_uuid ON gridsquare (grid_uuid);"))

            # foilhole indexes
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_foilhole_id_pattern ON foilhole (uuid text_pattern_ops);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_foilhole_id_hash ON foilhole USING hash (uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_foilhole_gridsquare_id ON foilhole (gridsquare_uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_foilhole_quality ON foilhole (quality);"))

            # micrograph indexes
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_micrograph_id_pattern ON micrograph (uuid text_pattern_ops);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_micrograph_id_hash ON micrograph USING hash (uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_micrograph_foilhole_id ON micrograph (foilhole_uuid);"))

            # QualityPredictionModelParameter indexes
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_param_grid_uuid "
                    "ON qualitypredictionmodelparameter (grid_uuid);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_param_model_name "
                    "ON qualitypredictionmodelparameter (prediction_model_name);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_param_metric "
                    "ON qualitypredictionmodelparameter (metric_name);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_param_composite "
                    "ON qualitypredictionmodelparameter (grid_uuid, prediction_model_name);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_param_timestamp "
                    "ON qualitypredictionmodelparameter (timestamp);"
                )
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_quality_model_param_key ON qualitypredictionmodelparameter (key);")
            )

            # QualityPredictionModelWeight indexes
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_weight_grid_uuid "
                    "ON qualitypredictionmodelweight (grid_uuid);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_weight_micrograph_uuid "
                    "ON qualitypredictionmodelweight (micrograph_uuid);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_weight_model_name "
                    "ON qualitypredictionmodelweight (prediction_model_name);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_weight_metric "
                    "ON qualitypredictionmodelparameter (metric_name);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_weight_grid_model "
                    "ON qualitypredictionmodelweight (grid_uuid, prediction_model_name);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_weight_micrograph_model "
                    "ON qualitypredictionmodelweight (micrograph_uuid, prediction_model_name);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_weight_timestamp "
                    "ON qualitypredictionmodelweight (timestamp);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_weight_value "
                    "ON qualitypredictionmodelweight (weight);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_model_weight_quality "
                    "ON qualitypredictionmodelweight (micrograph_quality);"
                )
            )

            # QualityPrediction indexes
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_prediction_model_name "
                    "ON qualityprediction (prediction_model_name);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_prediction_metric "
                    "ON qualitypredictionmodelparameter (metric_name);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_prediction_foilhole_uuid "
                    "ON qualityprediction (foilhole_uuid);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_prediction_gridsquare_uuid "
                    "ON qualityprediction (gridsquare_uuid);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_prediction_model_foilhole "
                    "ON qualityprediction (prediction_model_name, foilhole_uuid);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_quality_prediction_model_gridsquare "
                    "ON qualityprediction (prediction_model_name, gridsquare_uuid);"
                )
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_quality_prediction_timestamp ON qualityprediction (timestamp);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_quality_prediction_value ON qualityprediction (value);"))

            # Agent communication indexes
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_agent_session_agent_id ON agentsession (agent_id);"))
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_agent_session_acquisition_uuid ON agentsession (acquisition_uuid);"
                )
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_agent_session_status ON agentsession (status);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_agent_session_created_at ON agentsession (created_at);"))
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_session_last_activity ON agentsession (last_activity_at);")
            )

            # Agent instruction indexes
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_instruction_session_id ON agentinstruction (session_id);")
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_instruction_agent_id ON agentinstruction (agent_id);")
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_instruction_type ON agentinstruction (instruction_type);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_agent_instruction_status ON agentinstruction (status);"))
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_instruction_created_at ON agentinstruction (created_at);")
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_instruction_sent_at ON agentinstruction (sent_at);")
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_agent_instruction_acknowledged_at "
                    "ON agentinstruction (acknowledged_at);"
                )
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_instruction_expires_at ON agentinstruction (expires_at);")
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_instruction_sequence ON agentinstruction (sequence_number);")
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_instruction_priority ON agentinstruction (priority);")
            )

            # Agent connection indexes
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_connection_session_id ON agentconnection (session_id);")
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_connection_agent_id ON agentconnection (agent_id);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_agent_connection_status ON agentconnection (status);"))
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_connection_created_at ON agentconnection (created_at);")
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_agent_connection_heartbeat ON agentconnection (last_heartbeat_at);"
                )
            )

            # Agent acknowledgement indexes
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_agent_ack_instruction_id "
                    "ON agentinstructionacknowledgement (instruction_id);"
                )
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_ack_agent_id ON agentinstructionacknowledgement (agent_id);")
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_agent_ack_session_id "
                    "ON agentinstructionacknowledgement (session_id);"
                )
            )
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_agent_ack_status ON agentinstructionacknowledgement (status);")
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_agent_ack_created_at "
                    "ON agentinstructionacknowledgement (created_at);"
                )
            )
            sess.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_agent_ack_processed_at "
                    "ON agentinstructionacknowledgement (processed_at);"
                )
            )

            sess.commit()
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            sess.rollback()

        try:
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_atlastile_id_pattern ON atlastile (uuid text_pattern_ops);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_atlastile_atlas_id ON atlastile (atlas_uuid);"))
            sess.commit()
        except Exception as e:
            logger.error(f"Error creating atlastile indexes: {e}")
            sess.rollback()


def main():
    db_engine = setup_postgres_connection()
    _create_db_and_tables(db_engine)


if __name__ == "__main__":
    main()
