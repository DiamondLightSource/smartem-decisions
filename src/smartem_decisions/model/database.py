from datetime import datetime

from sqlalchemy import Column, text
from sqlmodel import (
    Field,
    Relationship,
    SQLModel,
    Session as SQLModelSession,
)

from src.smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    AcquisitionStatusType,
    FoilHoleStatus,
    FoilHoleStatusType,
    GridSquareStatus,
    GridSquareStatusType,
    GridStatus,
    GridStatusType,
    MicrographStatus,
    MicrographStatusType,
)
from src.smartem_decisions.utils import (
    setup_postgres_connection,
)


class Acquisition(SQLModel, table=True, table_name="acquisition"):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    epu_id: str | None = Field(default=None)
    name: str
    status: AcquisitionStatus = Field(default=AcquisitionStatus.PLANNED, sa_column=Column(AcquisitionStatusType()))
    start_time: datetime | None = Field(default=None)
    end_time: datetime | None = Field(default=None)
    paused_time: datetime | None = Field(default=None)
    # Added fields from EpuSessionData
    storage_path: str | None = Field(default=None)
    atlas_path: str | None = Field(default=None)
    clustering_mode: str | None = Field(default=None)
    clustering_radius: str | None = Field(default=None)
    grids: list["Grid"] = Relationship(sa_relationship_kwargs={"back_populates": "acquisition"}, cascade_delete=True)


class Atlas(SQLModel, table=True, table_name="atlas"):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    atlas_id: str = Field(default="")
    grid_id: int | None = Field(default=None, foreign_key="grid.id")
    acquisition_date: datetime | None = Field(default=None)
    storage_folder: str | None = Field(default=None)
    description: str | None = Field(default=None)
    name: str = Field(default="")
    grid: "Grid" = Relationship(sa_relationship_kwargs={"back_populates": "atlas"})
    atlas_tiles: list["AtlasTile"] = Relationship(sa_relationship_kwargs={"back_populates": "atlas"}, cascade_delete=True)


class AtlasTile(SQLModel, table=True, table_name="atlas_tile"):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    atlas_id: int | None = Field(default=None, foreign_key="atlas.id")
    tile_id: str = Field(default="")
    position_x: int | None = Field(default=None)
    position_y: int | None = Field(default=None)
    size_x: int | None = Field(default=None)
    size_y: int | None = Field(default=None)
    file_format: str | None = Field(default=None)
    base_filename: str | None = Field(default=None)
    atlas: Atlas = Relationship(sa_relationship_kwargs={"back_populates": "atlas_tiles"})


class Grid(SQLModel, table=True, table_name="grid"):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    acquisition_id: int | None = Field(default=None, foreign_key="acquisition.id")
    status: GridStatus = Field(default=GridStatus.NONE, sa_column=Column(GridStatusType()))
    name: str
    data_dir: str | None = Field(default=None)
    atlas_dir: str | None = Field(default=None)
    scan_start_time: datetime | None = Field(default=None)
    scan_end_time: datetime | None = Field(default=None)
    acquisition: Acquisition = Relationship(sa_relationship_kwargs={"back_populates": "grids"})
    gridsquares: list["GridSquare"] = Relationship(sa_relationship_kwargs={"back_populates": "grid"}, cascade_delete=True)
    atlas: Atlas = Relationship(sa_relationship_kwargs={"back_populates": "grid"})
    quality_model_parameters: list["QualityPredictionModelParameter"] = Relationship(
        back_populates="grid", cascade_delete=True
    )
    quality_model_weights: list["QualityPredictionModelWeight"] = Relationship(
        back_populates="grid", cascade_delete=True
    )


class GridSquare(SQLModel, table=True, table_name="gridsquare"):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_id: int | None = Field(default=None, foreign_key="grid.id")
    status: GridSquareStatus = Field(default=GridSquareStatus.NONE, sa_column=Column(GridSquareStatusType()))
    gridsquare_id: str = Field(default="")  # From the original model id field
    data_dir: str | None = Field(default=None)

    # From GridSquareMetadata
    atlas_node_id: int | None = Field(default=None)
    state: str | None = Field(default=None)
    rotation: float | None = Field(default=None)
    image_path: str | None = Field(default=None)
    selected: bool | None = Field(default=None)
    unusable: bool | None = Field(default=None)

    # From GridSquareStagePosition
    stage_position_x: float | None = Field(default=None)
    stage_position_y: float | None = Field(default=None)
    stage_position_z: float | None = Field(default=None)

    # From GridSquarePosition
    center_x: int | None = Field(default=None)
    center_y: int | None = Field(default=None)
    physical_x: float | None = Field(default=None)
    physical_y: float | None = Field(default=None)
    size_width: int | None = Field(default=None)
    size_height: int | None = Field(default=None)

    # From GridSquareManifest
    acquisition_datetime: datetime | None = Field(default=None)
    defocus: float | None = Field(default=None)
    magnification: float | None = Field(default=None)
    pixel_size: float | None = Field(default=None)
    detector_name: str | None = Field(default=None)
    applied_defocus: float | None = Field(default=None)

    grid: Grid = Relationship(sa_relationship_kwargs={"back_populates": "gridsquares"})
    foilholes: list["FoilHole"] = Relationship(sa_relationship_kwargs={"back_populates": "gridsquare"}, cascade_delete=True)
    prediction: list["QualityPrediction"] = Relationship(back_populates="gridsquare", cascade_delete=True)


class FoilHole(SQLModel, table=True, table_name="foilhole"):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    gridsquare_id: int | None = Field(default=None, foreign_key="gridsquare.id")
    status: FoilHoleStatus = Field(default=FoilHoleStatus.NONE, sa_column=Column(FoilHoleStatusType()))
    foilhole_id: str = Field(default="")  # From the original model id field

    # From FoilHoleData
    center_x: float | None = Field(default=None)
    center_y: float | None = Field(default=None)
    quality: float | None = Field(default=None)
    rotation: float | None = Field(default=None)
    size_width: float | None = Field(default=None)
    size_height: float | None = Field(default=None)

    # From FoilHolePosition
    x_location: int | None = Field(default=None)
    y_location: int | None = Field(default=None)
    x_stage_position: float | None = Field(default=None)
    y_stage_position: float | None = Field(default=None)
    diameter: int | None = Field(default=None)
    is_near_grid_bar: bool = Field(default=False)

    gridsquare: GridSquare = Relationship(sa_relationship_kwargs={"back_populates": "foilholes"})
    micrographs: list["Micrograph"] = Relationship(sa_relationship_kwargs={"back_populates": "foilhole"}, cascade_delete=True)
    prediction: list["QualityPrediction"] = Relationship(back_populates="foilhole", cascade_delete=True)


class Micrograph(SQLModel, table=True, table_name="micrograph"):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    foilhole_id: int | None = Field(default=None, foreign_key="foilhole.id")
    status: MicrographStatus = Field(default=MicrographStatus.NONE, sa_column=Column(MicrographStatusType()))

    # Fields from MicrographData
    micrograph_id: str = Field(default="")  # From the original model id field
    location_id: str | None = Field(default=None)
    high_res_path: str | None = Field(default=None)
    manifest_file: str | None = Field(default=None)

    # Fields from MicrographManifest
    acquisition_datetime: datetime | None = Field(default=None)
    defocus: float | None = Field(default=None)
    detector_name: str | None = Field(default=None)
    energy_filter: bool | None = Field(default=None)
    phase_plate: bool | None = Field(default=None)
    image_size_x: int | None = Field(default=None)
    image_size_y: int | None = Field(default=None)
    binning_x: int | None = Field(default=None)
    binning_y: int | None = Field(default=None)

    # Pre-existing fields
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
    parameters: list["QualityPredictionModelParameter"] = Relationship(back_populates="model", cascade_delete=True)
    weights: list["QualityPredictionModelWeight"] = Relationship(back_populates="model", cascade_delete=True)
    predictions: list["QualityPrediction"] = Relationship(back_populates="model", cascade_delete=True)


class QualityPredictionModelParameter(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    id: int | None = Field(default=None, primary_key=True)
    grid_id: int = Field(foreign_key="grid.id")
    timestamp: datetime = Field(default_factory=datetime.now)
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    key: str
    value: float
    model: QualityPredictionModel | None = Relationship(back_populates="parameters")
    grid: Grid | None = Relationship(back_populates="quality_model_parameters")


class QualityPredictionModelWeight(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_id: int = Field(foreign_key="grid.id")
    micrograph_id: int | None = Field(default=None, foreign_key="micrograph.id")
    micrograph_quality: bool | None = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)
    origin: str | None = Field(default=None)
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    weight: float
    model: QualityPredictionModel | None = Relationship(back_populates="weights")
    grid: Grid | None = Relationship(back_populates="quality_model_weights")
    micrograph: Micrograph | None = Relationship(back_populates="quality_model_weights")


class QualityPrediction(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now)
    value: float
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    foilhole_id: int | None = Field(default=None, foreign_key="foilhole.id")
    gridsquare_id: int | None = Field(default=None, foreign_key="gridsquare.id")
    foilhole: FoilHole | None = Relationship(back_populates="prediction")
    gridsquare: GridSquare | None = Relationship(back_populates="prediction")
    model: QualityPredictionModel | None = Relationship(back_populates="predictions")


def _create_db_and_tables(engine):
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
        sess.execute(teardown_query) # We do in fact want to use `sess.execute` not `.exec` here
        sess.commit()

    SQLModel.metadata.create_all(engine)
    """
    SELECT enum_range(NULL::acquisitionstatus);
    SELECT enum_range(NULL::gridstatus);
    SELECT enum_range(NULL::gridsquarestatus);
    SELECT enum_range(NULL::foilholestatus);
    SELECT enum_range(NULL::micrographstatus);
    """


def main():
    db_engine = setup_postgres_connection()
    _create_db_and_tables(db_engine)


if __name__ == "__main__":
    main()
