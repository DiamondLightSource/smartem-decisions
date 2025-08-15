from datetime import datetime
from typing import Optional

from sqlalchemy import Column, text
from sqlmodel import Field, Relationship, SQLModel
from sqlmodel import Session as SQLModelSession

from smartem_backend.model.entity_status import (
    AcquisitionStatusType,
    FoilHoleStatusType,
    GridSquareStatusType,
    GridStatusType,
    MicrographStatusType,
)
from smartem_backend.utils import logger, setup_postgres_connection
from smartem_common.entity_status import (
    AcquisitionStatus,
    FoilHoleStatus,
    GridSquareStatus,
    GridStatus,
    MicrographStatus,
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
    parameters: list["QualityPredictionModelParameter"] = Relationship(back_populates="model", cascade_delete=True)
    weights: list["QualityPredictionModelWeight"] = Relationship(back_populates="model", cascade_delete=True)
    predictions: list["QualityPrediction"] = Relationship(back_populates="model", cascade_delete=True)


class QualityPredictionModelParameter(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_uuid: str = Field(foreign_key="grid.uuid")
    timestamp: datetime = Field(default_factory=datetime.now)
    prediction_model_name: str = Field(foreign_key="qualitypredictionmodel.name")
    key: str
    value: float
    group: str = ""
    model: QualityPredictionModel | None = Relationship(back_populates="parameters")
    grid: Grid | None = Relationship(back_populates="quality_model_parameters")


class QualityPredictionModelWeight(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    grid_uuid: str = Field(foreign_key="grid.uuid")
    micrograph_uuid: str | None = Field(default=None, foreign_key="micrograph.uuid")
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
    foilhole_uuid: str | None = Field(default=None, foreign_key="foilhole.uuid")
    gridsquare_uuid: str | None = Field(default=None, foreign_key="gridsquare.uuid")
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


def _insert_prediction_model_data(engine):
    """Insert mock prediction model data using cute science fiction robots."""
    robot_models = [
        {
            "name": "R2-D2",
            "description": (
                "A sassy trash can on wheels who speaks only in beeps but somehow "
                "always has the last word in every argument."
            ),
        },
        {
            "name": "Claptrap",
            "description": (
                "An overly enthusiastic one-wheeled model which never stops talking "
                "and considers stairs to be it's greatest nemesis in the universe."
            ),
        },
        {
            "name": "WALL-E",
            "description": (
                "A lonely garbage-compacting model which falls in love and accidentally "
                "saves humanity while pursuing it's passion for collecting shiny objects."
            ),
        },
        {
            "name": "Bender",
            "description": (
                "A beer-guzzling, cigar-smoking model which dreams of becoming a folk "
                "singer but settles for petty theft and making sarcastic comments about humans."
            ),
        },
    ]

    with SQLModelSession(engine) as sess:
        for robot in robot_models:
            # Check if model already exists to avoid duplicates
            existing_model = sess.get(QualityPredictionModel, robot["name"])
            if existing_model is None:
                model = QualityPredictionModel(name=robot["name"], description=robot["description"])
                sess.add(model)
                logger.info(f"Added prediction model: {robot['name']}")
            else:
                logger.info(f"Prediction model already exists: {robot['name']}")
        sess.commit()


def main():
    db_engine = setup_postgres_connection()
    _create_db_and_tables(db_engine)
    _insert_prediction_model_data(db_engine)


if __name__ == "__main__":
    main()
