from datetime import datetime
from typing import Optional, List

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
    logger,
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
    grids: List["Grid"] = Relationship(sa_relationship_kwargs={"back_populates": "acquisition"}, cascade_delete=True)


class Atlas(SQLModel, table=True, table_name="atlas"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    atlas_id: str = Field(default="")
    grid_id: str | None = Field(default=None, foreign_key="grid.uuid")
    acquisition_date: datetime | None = Field(default=None)
    storage_folder: str | None = Field(default=None)
    description: str | None = Field(default=None)
    name: str = Field(default="")
    grid: Optional["Grid"] = Relationship(sa_relationship_kwargs={"back_populates": "atlas"})
    atlastiles: List["AtlasTile"] = Relationship(
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
    acquisition: Acquisition = Relationship(sa_relationship_kwargs={"back_populates": "grids"})
    gridsquares: List["GridSquare"] = Relationship(
        sa_relationship_kwargs={"back_populates": "grid"}, cascade_delete=True
    )
    atlas: Optional["Atlas"] = Relationship(sa_relationship_kwargs={"back_populates": "grid"})
    quality_model_parameters: List["QualityPredictionModelParameter"] = Relationship(
        back_populates="grid", cascade_delete=True
    )
    quality_model_weights: List["QualityPredictionModelWeight"] = Relationship(
        back_populates="grid", cascade_delete=True
    )


class AtlasTile(SQLModel, table=True, table_name="atlastile"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    atlas_id: str | None = Field(default=None, foreign_key="atlas.uuid")
    tile_id: str = Field(default="")
    position_x: int | None = Field(default=None)
    position_y: int | None = Field(default=None)
    size_x: int | None = Field(default=None)
    size_y: int | None = Field(default=None)
    file_format: str | None = Field(default=None)
    base_filename: str | None = Field(default=None)
    atlas: Optional["Atlas"] = Relationship(sa_relationship_kwargs={"back_populates": "atlastiles"})


class GridSquare(SQLModel, table=True, table_name="gridsquare"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    grid_id: str | None = Field(default=None, foreign_key="grid.uuid")
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
    foilholes: List["FoilHole"] = Relationship(
        sa_relationship_kwargs={"back_populates": "gridsquare"}, cascade_delete=True
    )
    prediction: List["QualityPrediction"] = Relationship(back_populates="gridsquare", cascade_delete=True)


class FoilHole(SQLModel, table=True, table_name="foilhole"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    gridsquare_id: str | None = Field(default=None, foreign_key="gridsquare.uuid")
    status: FoilHoleStatus = Field(default=FoilHoleStatus.NONE, sa_column=Column(FoilHoleStatusType()))
    foilhole_id: str = Field(default="")
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
    micrographs: List["Micrograph"] = Relationship(
        sa_relationship_kwargs={"back_populates": "foilhole"}, cascade_delete=True
    )
    prediction: List["QualityPrediction"] = Relationship(back_populates="foilhole", cascade_delete=True)


class Micrograph(SQLModel, table=True, table_name="micrograph"):
    __table_args__ = {"extend_existing": True}
    uuid: str = Field(primary_key=True)
    foilhole_id: str | None = Field(default=None, foreign_key="foilhole.uuid")
    status: MicrographStatus = Field(default=MicrographStatus.NONE, sa_column=Column(MicrographStatusType()))
    micrograph_id: str = Field(default="")
    location_id: str | None = Field(default=None)
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
    quality_model_weights: List["QualityPredictionModelWeight"] = Relationship(
        back_populates="micrograph", cascade_delete=True
    )


class QualityPredictionModel(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    name: str = Field(primary_key=True)
    description: str = ""
    parameters: List["QualityPredictionModelParameter"] = Relationship(back_populates="model", cascade_delete=True)
    weights: List["QualityPredictionModelWeight"] = Relationship(back_populates="model", cascade_delete=True)
    predictions: List["QualityPrediction"] = Relationship(back_populates="model", cascade_delete=True)


class QualityPredictionModelParameter(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_id: str = Field(foreign_key="grid.uuid")
    timestamp: datetime = Field(default_factory=datetime.now)
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    key: str
    value: float
    model: QualityPredictionModel | None = Relationship(back_populates="parameters")
    grid: Grid | None = Relationship(back_populates="quality_model_parameters")


class QualityPredictionModelWeight(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_id: str = Field(foreign_key="grid.uuid")
    micrograph_id: str | None = Field(default=None, foreign_key="micrograph.uuid")
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
    foilhole_id: str | None = Field(default=None, foreign_key="foilhole.uuid")
    gridsquare_id: str | None = Field(default=None, foreign_key="gridsquare.uuid")
    foilhole: FoilHole | None = Relationship(back_populates="prediction")
    gridsquare: GridSquare | None = Relationship(back_populates="prediction")
    model: QualityPredictionModel | None = Relationship(back_populates="predictions")


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
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_atlas_grid_id ON atlas (grid_id);"))

            # grid indexes
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_grid_id_pattern ON grid (uuid text_pattern_ops);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_grid_id_hash ON grid USING hash (uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_grid_acquisition_id ON grid (acquisition_id);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_grid_name ON grid (name);"))

            # gridsquare indexes
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_gridsquare_id_pattern ON gridsquare (uuid text_pattern_ops);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_gridsquare_id_hash ON gridsquare USING hash (uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_gridsquare_grid_id ON gridsquare (grid_id);"))

            # foilhole indexes
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_foilhole_id_pattern ON foilhole (uuid text_pattern_ops);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_foilhole_id_hash ON foilhole USING hash (uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_foilhole_gridsquare_id ON foilhole (gridsquare_id);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_foilhole_quality ON foilhole (quality);"))

            # micrograph indexes
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_micrograph_id_pattern ON micrograph (uuid text_pattern_ops);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_micrograph_id_hash ON micrograph USING hash (uuid);"))
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_micrograph_foilhole_id ON micrograph (foilhole_id);"))

            sess.commit()
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            sess.rollback()

        try:
            sess.execute(
                text("CREATE INDEX IF NOT EXISTS idx_atlastile_id_pattern ON atlastile (uuid text_pattern_ops);")
            )
            sess.execute(text("CREATE INDEX IF NOT EXISTS idx_atlastile_atlas_id ON atlastile (atlas_id);"))
            sess.commit()
        except Exception as e:
            logger.error(f"Error creating atlastile indexes: {e}")
            sess.rollback()


def main():
    db_engine = setup_postgres_connection()
    _create_db_and_tables(db_engine)


if __name__ == "__main__":
    main()
