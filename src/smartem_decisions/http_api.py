import json
import logging
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request, status
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

# Import event service for publishing to RabbitMQ
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

# from src.smartem_decisions.log_manager import logger # TODO integrate with FastAPI logger
from src.smartem_decisions.utils import setup_postgres_connection

db_engine = setup_postgres_connection()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create dependency object at module level to avoid B008 linting errors
DB_DEPENDENCY = Depends(get_db)


app = FastAPI(
    title="SmartEM Decisions API",
    description="API for accessing and managing electron microscopy data",
    version=__version__,
    redoc_url=None,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastapi")


# TODO remove in prod:
@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
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
    """Get API status information"""
    return {
        "status": "ok",
        "version": __version__,
        "timestamp": datetime.now().isoformat(),
        "service": "SmartEM Decisions API",
    }


@app.get("/health")
def get_health():
    """Health check endpoint"""
    # TODO: add database, rabbitmq connectivity checks here
    # try:
    #     # Simple db connectivity check
    #     db = SessionLocal()
    #     db.execute("SELECT 1")
    #     db.close()
    #     db_status = "ok"
    # except Exception:
    #     db_status = "error"

    # TODO consider masking internal implementation details for security reasons
    return {
        "status": "ok",
        "database": "ok",
        "event broker": "ok",
        "log aggregator": "ok",
        "timestamp": datetime.now().isoformat(),
    }


# ============ Acquisition CRUD Operations ============


@app.get("/acquisitions", response_model=list[AcquisitionResponse])
def get_acquisitions(db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all acquisitions"""
    return db.query(Acquisition).all()


@app.post("/acquisitions", response_model=AcquisitionResponse, status_code=status.HTTP_201_CREATED)
def create_acquisition(acquisition: AcquisitionCreateRequest):
    """Create a new acquisition by publishing to RabbitMQ"""
    acquisition_data = {
        "uuid": acquisition.uuid,
        "status": AcquisitionStatus.STARTED,
        **acquisition.model_dump(exclude={"uuid"}),
    }

    success = publish_acquisition_created(acquisition_data)
    if not success:
        logger.error(f"Failed to publish acquisition created event for ID: {acquisition.uuid}")

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
    """Update an acquisition by publishing to RabbitMQ"""
    # Check if acquisition exists
    db_acquisition = db.query(Acquisition).filter(Acquisition.uuid == acquisition_uuid).first()
    if not db_acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    # Prepare update data
    update_data = acquisition.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"uuid": acquisition_uuid, **update_data}

    # Publish the event to RabbitMQ
    success = publish_acquisition_updated(event_data)
    if not success:
        logger.error(f"Failed to publish acquisition updated event for ID: {acquisition_uuid}")

    # For immediate feedback, update the object in database, too.
    # This isn't ideal in a true event-driven architecture, but provides better UX
    for key, value in update_data.items():
        setattr(db_acquisition, key, value)

    db.commit()
    db.refresh(db_acquisition)
    return db_acquisition


@app.delete("/acquisitions/{acquisition_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_acquisition(acquisition_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete an acquisition by publishing to RabbitMQ"""
    # Check if acquisition exists
    db_acquisition = db.query(Acquisition).filter(Acquisition.uuid == acquisition_uuid).first()
    if not db_acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    success = publish_acquisition_deleted(acquisition_uuid)
    if not success:
        logger.error(f"Failed to publish acquisition deleted event for ID: {acquisition_uuid}")

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
    """Update a grid by publishing to RabbitMQ"""
    # Check if grid exists
    db_grid = db.query(Grid).filter(Grid.uuid == grid_uuid).first()
    if not db_grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    # Prepare update data
    update_data = grid.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"uuid": grid_uuid, **update_data}

    # Publish the event to RabbitMQ
    success = publish_grid_updated(event_data)
    if not success:
        logger.error(f"Failed to publish grid updated event for ID: {grid_uuid}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_grid, key, value)

    db.commit()
    db.refresh(db_grid)
    return db_grid


@app.delete("/grids/{grid_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grid(grid_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete a grid by publishing to RabbitMQ"""
    # Check if grid exists
    db_grid = db.query(Grid).filter(Grid.uuid == grid_uuid).first()
    if not db_grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    success = publish_grid_deleted(grid_uuid)
    if not success:
        logger.error(f"Failed to publish grid deleted event for ID: {grid_uuid}")

    return None


@app.get("/acquisitions/{acquisition_uuid}/grids", response_model=list[GridResponse])
def get_acquisition_grids(acquisition_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all grids for a specific acquisition"""
    return db.query(Grid).filter(Grid.acquisition_uuid == acquisition_uuid).all()


@app.post("/acquisitions/{acquisition_uuid}/grids", response_model=GridResponse, status_code=status.HTTP_201_CREATED)
def create_acquisition_grid(acquisition_uuid: str, grid: GridCreateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Create a new grid for a specific acquisition by publishing to RabbitMQ"""
    acquisition = db.query(Acquisition).filter(Acquisition.uuid == acquisition_uuid).first()
    if not acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    # Create grid data with acquisition_id
    grid_data = {"uuid": grid.uuid, "acquisition_uuid": acquisition_uuid, **grid.model_dump()}

    # Publish the event to RabbitMQ
    success = publish_grid_created(grid_data)
    if not success:
        logger.error(f"Failed to publish grid created event for ID: {grid.uuid}")

    # Create response data without needing to access the database
    response_data = {
        "uuid": grid.uuid,
        "acquisition_uuid": acquisition_uuid,
        "status": GridStatus.NONE,  # Set default status
        **grid.model_dump(),
    }

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
    """Update an atlas by publishing to RabbitMQ"""
    # Check if atlas exists
    db_atlas = db.query(Atlas).filter(Atlas.uuid == atlas_uuid).first()
    if not db_atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    # Prepare update data
    update_data = atlas.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"uuid": atlas_uuid, **update_data}

    # Publish the event to RabbitMQ
    success = publish_atlas_updated(event_data)
    if not success:
        logger.error(f"Failed to publish atlas updated event for ID: {atlas_uuid}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_atlas, key, value)

    db.commit()
    db.refresh(db_atlas)
    return db_atlas


@app.delete("/atlases/{atlas_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_atlas(atlas_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete an atlas by publishing to RabbitMQ"""
    # Check if atlas exists
    db_atlas = db.query(Atlas).filter(Atlas.uuid == atlas_uuid).first()
    if not db_atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    success = publish_atlas_deleted(atlas_uuid)
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
    """Create a new atlas for a grid by publishing to RabbitMQ"""
    # Check if grid exists
    grid = db.query(Grid).filter(Grid.uuid == grid_uuid).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    # Extract tiles for later
    tiles_data = None
    if atlas.tiles:
        tiles_data = [tile.model_dump() for tile in atlas.tiles]
        atlas_dict = atlas.model_dump(exclude={"tiles"})
    else:
        atlas_dict = atlas.model_dump()

    # Override grid_id
    atlas_dict["grid_uuid"] = grid_uuid

    # Create the atlas in DB to get an ID
    db_atlas = Atlas(**atlas_dict)
    db.add(db_atlas)
    db.commit()
    db.refresh(db_atlas)

    # Prepare data for event publishing
    atlas_event_data = {"uuid": db_atlas.uuid, **atlas_dict}

    # Publish the atlas created event
    success = publish_atlas_created(atlas_event_data)
    if not success:
        logger.error(f"Failed to publish atlas created event for ID: {db_atlas.uuid}")

    # If tiles were provided, create them too
    if tiles_data:
        for tile_data in tiles_data:
            # Add atlas_id to each tile
            tile_data["atlas_uuid"] = db_atlas.uuid

            # Create tile in DB to get an ID
            db_tile = AtlasTile(**tile_data)
            db.add(db_tile)
            db.commit()
            db.refresh(db_tile)

            # Publish tile created event
            tile_event_data = {"uuid": db_tile.id, **tile_data}
            tile_success = publish_atlas_tile_created(tile_event_data)
            if not tile_success:
                logger.error(f"Failed to publish atlas tile created event for ID: {db_tile.uuid}")

    return db_atlas


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
    """Update an atlas tile by publishing to RabbitMQ"""
    # Check if tile exists
    db_tile = db.query(AtlasTile).filter(AtlasTile.uuid == tile_uuid).first()
    if not db_tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")

    # Prepare update data
    update_data = tile.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"uuid": tile_uuid, **update_data}

    # Publish the event to RabbitMQ
    success = publish_atlas_tile_updated(event_data)
    if not success:
        logger.error(f"Failed to publish atlas tile updated event for ID: {tile_uuid}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_tile, key, value)

    db.commit()
    db.refresh(db_tile)
    return db_tile


@app.delete("/atlas-tiles/{tile_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_atlas_tile(tile_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete an atlas tile by publishing to RabbitMQ"""
    # Check if tile exists
    db_tile = db.query(AtlasTile).filter(AtlasTile.uuid == tile_uuid).first()
    if not db_tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")

    success = publish_atlas_tile_deleted(tile_uuid)
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
    """Create a new tile for a specific atlas by publishing to RabbitMQ"""
    # Verify atlas exists
    atlas = db.query(Atlas).filter(Atlas.uuid == atlas_uuid).first()
    if not atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    # Create tile data with atlas_id
    tile_data = tile.model_dump()
    tile_data["atlas_id"] = atlas_uuid

    # Create tile in DB to get an ID
    db_tile = AtlasTile(**tile_data)
    db.add(db_tile)
    db.commit()
    db.refresh(db_tile)

    # Prepare data for event publishing
    tile_event_data = {"uuid": db_tile.uuid, **tile_data}

    # Publish the event to RabbitMQ
    success = publish_atlas_tile_created(tile_event_data)
    if not success:
        logger.error(f"Failed to publish atlas tile created event for ID: {db_tile.uuid}")

    return db_tile


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
    """Update a grid square by publishing to RabbitMQ"""
    # Check if grid square exists
    db_gridsquare = db.query(GridSquare).filter(GridSquare.uuid == gridsquare_uuid).first()
    if not db_gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    # Prepare update data
    update_data = gridsquare.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"uuid": gridsquare_uuid, **update_data}

    # Publish the event to RabbitMQ
    success = publish_gridsquare_updated(event_data)
    if not success:
        logger.error(f"Failed to publish grid square updated event for ID: {gridsquare_uuid}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_gridsquare, key, value)

    db.commit()
    db.refresh(db_gridsquare)
    return db_gridsquare


@app.delete("/gridsquares/{gridsquare_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gridsquare(gridsquare_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete a grid square by publishing to RabbitMQ"""
    # Check if grid square exists
    db_gridsquare = db.query(GridSquare).filter(GridSquare.uuid == gridsquare_uuid).first()
    if not db_gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    success = publish_gridsquare_deleted(gridsquare_uuid)
    if not success:
        logger.error(f"Failed to publish grid square deleted event for ID: {gridsquare_uuid}")

    return None


@app.get("/grids/{grid_uuid}/gridsquares", response_model=list[GridSquareResponse])
def get_grid_gridsquares(grid_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Get all grid squares for a specific grid"""
    return db.query(GridSquare).filter(GridSquare.grid_uuid == grid_uuid).all()


@app.post("/grids/{grid_uuid}/gridsquares", response_model=GridSquareResponse, status_code=status.HTTP_201_CREATED)
def create_grid_gridsquare(grid_uuid: str, gridsquare: GridSquareCreateRequest, db: SqlAlchemySession = DB_DEPENDENCY):
    """Create a new grid square for a specific grid by publishing to RabbitMQ"""
    grid = db.query(Grid).filter(Grid.uuid == grid_uuid).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    gridsquare_data = {"uuid": gridsquare.uuid, "grid_id": grid_uuid, **gridsquare.model_dump()}

    success = publish_gridsquare_created(gridsquare_data)
    if not success:
        logger.error(f"Failed to publish grid square created event for ID: {gridsquare.uuid}")

    # Create response data without needing to access the database
    response_data = {
        "uuid": gridsquare.uuid,  # TODO test if needed, is it not set anyway by `**gridsquare.model_dump()`?
        "grid_uuid": grid_uuid,
        "status": GridSquareStatus.NONE,  # TODO techdebt, should be setting default status on edge
        # when instantiating data entity and certainly NOT HERE!!
        **gridsquare.model_dump(),
    }

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
    """Update a foil hole by publishing to RabbitMQ"""
    # TODO this isn't tested

    # Check if foil hole exists
    db_foilhole = db.query(FoilHole).filter(FoilHole.uuid == foilhole_uuid).first()
    if not db_foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    # Prepare update data
    update_data = foilhole.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"uuid": foilhole_uuid, **update_data}

    # Publish the event to RabbitMQ
    success = publish_foilhole_updated(event_data)
    if not success:
        logger.error(f"Failed to publish foil hole updated event for ID: {foilhole_uuid}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_foilhole, key, value)

    db.commit()
    db.refresh(db_foilhole)
    return db_foilhole


@app.delete("/foilholes/{foilhole_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_foilhole(foilhole_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete a foil hole by publishing to RabbitMQ"""
    db_foilhole = db.query(FoilHole).filter(FoilHole.uuid == foilhole_uuid).first()
    if not db_foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    success = publish_foilhole_deleted(foilhole_uuid)
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
    """Create a new foil hole for a specific grid square by publishing to RabbitMQ"""
    gridsquare = db.query(GridSquare).filter(GridSquare.uuid == gridsquare_uuid).first()
    if not gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    foilhole_data = {
        "gridsquare_uuid": gridsquare_uuid,  # The synthetic UUID for relationship
        **foilhole.model_dump(),
    }

    success = publish_foilhole_created(foilhole_data)
    if not success:
        logger.error(f"Failed to publish foil hole created event for foilhole: {foilhole.uuid}")

    # Create response data without needing to access the database
    response_data = {
        "gridsquare_uuid": gridsquare_uuid,
        "status": FoilHoleStatus.NONE.value,  # TODO techdebt, should be setting default status on edge
        # when instantiating data entity and certainly NOT HERE!!
        **foilhole.model_dump(),
    }

    # Make sure status is set correctly (the above might get overridden by model_dump)
    # TODO: remove hacky-hacky when techdebt above addressed
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
    """Update a micrograph by publishing to RabbitMQ"""
    # Check if micrograph exists
    db_micrograph = db.query(Micrograph).filter(Micrograph.uuid == micrograph_uuid).first()
    if not db_micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")

    # Prepare update data
    update_data = micrograph.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"id": micrograph_uuid, **update_data}

    # Publish the event to RabbitMQ
    success = publish_micrograph_updated(event_data)
    if not success:
        logger.error(f"Failed to publish micrograph updated event for ID: {micrograph_uuid}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_micrograph, key, value)

    db.commit()
    db.refresh(db_micrograph)
    return db_micrograph


@app.delete("/micrographs/{micrograph_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_micrograph(micrograph_uuid: str, db: SqlAlchemySession = DB_DEPENDENCY):
    """Delete a micrograph by publishing to RabbitMQ"""
    # Check if micrograph exists
    db_micrograph = db.query(Micrograph).filter(Micrograph.uuid == micrograph_uuid).first()
    if not db_micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")

    success = publish_micrograph_deleted(micrograph_uuid)
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
    """Create a new micrograph for a specific foil hole by publishing to RabbitMQ"""
    # Check if foil hole exists
    foilhole = db.query(FoilHole).filter(FoilHole.uuid == foilhole_uuid).first()
    if not foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    # Create micrograph data with foil hole ID
    micrograph_data = {
        "uuid": micrograph.uuid,
        "foilhole_uuid": foilhole_uuid,
        "status": MicrographStatus.NONE,
        **micrograph.model_dump(),
    }

    # Publish the event to RabbitMQ
    success = publish_micrograph_created(micrograph_data)
    if not success:
        logger.error(
            f"Failed to publish micrograph created event for natural ID: {micrograph.uuid}"
        )  # TODO respond with 500?

    # Create response data without needing to access the database
    response_data = {
        "uuid": micrograph.uuid,
        "foilhole_uuid": foilhole_uuid,
        "foilhole_id": micrograph.foilhole_id,
        "micrograph_id": micrograph.uuid,
        "status": MicrographStatus.NONE,  # Always provide a valid enum value
        **micrograph.model_dump(exclude={"status", "foilhole_uuid"}),  # Avoid duplicates
    }

    return MicrographResponse(**response_data)
