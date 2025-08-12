import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Request, status
<<<<<<< HEAD:src/smartem_backend/api_server.py
from sqlalchemy import and_, desc, or_, text
=======
from pydantic import BaseModel
from sqlalchemy import text
>>>>>>> 613abb5 (some quality prediction model related endpoints):src/smartem_api/server.py
from sqlalchemy.orm import Session as SqlAlchemySession
from sqlalchemy.orm import sessionmaker
from sse_starlette.sse import EventSourceResponse

from smartem_backend.agent_connection_manager import get_connection_manager
from smartem_backend.model.database import (
    Acquisition,
    AgentConnection,
    AgentInstruction,
    AgentInstructionAcknowledgement,
    AgentSession,
    Atlas,
    AtlasTile,
    AtlasTileGridSquarePosition,
    FoilHole,
    Grid,
    GridSquare,
    Micrograph,
    QualityPrediction,
    QualityPredictionModel,
    QualityPredictionModelParameter,
)
from smartem_backend.model.entity_status import (
    AcquisitionStatus,
    FoilHoleStatus,
    GridSquareStatus,
    GridStatus,
    MicrographStatus,
)
from smartem_backend.model.http_request import (
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
    GridSquarePositionRequest,
    GridSquareUpdateRequest,
    GridUpdateRequest,
    MicrographCreateRequest,
    MicrographUpdateRequest,
)
from smartem_backend.model.http_request import (
    AgentInstructionAcknowledgement as AgentInstructionAcknowledgementRequest,
)
from smartem_backend.model.http_response import (
    AcquisitionResponse,
    AgentInstructionAcknowledgementResponse,
    AtlasResponse,
    AtlasTileGridSquarePositionResponse,
    AtlasTileResponse,
    FoilHoleResponse,
    GridResponse,
    GridSquareResponse,
    LatentRepresentationResponse,
    MicrographResponse,
    QualityPredictionModelResponse,
    QualityPredictionResponse,
)
from smartem_backend.mq_publisher import (
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
    publish_grid_registered,
    publish_grid_updated,
    publish_gridsquare_created,
    publish_gridsquare_deleted,
    publish_gridsquare_lowmag_created,
    publish_gridsquare_lowmag_updated,
    publish_gridsquare_registered,
    publish_gridsquare_updated,
    publish_micrograph_created,
    publish_micrograph_deleted,
    publish_micrograph_updated,
)
from smartem_backend.utils import setup_postgres_connection, setup_rabbitmq
from smartem_common._version import __version__

# Initialize database connection (skip in documentation generation mode)
if os.getenv("SKIP_DB_INIT", "false").lower() != "true":
    db_engine = setup_postgres_connection()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
else:
    # Mock objects for documentation generation
    db_engine = None
    SessionLocal = None

# Set up RabbitMQ connections for health checks (skip in documentation generation mode)
if os.getenv("SKIP_DB_INIT", "false").lower() != "true":
    try:
        rmq_publisher, rmq_consumer = setup_rabbitmq()
    except Exception as e:
        # Logger is defined later, so we'll use print for early initialization errors
        print(f"Failed to initialize RabbitMQ connections for health checks: {e}")
        rmq_publisher, rmq_consumer = None, None
else:
    # Mock objects for documentation generation
    rmq_publisher, rmq_consumer = None, None


def get_db():
    if SessionLocal is None:
        # Mock for documentation generation
        yield None
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


# Create a dependency object at module level to avoid B008 linting errors
DB_DEPENDENCY = Depends(get_db)

# Get connection manager instance
connection_manager = get_connection_manager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("Starting SmartEM Backend services...")
    try:
        await connection_manager.start()
        logger.info("Connection manager started successfully")
    except Exception as e:
        logger.error(f"Failed to start connection manager: {e}")

    yield

    # Shutdown
    logger.info("Stopping SmartEM Backend services...")
    try:
        await connection_manager.stop()
        logger.info("Connection manager stopped successfully")
    except Exception as e:
        logger.error(f"Failed to stop connection manager: {e}")


app = FastAPI(
    title="SmartEM Decisions Backend API",
    description="API for accessing and managing electron microscopy data",
    version=__version__,
    redoc_url=None,
    lifespan=lifespan,
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


@app.post("/grids/{grid_uuid}/registered")
def grid_registered(grid_uuid: str) -> bool:
    """All squares on a grid have been registered at low mag"""
    success = publish_grid_registered(grid_uuid)
    if not success:
        logger.error(f"Failed to publish grid created event for UUID: {grid_uuid}")
    return success


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


@app.post(
    "/atlas-tiles/{tile_uuid}/gridsquares/{gridsquare_uuid}",
    response_model=AtlasTileGridSquarePositionResponse,
    status_code=status.HTTP_201_CREATED,
)
def link_atlas_tile_to_gridsquare(
    tile_uuid: str,
    gridsquare_uuid: str,
    gridsquare_position: GridSquarePositionRequest,
    db: SqlAlchemySession = DB_DEPENDENCY,
):
    """Connect a grid square to a tile with its position information"""
    position_data = gridsquare_position.model_dump()
    position_data["atlastile_uuid"] = tile_uuid
    position_data["gridsquare_uuid"] = gridsquare_uuid

    tile_square_link = AtlasTileGridSquarePosition(**position_data)
    db.add(tile_square_link)
    db.commit()

    response_data = {
        "atlastile_uuid": tile_square_link.atlastile_uuid,
        "gridsquare_uuid": tile_square_link.gridsquare_uuid,
        "center_x": tile_square_link.center_x,
        "center_y": tile_square_link.center_y,
        "size_width": tile_square_link.size_width,
        "size_height": tile_square_link.size_height,
    }
    return AtlasTileGridSquarePositionResponse(**response_data)


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
        if hasattr(db_gridsquare, key):
            setattr(db_gridsquare, key, value)
    db.commit()
    db.refresh(db_gridsquare)

    if gridsquare.lowmag:
        success = publish_gridsquare_lowmag_updated(
            uuid=db_gridsquare.uuid, grid_uuid=db_gridsquare.grid_uuid, gridsquare_id=db_gridsquare.gridsquare_id
        )
    else:
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

    if gridsquare.lowmag:
        success = publish_gridsquare_lowmag_created(
            uuid=db_gridsquare.uuid, grid_uuid=db_gridsquare.grid_uuid, gridsquare_id=db_gridsquare.gridsquare_id
        )
    else:
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


@app.post("/gridsquares/{gridsquare_uuid}/registered")
def gridsquare_registered(gridsquare_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY) -> bool:
    """All holes on a grid square have been registered at square mag"""
    db_gridsquare = db.query(GridSquare).filter(GridSquare.uuid == gridsquare_uuid).first()
    if not db_gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")
    db_gridsquare.status = GridSquareStatus.REGISTERED
    db.add(db_gridsquare)
    db.commit()
    success = publish_gridsquare_registered(gridsquare_uuid)
    if not success:
        logger.error(f"Failed to publish grid square created event for UUID: {gridsquare_uuid}")
    return success


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


# ============ Agent Communication Endpoints ============


@app.get("/agent/{agent_id}/session/{session_id}/instructions/stream")
async def stream_instructions(
    agent_id: str, session_id: str, db: SqlAlchemySession = DB_DEPENDENCY
) -> EventSourceResponse:
    """SSE endpoint for streaming instructions to agents for a specific session"""

    async def event_generator():
        connection_id = str(uuid.uuid4())

        try:
            # Validate session exists and belongs to agent
            try:
                session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
                if not session:
                    raise ValueError(f"Session {session_id} not found")
                if session.agent_id != agent_id:
                    raise ValueError(f"Session {session_id} does not belong to agent {agent_id}")
                if session.status != "active":
                    raise ValueError(f"Session {session_id} is not active (status: {session.status})")
            except ValueError as e:
                logger.error(f"Session validation failed for agent {agent_id}, session {session_id}: {e}")
                yield {
                    "event": "error",
                    "data": json.dumps({"type": "error", "error": "session_validation_failed", "message": str(e)}),
                }
                return

            # Create database connection record
            try:
                connection = AgentConnection(
                    connection_id=connection_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    connection_type="sse",
                    client_info={"connected_at": datetime.now().isoformat()},
                    status="active",
                    created_at=datetime.now(),
                    last_heartbeat_at=datetime.now(),
                )
                db.add(connection)
                db.commit()
                db.refresh(connection)
                logger.info(f"Created connection {connection_id} for agent {agent_id} in session {session_id}")
            except Exception as e:
                logger.error(f"Failed to create connection record: {e}")
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {
                            "type": "error",
                            "error": "connection_creation_failed",
                            "message": "Failed to register connection",
                        }
                    ),
                }
                return

            # Send initial connection acknowledgment
            yield {
                "event": "connection",
                "data": json.dumps(
                    {
                        "type": "connection",
                        "agent_id": agent_id,
                        "session_id": session_id,
                        "connection_id": connection_id,
                        "status": "connected",
                    }
                ),
            }

            heartbeat_counter = 0

            while True:
                # Send heartbeat every 30 seconds
                if heartbeat_counter % 6 == 0:  # Every 6th iteration (30 seconds)
                    # Update connection heartbeat
                    connection_obj = (
                        db.query(AgentConnection).filter(AgentConnection.connection_id == connection_id).first()
                    )
                    if connection_obj and connection_obj.status == "active":
                        connection_obj.last_heartbeat_at = datetime.now()
                        db.commit()
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps(
                            {
                                "type": "heartbeat",
                                "timestamp": datetime.now().isoformat(),
                                "connection_id": connection_id,
                            }
                        ),
                    }

                # Check for pending instructions
                try:
                    pending_instructions = (
                        db.query(AgentInstruction)
                        .filter(
                            and_(
                                AgentInstruction.session_id == session_id,
                                AgentInstruction.status == "pending",
                                or_(
                                    AgentInstruction.expires_at.is_(None), AgentInstruction.expires_at > datetime.now()
                                ),
                            )
                        )
                        .order_by(
                            AgentInstruction.priority.desc(),  # High priority first
                            AgentInstruction.sequence_number.asc(),  # Lower sequence numbers first
                            AgentInstruction.created_at.asc(),  # Older instructions first
                        )
                        .all()
                    )

                    for instruction in pending_instructions:
                        # Mark as sent
                        if instruction.status == "pending":
                            instruction.status = "sent"
                            instruction.sent_at = datetime.now()
                            db.commit()
                            db.refresh(instruction)

                        # Send instruction to agent
                        instruction_data = {
                            "type": "instruction",
                            "instruction_id": instruction.instruction_id,
                            "agent_id": agent_id,
                            "session_id": session_id,
                            "instruction_type": instruction.instruction_type,
                            "payload": instruction.payload,
                            "sequence_number": instruction.sequence_number,
                            "priority": instruction.priority,
                            "created_at": instruction.created_at.isoformat(),
                            "expires_at": instruction.expires_at.isoformat() if instruction.expires_at else None,
                            "metadata": instruction.instruction_metadata,
                        }

                        yield {"event": "instruction", "data": json.dumps(instruction_data)}

                        logger.info(f"Sent instruction {instruction.instruction_id} to agent {agent_id}")

                except Exception as e:
                    logger.error(f"Error processing instructions for session {session_id}: {e}")

                # Update session activity
                session.last_activity_at = datetime.now()
                db.commit()

                # Wait 5 seconds before next poll
                await asyncio.sleep(5)
                heartbeat_counter += 1

        except asyncio.CancelledError:
            logger.info(f"SSE connection closed for agent {agent_id}, session {session_id}")
            # Connection closed by client
            connection_obj = db.query(AgentConnection).filter(AgentConnection.connection_id == connection_id).first()
            if connection_obj:
                connection_obj.status = "closed"
                connection_obj.closed_at = datetime.now()
                connection_obj.close_reason = "client_disconnect"
                db.commit()
                logger.info(f"Closed connection {connection_id} with reason: client_disconnect")
            raise
        except Exception as e:
            logger.error(f"SSE stream error for agent {agent_id}: {e}")
            # Unexpected error
            connection_obj = db.query(AgentConnection).filter(AgentConnection.connection_id == connection_id).first()
            if connection_obj:
                connection_obj.status = "closed"
                connection_obj.closed_at = datetime.now()
                connection_obj.close_reason = f"error: {str(e)}"
                db.commit()
                logger.info(f"Closed connection {connection_id} with reason: error: {str(e)}")
            raise

    return EventSourceResponse(event_generator())


@app.post(
    "/agent/{agent_id}/session/{session_id}/instructions/{instruction_id}/ack",
    response_model=AgentInstructionAcknowledgementResponse,
)
async def acknowledge_instruction(
    agent_id: str,
    session_id: str,
    instruction_id: str,
    acknowledgement: AgentInstructionAcknowledgementRequest,
    db: SqlAlchemySession = DB_DEPENDENCY,
) -> AgentInstructionAcknowledgementResponse:
    """HTTP endpoint for instruction acknowledgements with database persistence"""

    try:
        # Validate session exists and belongs to agent
        session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        if session.agent_id != agent_id:
            raise HTTPException(status_code=403, detail=f"Session {session_id} does not belong to agent {agent_id}")
        if session.status != "active":
            raise HTTPException(status_code=400, detail=f"Session {session_id} is not active")

        # Validate agent has an active connection
        active_connections = (
            db.query(AgentConnection)
            .filter(and_(AgentConnection.agent_id == agent_id, AgentConnection.status == "active"))
            .order_by(desc(AgentConnection.last_heartbeat_at))
            .all()
        )
        if not active_connections:
            raise HTTPException(status_code=404, detail="Agent not connected")

        # Find matching connection for this session
        session_connection = next((conn for conn in active_connections if conn.session_id == session_id), None)
        if not session_connection:
            raise HTTPException(status_code=400, detail="No active connection for this session")

        # Get and validate instruction
        instruction = db.query(AgentInstruction).filter(AgentInstruction.instruction_id == instruction_id).first()
        if not instruction:
            raise HTTPException(status_code=404, detail="Instruction not found")

        if instruction.session_id != session_id:
            raise HTTPException(status_code=400, detail="Instruction does not belong to this session")

        if instruction.agent_id != agent_id:
            raise HTTPException(status_code=400, detail="Instruction does not belong to this agent")

        # Mark instruction as acknowledged in the database
        if instruction.status == "sent":
            instruction.status = "acknowledged"
            instruction.acknowledged_at = datetime.now()
            db.commit()
            db.refresh(instruction)
        else:
            raise HTTPException(status_code=400, detail="Instruction cannot be acknowledged (invalid status)")

        # Create acknowledgement record for audit trail
        ack_record = AgentInstructionAcknowledgement(
            instruction_id=instruction_id,
            agent_id=agent_id,
            session_id=session_id,
            status=acknowledgement.status,
            result=acknowledgement.result,
            error_message=acknowledgement.error_message,
            acknowledgement_metadata=getattr(acknowledgement, "metadata", None) or {},
            created_at=datetime.now(),
            processed_at=datetime.now() if acknowledgement.status in ["processed", "failed"] else None,
        )
        db.add(ack_record)
        db.commit()
        db.refresh(ack_record)

        logger.info(f"Created acknowledgement for instruction {instruction_id} with status {acknowledgement.status}")

        # Update session activity
        session.last_activity_at = datetime.now()
        db.commit()

        # Update connection heartbeat
        session_connection.last_heartbeat_at = datetime.now()
        db.commit()

        logger.info(
            f"Instruction {instruction_id} acknowledged by agent {agent_id} with status: {acknowledgement.status}"
        )

        return AgentInstructionAcknowledgementResponse(
            status="success",
            instruction_id=instruction_id,
            acknowledged_at=ack_record.created_at.isoformat(),
            agent_id=agent_id,
            session_id=session_id,
        )

    except ValueError as e:
        logger.error(f"Acknowledgement validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Acknowledgement processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@app.post("/agent/{agent_id}/session/{session_id}/heartbeat")
async def agent_heartbeat(agent_id: str, session_id: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """
    Agent heartbeat endpoint to update connection health status.

    Args:
        agent_id: The agent identifier
        session_id: The session identifier
        db: Database session

    Returns:
        Heartbeat response with status and timestamp
    """
    try:
        # Find active connection for this agent and session
        connection = (
            db.query(AgentConnection)
            .filter(
                and_(
                    AgentConnection.agent_id == agent_id,
                    AgentConnection.session_id == session_id,
                    AgentConnection.status == "active",
                )
            )
            .first()
        )

        if not connection:
            raise HTTPException(status_code=404, detail="No active connection found for agent and session")

        # Update heartbeat timestamp
        now = datetime.now()
        connection.last_heartbeat_at = now
        db.commit()

        # Also update session activity
        session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
        if session:
            session.last_activity_at = now
            db.commit()

        logger.info(f"Heartbeat received from agent {agent_id} session {session_id}")

        return {
            "status": "success",
            "agent_id": agent_id,
            "session_id": session_id,
            "heartbeat_timestamp": now.isoformat(),
            "connection_id": connection.connection_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Heartbeat processing error for agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from None


# Debug endpoints for development
@app.get("/debug/agent-connections")
async def get_active_connections(db: SqlAlchemySession = DB_DEPENDENCY):
    """Debug endpoint to view active agent connections"""
    # Get all active connections
    all_connections = (
        db.query(AgentConnection)
        .filter(AgentConnection.status == "active")
        .order_by(AgentConnection.last_heartbeat_at.desc())
        .all()
    )

    connections_data = []
    for conn in all_connections:
        connections_data.append(
            {
                "connection_id": conn.connection_id,
                "agent_id": conn.agent_id,
                "session_id": conn.session_id,
                "connection_type": conn.connection_type,
                "status": conn.status,
                "created_at": conn.created_at.isoformat(),
                "last_heartbeat_at": conn.last_heartbeat_at.isoformat(),
                "client_info": conn.client_info,
            }
        )

    return {"active_connections": connections_data, "total_count": len(connections_data)}


@app.get("/debug/session/{session_id}/instructions")
async def get_session_instructions(session_id: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Debug endpoint to view instructions for a session"""
    # Get all instructions for the session
    instructions = (
        db.query(AgentInstruction)
        .filter(AgentInstruction.session_id == session_id)
        .order_by(AgentInstruction.created_at.desc())
        .all()
    )

    instructions_data = []
    for instr in instructions:
        # Get acknowledgements for this instruction
        acknowledgements = (
            db.query(AgentInstructionAcknowledgement)
            .filter(AgentInstructionAcknowledgement.instruction_id == instr.instruction_id)
            .order_by(desc(AgentInstructionAcknowledgement.created_at))
            .all()
        )

        instructions_data.append(
            {
                "instruction_id": instr.instruction_id,
                "agent_id": instr.agent_id,
                "instruction_type": instr.instruction_type,
                "payload": instr.payload,
                "sequence_number": instr.sequence_number,
                "priority": instr.priority,
                "status": instr.status,
                "created_at": instr.created_at.isoformat(),
                "sent_at": instr.sent_at.isoformat() if instr.sent_at else None,
                "acknowledged_at": instr.acknowledged_at.isoformat() if instr.acknowledged_at else None,
                "expires_at": instr.expires_at.isoformat() if instr.expires_at else None,
                "metadata": instr.metadata,
                "acknowledgements_count": len(acknowledgements),
            }
        )

    # Get acknowledgement statistics
    from sqlalchemy import func

    ack_stats_query = (
        db.query(AgentInstructionAcknowledgement.status, func.count().label("count"))
        .filter(AgentInstructionAcknowledgement.session_id == session_id)
        .group_by(AgentInstructionAcknowledgement.status)
        .all()
    )
    ack_stats = dict(ack_stats_query)

    return {
        "session_id": session_id,
        "instructions": instructions_data,
        "total_instructions": len(instructions_data),
        "acknowledgement_statistics": ack_stats,
    }


# Additional debug endpoints for session and connection management
@app.get("/debug/sessions")
async def get_active_sessions(db: SqlAlchemySession = DB_DEPENDENCY):
    """Debug endpoint to view all active sessions"""
    sessions = (
        db.query(AgentSession)
        .filter(AgentSession.status == "active")
        .order_by(AgentSession.last_activity_at.desc())
        .all()
    )

    sessions_data = []
    for session in sessions:
        sessions_data.append(
            {
                "session_id": session.session_id,
                "agent_id": session.agent_id,
                "acquisition_uuid": session.acquisition_uuid,
                "name": session.name,
                "description": session.description,
                "status": session.status,
                "created_at": session.created_at.isoformat(),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "last_activity_at": session.last_activity_at.isoformat(),
                "experimental_parameters": session.experimental_parameters,
            }
        )

    return {"active_sessions": sessions_data, "total_count": len(sessions_data)}


@app.get("/debug/connection-stats")
async def get_connection_stats():
    """Get real-time connection and session statistics"""
    return connection_manager.get_connection_stats()


@app.post("/debug/sessions/create-managed")
async def create_managed_session(session_data: dict):
    """Create a session using the connection manager"""
    try:
        session_id = connection_manager.create_session(
            agent_id=session_data.get("agent_id", "test-agent"),
            acquisition_uuid=session_data.get("acquisition_uuid"),
            name=session_data.get("name"),
            description=session_data.get("description"),
            experimental_parameters=session_data.get("experimental_parameters", {}),
        )

        return {
            "session_id": session_id,
            "status": "created",
            "created_via": "connection_manager",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}") from e


@app.delete("/debug/sessions/{session_id}/close")
async def close_managed_session(session_id: str):
    """Close a session using the connection manager"""
    success = connection_manager.close_session(session_id)
    if success:
        return {
            "session_id": session_id,
            "status": "closed",
            "closed_via": "connection_manager",
            "timestamp": datetime.now().isoformat(),
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to close session")


@app.post("/debug/session/{session_id}/create-instruction")
async def create_test_instruction(session_id: str, instruction_data: dict, db: SqlAlchemySession = DB_DEPENDENCY):
    """Debug endpoint to create test instructions"""
    # Validate session exists
    session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Create instruction with provided data
    expires_at = None
    expires_in_minutes = instruction_data.get("expires_in_minutes", 60)
    if expires_in_minutes:
        expires_at = datetime.now() + timedelta(minutes=expires_in_minutes)

    instruction = AgentInstruction(
        instruction_id=str(uuid.uuid4()),
        session_id=session_id,
        agent_id=session.agent_id,
        instruction_type=instruction_data.get("instruction_type", "test.instruction"),
        payload=instruction_data.get("payload", {"test": True}),
        sequence_number=instruction_data.get("sequence_number"),
        priority=instruction_data.get("priority", "normal"),
        status="pending",
        created_at=datetime.now(),
        expires_at=expires_at,
        instruction_metadata=instruction_data.get("metadata", {}),
    )
    db.add(instruction)
    db.commit()
    db.refresh(instruction)

    logger.info(f"Created instruction {instruction.instruction_id} for session {session_id}")

    return {
        "instruction_id": instruction.instruction_id,
        "status": "created",
        "created_at": instruction.created_at.isoformat(),
    }


@app.post("/debug/sessions/create")
async def create_test_session(session_data: dict, db: SqlAlchemySession = DB_DEPENDENCY):
    """Debug endpoint to create test sessions"""
    # Validate acquisition exists if provided
    acquisition_uuid = session_data.get("acquisition_uuid")
    if acquisition_uuid:
        acquisition = db.query(Acquisition).filter(Acquisition.uuid == acquisition_uuid).first()
        if not acquisition:
            raise HTTPException(status_code=404, detail=f"Acquisition {acquisition_uuid} not found")

    # Create session with provided data
    session = AgentSession(
        session_id=session_data.get("session_id", str(uuid.uuid4())),
        agent_id=session_data.get("agent_id", "test-agent"),
        acquisition_uuid=acquisition_uuid,
        name=session_data.get("name", "Test Session"),
        description=session_data.get("description", "Debug session for testing"),
        experimental_parameters=session_data.get("experimental_parameters", {}),
        status="active",
        created_at=datetime.now(),
        last_activity_at=datetime.now(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(f"Created agent session {session.session_id} for agent {session.agent_id}")

    return {
        "session_id": session.session_id,
        "agent_id": session.agent_id,
        "status": "created",
        "created_at": session.created_at.isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("HTTP_API_PORT", "8000"))
    host = os.getenv("HTTP_API_HOST", "127.0.0.1")

    uvicorn.run("smartem_backend.api_server:app", host=host, port=port, reload=False, log_level="info")
# ============ Quality Prediction Model CRUD Operations ============


@app.get("/prediction_models", response_model=list[QualityPredictionModelResponse])
def get_prediction_models(db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all prediction model"""
    return db.query(QualityPredictionModel).all()


@app.get(
    "/prediction_model/{prediction_model_name}/grid/{grid_uuid}/prediction",
    response_model=list[QualityPredictionResponse],
)
def get_prediction_for_grid(prediction_model_name: str, grid_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    squares = db.query(GridSquare).filter(GridSquare.grid_uuid == grid_uuid).all()
    predictions = [
        db.query(QualityPrediction)
        .filter(QualityPrediction.gridsquare_uuid == gs.uuid)
        .filter(QualityPrediction.prediction_model_name == prediction_model_name)
        .order_by(QualityPrediction.timestamp.desc())
        .all()
        for gs in squares
    ]
    predictions = [p[0] for p in predictions if p]
    return predictions


@app.get(
    "/prediction_model/{prediction_model_name}/grid/{grid_uuid}/latent_representation",
    response_model=list[LatentRepresentationResponse],
)
def get_latent_rep(prediction_model_name: str, grid_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    model_parameters = (
        db.query(QualityPredictionModelParameter)
        .filter(QualityPredictionModelParameter.prediction_model_name == prediction_model_name)
        .filter(QualityPredictionModelParameter.grid_uuid == grid_uuid)
        .filter(QualityPredictionModelParameter.group.like("coordinates:%"))
        .order_by(QualityPredictionModelParameter.timestamp.desc())
        .all()
    )
    cluster_indices = (
        db.query(QualityPredictionModelParameter)
        .filter(QualityPredictionModelParameter.prediction_model_name == prediction_model_name)
        .filter(QualityPredictionModelParameter.grid_uuid == grid_uuid)
        .filter(QualityPredictionModelParameter.group == "cluster_indices")
        .order_by(QualityPredictionModelParameter.timestamp.desc())
        .all()
    )

    class LatentRep(BaseModel):
        x: float | None = None
        y: float | None = None
        index: int | None = None

        def complete(self):
            return all(a is not None for a in (self.x, self.y, self.index))

    rep = {p.uuid: LatentRep() for p in db.query(GridSquare).filter(GridSquare.grid_uuid == grid_uuid).all()}
    for p in cluster_indices + model_parameters:
        if p.group == "cluster_indices":
            square_uuid = p.key
            if rep[square_uuid].index is None:
                rep[square_uuid].index = p.value
            continue
        else:
            square_uuid = p.group.replace("coordinates:", "")
        if rep.get(square_uuid, LatentRep()).complete():
            break
        if p.key == "x":
            rep[square_uuid].x = p.value
        else:
            rep[square_uuid].y = p.value
    return [LatentRepresentationResponse(gridsquare_uuid=k, x=v.x, y=v.y, index=v.index) for k, v in rep.items() if v]
