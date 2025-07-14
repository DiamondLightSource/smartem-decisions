import json
import logging
import os
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session as SqlAlchemySession
from sqlalchemy.orm import sessionmaker

from src.smartem_decisions._version import __version__
from src.smartem_decisions.model.database import (
    Acquisition,
    Atlas,
    AtlasTile,
    FoilHole,
    Grid,
    GridSquare,
    Micrograph,
)
from src.smartem_decisions.model.entity_status import (
    AcquisitionStatus,
    FoilHoleStatus,
    GridSquareStatus,
    GridStatus,
    MicrographStatus,
)
from src.smartem_decisions.model.http_request import (
    AcquisitionCreateRequest,
    AcquisitionUpdateRequest,
    AtlasCreateRequest,
    AtlasTileCreateRequest,
    AtlasTileUpdateRequest,
    AtlasUpdateRequest,
    FoilHoleCreateRequest,
    FoilHoleUpdateRequest,
    GridCreateRequest,
    GridSquareCreateRequest,
    GridSquareUpdateRequest,
    GridUpdateRequest,
    MicrographCreateRequest,
    MicrographUpdateRequest,
)
from src.smartem_decisions.model.http_response import (
    AcquisitionResponse,
    AtlasResponse,
    AtlasTileResponse,
    FoilHoleResponse,
    GridResponse,
    GridSquareResponse,
    MicrographResponse,
)
from src.smartem_decisions.mq_publisher import (
    publish_acquisition_created,
    publish_acquisition_deleted,
    publish_acquisition_updated,
    publish_atlas_created,
    publish_atlas_deleted,
    publish_atlas_tile_created,
    publish_atlas_tile_deleted,
    publish_atlas_tile_updated,
    publish_atlas_updated,
    publish_foilhole_created,
    publish_foilhole_deleted,
    publish_foilhole_updated,
    publish_grid_created,
    publish_grid_deleted,
    publish_grid_updated,
    publish_gridsquare_created,
    publish_gridsquare_deleted,
    publish_gridsquare_updated,
    publish_micrograph_created,
    publish_micrograph_deleted,
    publish_micrograph_updated,
)
from src.smartem_decisions.utils import setup_postgres_connection, setup_rabbitmq

db_engine = setup_postgres_connection()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

# Set up RabbitMQ connections for health checks
try:
    rmq_publisher, rmq_consumer = setup_rabbitmq()
except Exception as e:
    # Logger is defined later, so we'll use print for early initialization errors
    print(f"Failed to initialize RabbitMQ connections for health checks: {e}")
    rmq_publisher, rmq_consumer = None, None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create a dependency object at module level to avoid B008 linting errors
DB_DEPENDENCY = Depends(get_db)


app = FastAPI(
    title="SmartEM Decisions Backend API",
    description="API for accessing and managing electron microscopy data",
    version=__version__,
    redoc_url=None,
)

# Configure logging based on environment variable
# SMARTEM_LOG_LEVEL can be: ERROR (default), INFO, DEBUG
log_level_str = os.getenv("SMARTEM_LOG_LEVEL", "ERROR").upper()
log_level_map = {"ERROR": logging.ERROR, "INFO": logging.INFO, "DEBUG": logging.DEBUG}
log_level = log_level_map.get(log_level_str, logging.ERROR)

logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("smartem_decisions_api")


# Also configure uvicorn loggers to use the same level
uvicorn_loggers = ["uvicorn", "uvicorn.error", "uvicorn.access"]
for logger_name in uvicorn_loggers:
    logging.getLogger(logger_name).setLevel(log_level)


def check_database_health():
    """Check database connectivity and basic functionality"""
    try:
        db = SessionLocal()
        # Simple query to test database connectivity
        result = db.execute(text("SELECT 1 as health_check"))
        row = result.fetchone()
        db.close()

        if row and row[0] == 1:
            return {"status": "ok", "details": "Database connection successful"}
        else:
            return {"status": "error", "details": "Database query returned unexpected result"}

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "error", "details": f"Database connection failed: {str(e)}"}


def check_rabbitmq_health():
    """Check RabbitMQ connectivity"""
    if rmq_publisher is None:
        return {"status": "error", "details": "RabbitMQ publisher not initialized"}

    try:
        # Test connection by attempting to connect
        rmq_publisher.connect()

        # Connection successful - close it immediately to avoid resource leaks
        rmq_publisher.close()
        return {"status": "ok", "details": "RabbitMQ connection successful"}

    except Exception as e:
        logger.error(f"RabbitMQ health check failed: {e}")
        return {"status": "error", "details": f"RabbitMQ connection failed: {str(e)}"}
    finally:
        # Ensure connection is closed
        try:
            rmq_publisher.close()
        except Exception:
            pass  # Ignore cleanup errors


# TODO remove in prod:
@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH") and log_level == logging.DEBUG:
        body = await request.body()

        try:
            body_str = body.decode()
            if body_str:
                try:
                    pretty_json = json.dumps(json.loads(body_str), indent=2)
                    logger.info(f"Request {request.method} {request.url.path}:\n{pretty_json}")
                except (json.JSONDecodeError, ValueError):
                    logger.info(f"Request {request.method} {request.url.path}:\n{body_str}")
        except UnicodeDecodeError:
            logger.info(f"Request {request.method} {request.url.path}: [binary data]")

    response = await call_next(request)
    return response


@app.get("/status")
def get_status():
    """Get API status and configuration information"""
    return {
        "status": "ok",
        "service": "SmartEM Decisions API",
        "version": __version__,
        "timestamp": datetime.now().isoformat(),
        "configuration": {
            "log_level": log_level_str,
            "environment": os.getenv("ENVIRONMENT", "unknown"),
        },
        "endpoints": {"health": "/health", "status": "/status", "docs": "/docs", "openapi": "/openapi.json"},
        "uptime_seconds": None,  # Could be implemented with start time tracking
        "features": {
            "database_operations": True,
            "message_queue_publishing": rmq_publisher is not None,
            "direct_db_writes": True,
        },
    }


@app.get("/health")
def get_health():
    """Health check endpoint with actual connectivity checks"""
    # Perform health checks
    db_health = check_database_health()
    rabbitmq_health = check_rabbitmq_health()

    # Determine overall status
    overall_status = "ok" if db_health["status"] == "ok" and rabbitmq_health["status"] == "ok" else "degraded"

    # Log aggregator is not implemented yet, so we'll mark it as "not_configured"
    log_aggregator_status = "not_configured"

    health_response = {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": {"status": db_health["status"], "details": db_health["details"]},
            "event_broker": {"status": rabbitmq_health["status"], "details": rabbitmq_health["details"]},
            "log_aggregator": {"status": log_aggregator_status, "details": "Log aggregation service not configured"},
        },
        "version": __version__,
    }

    # Set appropriate HTTP status code
    if overall_status == "ok":
        return health_response
    else:
        # Return 503 Service Unavailable if any critical service is down
        raise HTTPException(status_code=503, detail=health_response)


# ============ Acquisition CRUD Operations ============


@app.get("/acquisitions", response_model=list[AcquisitionResponse])
def get_acquisitions(db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all acquisitions"""
    return db.query(Acquisition).all()


@app.post("/acquisitions", response_model=AcquisitionResponse, status_code=status.HTTP_201_CREATED)
def create_acquisition(acquisition: AcquisitionCreateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Create a new acquisition"""
    acquisition_data = {
        "uuid": acquisition.uuid,
        "status": AcquisitionStatus.STARTED,
        **acquisition.model_dump(exclude={"uuid"}),
    }

    db_acquisition = Acquisition(**acquisition_data)
    db.add(db_acquisition)
    db.commit()
    db.refresh(db_acquisition)

    success = publish_acquisition_created(
        uuid=db_acquisition.uuid,
        id=db_acquisition.id,
        name=db_acquisition.name,
        status=db_acquisition.status.value,
        start_time=db_acquisition.start_time,
        end_time=db_acquisition.end_time,
        metadata=db_acquisition.metadata,
    )
    if not success:
        logger.error(f"Failed to publish acquisition created event for UUID: {db_acquisition.uuid}")

    response_data = {
        "uuid": acquisition.uuid,
        "status": AcquisitionStatus.STARTED,
        **acquisition.model_dump(exclude={"uuid", "status"}),
    }

    return AcquisitionResponse(**response_data)


@app.get("/acquisitions/{acquisition_uuid}", response_model=AcquisitionResponse)
def get_acquisition(acquisition_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get a single acquisition by ID"""
    acquisition = db.query(Acquisition).filter(Acquisition.uuid == acquisition_uuid).first()
    if not acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")
    return acquisition


@app.put("/acquisitions/{acquisition_uuid}", response_model=AcquisitionResponse)
def update_acquisition(
    acquisition_uuid: str, acquisition: AcquisitionUpdateRequest, db: SqlAlchemySession = DB_DEPENDENCY
):
    """Update an acquisition"""
    db_acquisition = db.query(Acquisition).filter(Acquisition.uuid == acquisition_uuid).first()
    if not db_acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    update_data = acquisition.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_acquisition, key, value)
    db.commit()
    db.refresh(db_acquisition)

    success = publish_acquisition_updated(
        uuid=db_acquisition.uuid,
        id=db_acquisition.id,
    )
    if not success:
        logger.error(f"Failed to publish acquisition updated event for UUID: {db_acquisition.uuid}")

    response_data = {
        "uuid": db_acquisition.uuid,
        "status": db_acquisition.status,
        "id": db_acquisition.id,
        "name": db_acquisition.name,
        "start_time": db_acquisition.start_time,
        "end_time": db_acquisition.end_time,
        "paused_time": db_acquisition.paused_time,
        "storage_path": db_acquisition.storage_path,
        "atlas_path": db_acquisition.atlas_path,
        "clustering_mode": db_acquisition.clustering_mode,
        "clustering_radius": db_acquisition.clustering_radius,
        "instrument_model": db_acquisition.instrument_model,
        "instrument_id": db_acquisition.instrument_id,
        "computer_name": db_acquisition.computer_name,
    }

    return AcquisitionResponse(**response_data)


@app.delete("/acquisitions/{acquisition_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_acquisition(acquisition_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete an acquisition"""
    db_acquisition = db.query(Acquisition).filter(Acquisition.uuid == acquisition_uuid).first()
    if not db_acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    db.delete(db_acquisition)
    db.commit()

    success = publish_acquisition_deleted(uuid=acquisition_uuid)
    if not success:
        logger.error(f"Failed to publish acquisition deleted event for UUID: {acquisition_uuid}")

    return None


# ============ Grid CRUD Operations ============


@app.get("/grids", response_model=list[GridResponse])
def get_grids(db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all grids"""
    return db.query(Grid).all()


@app.get("/grids/{grid_uuid}", response_model=GridResponse)
def get_grid(grid_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get a single grid by ID"""
    grid = db.query(Grid).filter(Grid.uuid == grid_uuid).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")
    return grid


@app.put("/grids/{grid_uuid}", response_model=GridResponse)
def update_grid(grid_uuid: str, grid: GridUpdateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Update a grid"""
    db_grid = db.query(Grid).filter(Grid.uuid == grid_uuid).first()
    if not db_grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    update_data = grid.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_grid, key, value)
    db.commit()
    db.refresh(db_grid)

    success = publish_grid_updated(uuid=db_grid.uuid, acquisition_uuid=db_grid.acquisition_uuid)
    if not success:
        logger.error(f"Failed to publish grid updated event for UUID: {db_grid.uuid}")

    response_data = {
        "uuid": db_grid.uuid,
        "acquisition_uuid": db_grid.acquisition_uuid,
        "status": db_grid.status,
        "name": db_grid.name,
        "data_dir": db_grid.data_dir,
        "atlas_dir": db_grid.atlas_dir,
        "scan_start_time": db_grid.scan_start_time,
        "scan_end_time": db_grid.scan_end_time,
    }

    return GridResponse(**response_data)


@app.delete("/grids/{grid_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grid(grid_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete a grid by publishing to RabbitMQ"""
    db_grid = db.query(Grid).filter(Grid.uuid == grid_uuid).first()
    if not db_grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    success = publish_grid_deleted(uuid=grid_uuid)
    if not success:
        logger.error(f"Failed to publish grid deleted event for ID: {grid_uuid}")

    return None


@app.get("/acquisitions/{acquisition_uuid}/grids", response_model=list[GridResponse])
def get_acquisition_grids(acquisition_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all grids for a specific acquisition"""
    return db.query(Grid).filter(Grid.acquisition_uuid == acquisition_uuid).all()


@app.post("/acquisitions/{acquisition_uuid}/grids", response_model=GridResponse, status_code=status.HTTP_201_CREATED)
def create_acquisition_grid(acquisition_uuid: str, grid: GridCreateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Create a new grid for a specific acquisition"""
    grid_data = {
        "uuid": grid.uuid,
        "acquisition_uuid": acquisition_uuid,
        "status": GridStatus.NONE,
        **grid.model_dump(),
    }

    db_grid = Grid(**grid_data)
    db.add(db_grid)
    db.commit()
    db.refresh(db_grid)

    success = publish_grid_created(uuid=db_grid.uuid, acquisition_uuid=db_grid.acquisition_uuid)
    if not success:
        logger.error(f"Failed to publish grid created event for UUID: {db_grid.uuid}")

    response_data = {
        "uuid": grid.uuid,
        "acquisition_uuid": acquisition_uuid,
        "status": GridStatus.NONE,
        **grid.model_dump(),
    }

    # Make sure status is set correctly (the above might get overridden by model_dump)
    if "status" not in response_data or response_data["status"] is None:
        response_data["status"] = GridStatus.NONE

    return GridResponse(**response_data)


# ============ Atlas CRUD Operations ============


@app.get("/atlases", response_model=list[AtlasResponse])
def get_atlases(db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all atlases"""
    return db.query(Atlas).all()


@app.get("/atlases/{atlas_uuid}", response_model=AtlasResponse)
def get_atlas(atlas_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get a single atlas by ID"""
    atlas = db.query(Atlas).filter(Atlas.uuid == atlas_uuid).first()
    if not atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")
    return atlas


@app.put("/atlases/{atlas_uuid}", response_model=AtlasResponse)
def update_atlas(atlas_uuid: str, atlas: AtlasUpdateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Update an atlas"""
    db_atlas = db.query(Atlas).filter(Atlas.uuid == atlas_uuid).first()
    if not db_atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    update_data = atlas.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_atlas, key, value)
    db.commit()
    db.refresh(db_atlas)

    success = publish_atlas_updated(uuid=db_atlas.uuid, id=db_atlas.atlas_id, grid_uuid=db_atlas.grid_uuid)
    if not success:
        logger.error(f"Failed to publish atlas updated event for UUID: {db_atlas.uuid}")

    response_data = {
        "uuid": db_atlas.uuid,
        "atlas_id": db_atlas.atlas_id,
        "grid_uuid": db_atlas.grid_uuid,
        "acquisition_date": db_atlas.acquisition_date,
        "storage_folder": db_atlas.storage_folder,
        "description": db_atlas.description,
        "name": db_atlas.name,
    }

    return AtlasResponse(**response_data)


@app.delete("/atlases/{atlas_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_atlas(atlas_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete an atlas by publishing to RabbitMQ"""
    db_atlas = db.query(Atlas).filter(Atlas.uuid == atlas_uuid).first()
    if not db_atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    success = publish_atlas_deleted(uuid=atlas_uuid)
    if not success:
        logger.error(f"Failed to publish atlas deleted event for ID: {atlas_uuid}")

    return None


@app.get("/grids/{grid_uuid}/atlas", response_model=AtlasResponse)
def get_grid_atlas(grid_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get the atlas for a specific grid"""
    atlas = db.query(Atlas).filter(Atlas.grid_uuid == grid_uuid).first()
    if not atlas:
        raise HTTPException(status_code=404, detail="Atlas not found for this grid")
    return atlas


@app.post("/grids/{grid_uuid}/atlas", response_model=AtlasResponse, status_code=status.HTTP_201_CREATED)
def create_grid_atlas(grid_uuid: str, atlas: AtlasCreateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Create a new atlas for a grid"""
    tiles_data = None
    if atlas.tiles:
        tiles_data = [tile.model_dump() for tile in atlas.tiles]
        atlas_dict = atlas.model_dump(exclude={"tiles"})
    else:
        atlas_dict = atlas.model_dump()

    # Override grid_uuid
    atlas_dict["grid_uuid"] = grid_uuid

    db_atlas = Atlas(**atlas_dict)
    db.add(db_atlas)
    db.commit()
    db.refresh(db_atlas)

    success = publish_atlas_created(uuid=db_atlas.uuid, id=db_atlas.atlas_id, grid_uuid=db_atlas.grid_uuid)
    if not success:
        logger.error(f"Failed to publish atlas created event for UUID: {db_atlas.uuid}")

    # If tiles were provided, create them too
    if tiles_data:
        for tile_data in tiles_data:
            # Add atlas_uuid to each tile
            tile_data["atlas_uuid"] = db_atlas.uuid
            db_tile = AtlasTile(**tile_data)
            db.add(db_tile)
            db.commit()
            db.refresh(db_tile)

            tile_success = publish_atlas_tile_created(
                uuid=db_tile.uuid, id=db_tile.tile_id, atlas_uuid=db_tile.atlas_uuid
            )
            if not tile_success:
                logger.error(f"Failed to publish atlas tile created event for UUID: {db_tile.uuid}")

    response_data = {
        "uuid": db_atlas.uuid,
        "atlas_id": db_atlas.atlas_id,
        "grid_uuid": db_atlas.grid_uuid,
        "acquisition_date": db_atlas.acquisition_date,
        "storage_folder": db_atlas.storage_folder,
        "description": db_atlas.description,
        "name": db_atlas.name,
    }

    return AtlasResponse(**response_data)


# ============ Atlas Tile CRUD Operations ============


@app.get("/atlas-tiles", response_model=list[AtlasTileResponse])
def get_atlas_tiles(db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all atlas tiles"""
    return db.query(AtlasTile).all()


@app.get("/atlas-tiles/{tile_uuid}", response_model=AtlasTileResponse)
def get_atlas_tile(tile_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get a single atlas tile by ID"""
    tile = db.query(AtlasTile).filter(AtlasTile.uuid == tile_uuid).first()
    if not tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")
    return tile


@app.put("/atlas-tiles/{tile_uuid}", response_model=AtlasTileResponse)
def update_atlas_tile(tile_uuid: str, tile: AtlasTileUpdateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Update an atlas tile"""
    db_tile = db.query(AtlasTile).filter(AtlasTile.uuid == tile_uuid).first()
    if not db_tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")

    update_data = tile.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_tile, key, value)
    db.commit()
    db.refresh(db_tile)

    success = publish_atlas_tile_updated(uuid=db_tile.uuid, id=db_tile.tile_id, atlas_uuid=db_tile.atlas_uuid)
    if not success:
        logger.error(f"Failed to publish atlas tile updated event for UUID: {db_tile.uuid}")

    response_data = {
        "uuid": db_tile.uuid,
        "atlas_uuid": db_tile.atlas_uuid,
        "tile_id": db_tile.tile_id,
        "position_x": db_tile.position_x,
        "position_y": db_tile.position_y,
        "size_x": db_tile.size_x,
        "size_y": db_tile.size_y,
        "file_format": db_tile.file_format,
        "base_filename": db_tile.base_filename,
    }

    return AtlasTileResponse(**response_data)


@app.delete("/atlas-tiles/{tile_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_atlas_tile(tile_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete an atlas tile by publishing to RabbitMQ"""
    db_tile = db.query(AtlasTile).filter(AtlasTile.uuid == tile_uuid).first()
    if not db_tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")

    success = publish_atlas_tile_deleted(uuid=tile_uuid)
    if not success:
        logger.error(f"Failed to publish atlas tile deleted event for ID: {tile_uuid}")

    return None


@app.get("/atlases/{atlas_uuid}/tiles", response_model=list[AtlasTileResponse])
def get_atlas_tiles_by_atlas(atlas_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all tiles for a specific atlas"""
    tiles = db.query(AtlasTile).filter(AtlasTile.atlas_uuid == atlas_uuid).all()
    return tiles


@app.post("/atlases/{atlas_uuid}/tiles", response_model=AtlasTileResponse, status_code=status.HTTP_201_CREATED)
def create_atlas_tile_for_atlas(atlas_uuid: str, tile: AtlasTileCreateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Create a new tile for a specific atlas"""
    tile_data = tile.model_dump()
    tile_data["atlas_uuid"] = atlas_uuid

    db_tile = AtlasTile(**tile_data)
    db.add(db_tile)
    db.commit()
    db.refresh(db_tile)

    success = publish_atlas_tile_created(uuid=db_tile.uuid, id=db_tile.tile_id, atlas_uuid=db_tile.atlas_uuid)
    if not success:
        logger.error(f"Failed to publish atlas tile created event for UUID: {db_tile.uuid}")

    response_data = {
        "uuid": db_tile.uuid,
        "atlas_uuid": db_tile.atlas_uuid,
        "tile_id": db_tile.tile_id,
        "position_x": db_tile.position_x,
        "position_y": db_tile.position_y,
        "size_x": db_tile.size_x,
        "size_y": db_tile.size_y,
        "file_format": db_tile.file_format,
        "base_filename": db_tile.base_filename,
    }

    return AtlasTileResponse(**response_data)


# ============ GridSquare CRUD Operations ============


@app.get("/gridsquares", response_model=list[GridSquareResponse])
def get_gridsquares(db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all grid squares"""
    return db.query(GridSquare).all()


@app.get("/gridsquares/{gridsquare_uuid}", response_model=GridSquareResponse)
def get_gridsquare(gridsquare_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get a single grid square by ID"""
    gridsquare = db.query(GridSquare).filter(GridSquare.uuid == gridsquare_uuid).first()
    if not gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")
    return gridsquare


@app.put("/gridsquares/{gridsquare_uuid}", response_model=GridSquareResponse)
def update_gridsquare(gridsquare_uuid: str, gridsquare: GridSquareUpdateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Update a grid square"""
    db_gridsquare = db.query(GridSquare).filter(GridSquare.uuid == gridsquare_uuid).first()
    if not db_gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    update_data = gridsquare.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_gridsquare, key, value)
    db.commit()
    db.refresh(db_gridsquare)

    success = publish_gridsquare_updated(
        uuid=db_gridsquare.uuid, grid_uuid=db_gridsquare.grid_uuid, gridsquare_id=db_gridsquare.gridsquare_id
    )
    if not success:
        logger.error(f"Failed to publish gridsquare updated event for UUID: {db_gridsquare.uuid}")

    response_data = {
        "uuid": db_gridsquare.uuid,
        "grid_uuid": db_gridsquare.grid_uuid,
        "status": db_gridsquare.status,
        "gridsquare_id": db_gridsquare.gridsquare_id,
        "data_dir": db_gridsquare.data_dir,
        "atlas_node_id": db_gridsquare.atlas_node_id,
        "state": db_gridsquare.state,
        "rotation": db_gridsquare.rotation,
        "image_path": db_gridsquare.image_path,
        "selected": db_gridsquare.selected,
        "unusable": db_gridsquare.unusable,
        "stage_position_x": db_gridsquare.stage_position_x,
        "stage_position_y": db_gridsquare.stage_position_y,
        "stage_position_z": db_gridsquare.stage_position_z,
        "center_x": db_gridsquare.center_x,
        "center_y": db_gridsquare.center_y,
        "physical_x": db_gridsquare.physical_x,
        "physical_y": db_gridsquare.physical_y,
        "size_width": db_gridsquare.size_width,
        "size_height": db_gridsquare.size_height,
        "acquisition_datetime": db_gridsquare.acquisition_datetime,
        "defocus": db_gridsquare.defocus,
        "magnification": db_gridsquare.magnification,
        "pixel_size": db_gridsquare.pixel_size,
        "detector_name": db_gridsquare.detector_name,
        "applied_defocus": db_gridsquare.applied_defocus,
    }

    return GridSquareResponse(**response_data)


@app.delete("/gridsquares/{gridsquare_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gridsquare(gridsquare_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete a grid square by publishing to RabbitMQ"""
    db_gridsquare = db.query(GridSquare).filter(GridSquare.uuid == gridsquare_uuid).first()
    if not db_gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    success = publish_gridsquare_deleted(uuid=gridsquare_uuid)
    if not success:
        logger.error(f"Failed to publish grid square deleted event for ID: {gridsquare_uuid}")

    return None


@app.get("/grids/{grid_uuid}/gridsquares", response_model=list[GridSquareResponse])
def get_grid_gridsquares(grid_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all grid squares for a specific grid"""
    return db.query(GridSquare).filter(GridSquare.grid_uuid == grid_uuid).all()


@app.post("/grids/{grid_uuid}/gridsquares", response_model=GridSquareResponse, status_code=status.HTTP_201_CREATED)
def create_grid_gridsquare(grid_uuid: str, gridsquare: GridSquareCreateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Create a new grid square for a specific grid"""
    gridsquare_data = {
        "uuid": gridsquare.uuid,
        "grid_uuid": grid_uuid,
        "status": GridSquareStatus.NONE,
        **gridsquare.model_dump(),
    }

    db_gridsquare = GridSquare(**gridsquare_data)
    db.add(db_gridsquare)
    db.commit()
    db.refresh(db_gridsquare)

    success = publish_gridsquare_created(
        uuid=db_gridsquare.uuid, grid_uuid=db_gridsquare.grid_uuid, gridsquare_id=db_gridsquare.gridsquare_id
    )
    if not success:
        logger.error(f"Failed to publish gridsquare created event for UUID: {db_gridsquare.uuid}")

    response_data = {
        "uuid": gridsquare.uuid,
        "grid_uuid": grid_uuid,
        "status": GridSquareStatus.NONE,
        **gridsquare.model_dump(),
    }

    # Make sure status is set correctly (the above might get overridden by model_dump)
    if "status" not in response_data or response_data["status"] is None:
        response_data["status"] = GridSquareStatus.NONE

    return GridSquareResponse(**response_data)


# ============ FoilHole CRUD Operations ============


@app.get("/foilholes", response_model=list[FoilHoleResponse])
def get_foilholes(db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all foil holes"""
    return db.query(FoilHole).all()


@app.get("/foilholes/{foilhole_uuid}", response_model=FoilHoleResponse)
def get_foilhole(foilhole_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get a single foil hole by ID"""
    foilhole = db.query(FoilHole).filter(FoilHole.uuid == foilhole_uuid).first()
    if not foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")
    return foilhole


@app.put("/foilholes/{foilhole_uuid}", response_model=FoilHoleResponse)
def update_foilhole(foilhole_uuid: str, foilhole: FoilHoleUpdateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Update a foil hole"""
    # TODO this isn't tested

    db_foilhole = db.query(FoilHole).filter(FoilHole.uuid == foilhole_uuid).first()
    if not db_foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    update_data = foilhole.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_foilhole, key, value)
    db.commit()
    db.refresh(db_foilhole)

    success = publish_foilhole_updated(
        uuid=db_foilhole.uuid,
        foilhole_id=db_foilhole.foilhole_id,
        gridsquare_uuid=db_foilhole.gridsquare_uuid,
        gridsquare_id=db_foilhole.gridsquare_id,
    )
    if not success:
        logger.error(f"Failed to publish foilhole updated event for UUID: {db_foilhole.uuid}")

    response_data = {
        "uuid": db_foilhole.uuid,
        "foilhole_id": db_foilhole.foilhole_id,
        "gridsquare_uuid": db_foilhole.gridsquare_uuid,
        "gridsquare_id": db_foilhole.gridsquare_id,
        "status": db_foilhole.status if db_foilhole.status is not None else FoilHoleStatus.NONE,
        "center_x": db_foilhole.center_x,
        "center_y": db_foilhole.center_y,
        "quality": db_foilhole.quality,
        "rotation": db_foilhole.rotation,
        "size_width": db_foilhole.size_width,
        "size_height": db_foilhole.size_height,
        "x_location": db_foilhole.x_location,
        "y_location": db_foilhole.y_location,
        "x_stage_position": db_foilhole.x_stage_position,
        "y_stage_position": db_foilhole.y_stage_position,
        "diameter": db_foilhole.diameter,
        "is_near_grid_bar": db_foilhole.is_near_grid_bar,
    }

    return FoilHoleResponse(**response_data)


@app.delete("/foilholes/{foilhole_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_foilhole(foilhole_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete a foil hole by publishing to RabbitMQ"""
    db_foilhole = db.query(FoilHole).filter(FoilHole.uuid == foilhole_uuid).first()
    if not db_foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    success = publish_foilhole_deleted(uuid=foilhole_uuid)
    if not success:
        logger.error(f"Failed to publish foil hole deleted event for ID: {foilhole_uuid}")

    return None


@app.get("/gridsquares/{gridsquare_uuid}/foilholes", response_model=list[FoilHoleResponse])
def get_gridsquare_foilholes(gridsquare_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all foil holes for a specific grid square"""
    return db.query(FoilHole).filter(FoilHole.gridsquare_id == gridsquare_uuid).all()


@app.post(
    "/gridsquares/{gridsquare_uuid}/foilholes", response_model=FoilHoleResponse, status_code=status.HTTP_201_CREATED
)
def create_gridsquare_foilhole(
    gridsquare_uuid: str, foilhole: FoilHoleCreateRequest, db: SqlAlchemySession = DB_DEPENDENCY
):
    """Create a new foil hole for a specific grid square"""
    foilhole_data = {"gridsquare_uuid": gridsquare_uuid, "status": FoilHoleStatus.NONE, **foilhole.model_dump()}

    db_foilhole = FoilHole(**foilhole_data)
    db.add(db_foilhole)
    db.commit()
    db.refresh(db_foilhole)

    success = publish_foilhole_created(
        uuid=db_foilhole.uuid,
        foilhole_id=db_foilhole.foilhole_id,
        gridsquare_uuid=db_foilhole.gridsquare_uuid,
        gridsquare_id=db_foilhole.gridsquare_id,
    )
    if not success:
        logger.error(f"Failed to publish foilhole created event for UUID: {db_foilhole.uuid}")

    response_data = {
        "gridsquare_uuid": gridsquare_uuid,
        "status": FoilHoleStatus.NONE.value,
        **foilhole.model_dump(),
    }

    # Make sure status is set correctly (the above might get overridden by model_dump)
    if "status" not in response_data or response_data["status"] is None:
        response_data["status"] = FoilHoleStatus.NONE.value

    return FoilHoleResponse(**response_data)


# ============ Micrograph CRUD Operations ============


@app.get("/micrographs", response_model=list[MicrographResponse])
def get_micrographs(db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all micrographs"""
    return db.query(Micrograph).all()


@app.get("/micrographs/{micrograph_uuid}", response_model=MicrographResponse)
def get_micrograph(micrograph_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get a single micrograph by ID"""
    micrograph = db.query(Micrograph).filter(Micrograph.uuid == micrograph_uuid).first()
    if not micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")
    return micrograph


@app.put("/micrographs/{micrograph_uuid}", response_model=MicrographResponse)
def update_micrograph(micrograph_uuid: str, micrograph: MicrographUpdateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Update a micrograph"""
    db_micrograph = db.query(Micrograph).filter(Micrograph.uuid == micrograph_uuid).first()
    if not db_micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")

    update_data = micrograph.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_micrograph, key, value)
    db.commit()
    db.refresh(db_micrograph)

    success = publish_micrograph_updated(
        uuid=db_micrograph.uuid,
        foilhole_uuid=db_micrograph.foilhole_uuid,
        foilhole_id=db_micrograph.foilhole_id,
        micrograph_id=db_micrograph.micrograph_id,
    )
    if not success:
        logger.error(f"Failed to publish micrograph updated event for UUID: {db_micrograph.uuid}")

    response_data = {
        "uuid": db_micrograph.uuid,
        "micrograph_id": db_micrograph.micrograph_id,
        "foilhole_uuid": db_micrograph.foilhole_uuid,
        "foilhole_id": db_micrograph.foilhole_id,
        "location_id": db_micrograph.location_id,
        "status": db_micrograph.status,
        "high_res_path": db_micrograph.high_res_path,
        "manifest_file": db_micrograph.manifest_file,
        "acquisition_datetime": db_micrograph.acquisition_datetime,
        "defocus": db_micrograph.defocus,
        "detector_name": db_micrograph.detector_name,
        "energy_filter": db_micrograph.energy_filter,
        "phase_plate": db_micrograph.phase_plate,
        "image_size_x": db_micrograph.image_size_x,
        "image_size_y": db_micrograph.image_size_y,
        "binning_x": db_micrograph.binning_x,
        "binning_y": db_micrograph.binning_y,
        "total_motion": db_micrograph.total_motion,
        "average_motion": db_micrograph.average_motion,
        "ctf_max_resolution_estimate": db_micrograph.ctf_max_resolution_estimate,
        "number_of_particles_selected": db_micrograph.number_of_particles_selected,
        "number_of_particles_rejected": db_micrograph.number_of_particles_rejected,
        "selection_distribution": db_micrograph.selection_distribution,
        "number_of_particles_picked": db_micrograph.number_of_particles_picked,
        "pick_distribution": db_micrograph.pick_distribution,
    }

    return MicrographResponse(**response_data)


@app.delete("/micrographs/{micrograph_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_micrograph(micrograph_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete a micrograph by publishing to RabbitMQ"""
    db_micrograph = db.query(Micrograph).filter(Micrograph.uuid == micrograph_uuid).first()
    if not db_micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")

    success = publish_micrograph_deleted(uuid=micrograph_uuid)
    if not success:
        logger.error(f"Failed to publish micrograph deleted event for ID: {micrograph_uuid}")

    return None


@app.get("/foilholes/{foilhole_uuid}/micrographs", response_model=list[MicrographResponse])
def get_foilhole_micrographs(foilhole_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all micrographs for a specific foil hole"""
    return db.query(Micrograph).filter(Micrograph.foilhole_uuid == foilhole_uuid).all()


@app.post(
    "/foilholes/{foilhole_uuid}/micrographs", response_model=MicrographResponse, status_code=status.HTTP_201_CREATED
)
def create_foilhole_micrograph(
    foilhole_uuid: str, micrograph: MicrographCreateRequest, db: SqlAlchemySession = DB_DEPENDENCY
):
    """Create a new micrograph for a specific foil hole"""
    micrograph_data = {
        "uuid": micrograph.uuid,
        "foilhole_uuid": foilhole_uuid,
        "status": MicrographStatus.NONE,
        **micrograph.model_dump(),
    }

    db_micrograph = Micrograph(**micrograph_data)
    db.add(db_micrograph)
    db.commit()
    db.refresh(db_micrograph)

    success = publish_micrograph_created(
        uuid=db_micrograph.uuid,
        foilhole_uuid=db_micrograph.foilhole_uuid,
        foilhole_id=db_micrograph.foilhole_id,
        micrograph_id=db_micrograph.micrograph_id,
    )
    if not success:
        logger.error(f"Failed to publish micrograph created event for UUID: {db_micrograph.uuid}")

    response_data = {
        "uuid": micrograph.uuid,
        "foilhole_uuid": foilhole_uuid,
        "foilhole_id": micrograph.foilhole_id,
        "status": MicrographStatus.NONE,
        **micrograph.model_dump(),
    }

    # Make sure status is set correctly (the above might get overridden by model_dump)
    if "status" not in response_data or response_data["status"] is None:
        response_data["status"] = MicrographStatus.NONE

    return MicrographResponse(**response_data)
