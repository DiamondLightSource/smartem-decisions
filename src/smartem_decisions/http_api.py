from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import sessionmaker, Session as SqlAlchemySession

from src.smartem_decisions._version import __version__
from src.smartem_decisions.log_manager import logger
from src.smartem_decisions.utils import setup_postgres_connection
from src.smartem_decisions.model.http_request import (
    AcquisitionCreateRequest,
    AcquisitionUpdateRequest,
    AtlasCreateRequest,
    AtlasUpdateRequest,
    AtlasTileCreateRequest,
    AtlasTileUpdateRequest,
    GridCreateRequest,
    GridUpdateRequest,
    GridSquareCreateRequest,
    GridSquareUpdateRequest,
    FoilHoleCreateRequest,
    FoilHoleUpdateRequest,
    MicrographCreateRequest,
    MicrographUpdateRequest,
)
from src.smartem_decisions.model.http_response import (
    AcquisitionResponse,
    AtlasResponse,
    AtlasTileResponse,
    GridResponse,
    GridSquareResponse,
    FoilHoleResponse,
    MicrographResponse,
)
from src.smartem_decisions.model.database import (
    Acquisition,
    Atlas,
    AtlasTile,
    Grid,
    GridSquare,
    FoilHole,
    Micrograph,
)

# Import event service for publishing to RabbitMQ
from src.smartem_decisions.mq_publisher import (
    publish_acquisition_created,
    publish_acquisition_updated,
    publish_acquisition_deleted,
    publish_atlas_created,
    publish_atlas_updated,
    publish_atlas_deleted,
    publish_atlas_tile_created,
    publish_atlas_tile_updated,
    publish_atlas_tile_deleted,
    publish_grid_created,
    publish_grid_updated,
    publish_grid_deleted,
    publish_gridsquare_created,
    publish_gridsquare_updated,
    publish_gridsquare_deleted,
    publish_foilhole_created,
    publish_foilhole_updated,
    publish_foilhole_deleted,
    publish_micrograph_created,
    publish_micrograph_updated,
    publish_micrograph_deleted,
)

db_engine = setup_postgres_connection()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI(
    title="SmartEM Decisions API",
    description="API for accessing and managing electron microscopy data",
    version=__version__,
    redoc_url=None,
)
# TODO app.logger is probably built into FastAPI, but we use our own logger from log_manager,
#   see if these two can be combined

# ============ Acquisition CRUD Operations ============


@app.get("/acquisitions", response_model=list[AcquisitionResponse])
def get_acquisitions(db: SqlAlchemySession = Depends(get_db)):
    """Get all acquisitions"""
    return db.query(Acquisition).all()


@app.post("/acquisitions", response_model=AcquisitionResponse, status_code=status.HTTP_201_CREATED)
def create_acquisition(acquisition: AcquisitionCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new acquisition by publishing to RabbitMQ"""
    # Create a temporary entry to get an ID and return to the user
    # This allows the client to have immediate feedback and an ID to reference
    db_acquisition = Acquisition(**acquisition.model_dump())
    db.add(db_acquisition)
    db.commit()
    db.refresh(db_acquisition)

    # Prepare data for event publishing
    acquisition_data = {"id": db_acquisition.id, **acquisition.model_dump()}

    # Publish the event to RabbitMQ
    success = publish_acquisition_created(acquisition_data)
    if not success:
        # If the publishing fails, we might want to roll back or log the issue
        # For now, we'll just return the entry we created and log the issue
        logger.error(f"Failed to publish acquisition created event for ID: {db_acquisition.id}")

    return db_acquisition


@app.get("/acquisitions/{acquisition_id}", response_model=AcquisitionResponse)
def get_acquisition(acquisition_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get a single acquisition by ID"""
    acquisition = db.query(Acquisition).filter(Acquisition.id == acquisition_id).first()
    if not acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")
    return acquisition


@app.put("/acquisitions/{acquisition_id}", response_model=AcquisitionResponse)
def update_acquisition(
    acquisition_id: int, acquisition: AcquisitionUpdateRequest, db: SqlAlchemySession = Depends(get_db)
):
    """Update an acquisition by publishing to RabbitMQ"""
    # Check if acquisition exists
    db_acquisition = db.query(Acquisition).filter(Acquisition.id == acquisition_id).first()
    if not db_acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    # Prepare update data
    update_data = acquisition.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"id": acquisition_id, **update_data}

    # Publish the event to RabbitMQ
    success = publish_acquisition_updated(event_data)
    if not success:
        logger.error(f"Failed to publish acquisition updated event for ID: {acquisition_id}")

    # For immediate feedback, update the object in database, too.
    # This isn't ideal in a true event-driven architecture, but provides better UX
    for key, value in update_data.items():
        setattr(db_acquisition, key, value)

    db.commit()
    db.refresh(db_acquisition)
    return db_acquisition


@app.delete("/acquisitions/{acquisition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_acquisition(acquisition_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Delete an acquisition by publishing to RabbitMQ"""
    # Check if acquisition exists
    db_acquisition = db.query(Acquisition).filter(Acquisition.id == acquisition_id).first()
    if not db_acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    # Publish the deletion event to RabbitMQ
    success = publish_acquisition_deleted(acquisition_id)
    if not success:
        logger.error(f"Failed to publish acquisition deleted event for ID: {acquisition_id}")

    # For immediate feedback, also delete from the database
    db.delete(db_acquisition)
    db.commit()

    return None


# ============ Atlas CRUD Operations ============


@app.get("/atlases", response_model=list[AtlasResponse])
def get_atlases(db: SqlAlchemySession = Depends(get_db)):
    """Get all atlases"""
    return db.query(Atlas).all()


@app.post("/atlases", response_model=AtlasResponse, status_code=status.HTTP_201_CREATED)
def create_atlas(atlas: AtlasCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new atlas by publishing to RabbitMQ"""
    # Extract tiles for later
    tiles_data = None
    if atlas.tiles:
        tiles_data = [tile.model_dump() for tile in atlas.tiles]
        atlas_dict = atlas.model_dump(exclude={"tiles"})
    else:
        atlas_dict = atlas.model_dump()

    # Create the atlas in DB to get an ID
    db_atlas = Atlas(**atlas_dict)
    db.add(db_atlas)
    db.commit()
    db.refresh(db_atlas)

    # Prepare data for event publishing
    atlas_event_data = {"id": db_atlas.id, **atlas_dict}

    # Publish the atlas created event
    success = publish_atlas_created(atlas_event_data)
    if not success:
        logger.error(f"Failed to publish atlas created event for ID: {db_atlas.id}")

    # If tiles were provided, create them too
    if tiles_data:
        for tile_data in tiles_data:
            # Add atlas_id to each tile
            tile_data["atlas_id"] = db_atlas.id

            # Create tile in DB to get an ID
            db_tile = AtlasTile(**tile_data)
            db.add(db_tile)
            db.commit()
            db.refresh(db_tile)

            # Publish tile created event
            tile_event_data = {"id": db_tile.id, **tile_data}
            tile_success = publish_atlas_tile_created(tile_event_data)
            if not tile_success:
                logger.error(f"Failed to publish atlas tile created event for ID: {db_tile.id}")

    return db_atlas


@app.get("/atlases/{atlas_id}", response_model=AtlasResponse)
def get_atlas(atlas_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get a single atlas by ID"""
    atlas = db.query(Atlas).filter(Atlas.id == atlas_id).first()
    if not atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")
    return atlas


@app.put("/atlases/{atlas_id}", response_model=AtlasResponse)
def update_atlas(atlas_id: int, atlas: AtlasUpdateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Update an atlas by publishing to RabbitMQ"""
    # Check if atlas exists
    db_atlas = db.query(Atlas).filter(Atlas.id == atlas_id).first()
    if not db_atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    # Prepare update data
    update_data = atlas.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"id": atlas_id, **update_data}

    # Publish the event to RabbitMQ
    success = publish_atlas_updated(event_data)
    if not success:
        logger.error(f"Failed to publish atlas updated event for ID: {atlas_id}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_atlas, key, value)

    db.commit()
    db.refresh(db_atlas)
    return db_atlas


@app.delete("/atlases/{atlas_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_atlas(atlas_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Delete an atlas by publishing to RabbitMQ"""
    # Check if atlas exists
    db_atlas = db.query(Atlas).filter(Atlas.id == atlas_id).first()
    if not db_atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    # Publish the deletion event to RabbitMQ
    success = publish_atlas_deleted(atlas_id)
    if not success:
        logger.error(f"Failed to publish atlas deleted event for ID: {atlas_id}")

    # For immediate feedback, also delete from the database
    db.delete(db_atlas)
    db.commit()

    return None


@app.get("/grids/{grid_id}/atlas", response_model=AtlasResponse)
def get_grid_atlas(grid_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get the atlas for a specific grid"""
    atlas = db.query(Atlas).filter(Atlas.grid_id == grid_id).first()
    if not atlas:
        raise HTTPException(status_code=404, detail="Atlas not found for this grid")
    return atlas


@app.post("/grids/{grid_id}/atlas", response_model=AtlasResponse, status_code=status.HTTP_201_CREATED)
def create_grid_atlas(grid_id: int, atlas: AtlasCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new atlas for a grid by publishing to RabbitMQ"""
    # Check if grid exists
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
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
    atlas_dict["grid_id"] = grid_id

    # Create the atlas in DB to get an ID
    db_atlas = Atlas(**atlas_dict)
    db.add(db_atlas)
    db.commit()
    db.refresh(db_atlas)

    # Prepare data for event publishing
    atlas_event_data = {"id": db_atlas.id, **atlas_dict}

    # Publish the atlas created event
    success = publish_atlas_created(atlas_event_data)
    if not success:
        logger.error(f"Failed to publish atlas created event for ID: {db_atlas.id}")

    # If tiles were provided, create them too
    if tiles_data:
        for tile_data in tiles_data:
            # Add atlas_id to each tile
            tile_data["atlas_id"] = db_atlas.id

            # Create tile in DB to get an ID
            db_tile = AtlasTile(**tile_data)
            db.add(db_tile)
            db.commit()
            db.refresh(db_tile)

            # Publish tile created event
            tile_event_data = {"id": db_tile.id, **tile_data}
            tile_success = publish_atlas_tile_created(tile_event_data)
            if not tile_success:
                logger.error(f"Failed to publish atlas tile created event for ID: {db_tile.id}")

    return db_atlas


# ============ Atlas Tile CRUD Operations ============


@app.get("/atlas-tiles", response_model=list[AtlasTileResponse])
def get_atlas_tiles(db: SqlAlchemySession = Depends(get_db)):
    """Get all atlas tiles"""
    return db.query(AtlasTile).all()


@app.post("/atlas-tiles", response_model=AtlasTileResponse, status_code=status.HTTP_201_CREATED)
def create_atlas_tile(tile: AtlasTileCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new atlas tile by publishing to RabbitMQ"""
    # Create tile in DB to get an ID
    db_tile = AtlasTile(**tile.model_dump())
    db.add(db_tile)
    db.commit()
    db.refresh(db_tile)

    # Prepare data for event publishing
    tile_event_data = {"id": db_tile.id, **tile.model_dump()}

    # Publish the event to RabbitMQ
    success = publish_atlas_tile_created(tile_event_data)
    if not success:
        logger.error(f"Failed to publish atlas tile created event for ID: {db_tile.id}")

    return db_tile


@app.get("/atlas-tiles/{tile_id}", response_model=AtlasTileResponse)
def get_atlas_tile(tile_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get a single atlas tile by ID"""
    tile = db.query(AtlasTile).filter(AtlasTile.id == tile_id).first()
    if not tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")
    return tile


@app.put("/atlas-tiles/{tile_id}", response_model=AtlasTileResponse)
def update_atlas_tile(tile_id: int, tile: AtlasTileUpdateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Update an atlas tile by publishing to RabbitMQ"""
    # Check if tile exists
    db_tile = db.query(AtlasTile).filter(AtlasTile.id == tile_id).first()
    if not db_tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")

    # Prepare update data
    update_data = tile.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"id": tile_id, **update_data}

    # Publish the event to RabbitMQ
    success = publish_atlas_tile_updated(event_data)
    if not success:
        logger.error(f"Failed to publish atlas tile updated event for ID: {tile_id}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_tile, key, value)

    db.commit()
    db.refresh(db_tile)
    return db_tile


@app.delete("/atlas-tiles/{tile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_atlas_tile(tile_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Delete an atlas tile by publishing to RabbitMQ"""
    # Check if tile exists
    db_tile = db.query(AtlasTile).filter(AtlasTile.id == tile_id).first()
    if not db_tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")

    # Publish the deletion event to RabbitMQ
    success = publish_atlas_tile_deleted(tile_id)
    if not success:
        logger.error(f"Failed to publish atlas tile deleted event for ID: {tile_id}")

    # For immediate feedback, also delete from the database
    db.delete(db_tile)
    db.commit()

    return None


@app.get("/atlases/{atlas_id}/tiles", response_model=list[AtlasTileResponse])
def get_atlas_tiles_by_atlas(atlas_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get all tiles for a specific atlas"""
    tiles = db.query(AtlasTile).filter(AtlasTile.atlas_id == atlas_id).all()
    return tiles


@app.post("/atlases/{atlas_id}/tiles", response_model=AtlasTileResponse, status_code=status.HTTP_201_CREATED)
def create_atlas_tile_for_atlas(atlas_id: int, tile: AtlasTileCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new tile for a specific atlas by publishing to RabbitMQ"""
    # Verify atlas exists
    atlas = db.query(Atlas).filter(Atlas.id == atlas_id).first()
    if not atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    # Create tile data with atlas_id
    tile_data = tile.model_dump()
    tile_data["atlas_id"] = atlas_id

    # Create tile in DB to get an ID
    db_tile = AtlasTile(**tile_data)
    db.add(db_tile)
    db.commit()
    db.refresh(db_tile)

    # Prepare data for event publishing
    tile_event_data = {"id": db_tile.id, **tile_data}

    # Publish the event to RabbitMQ
    success = publish_atlas_tile_created(tile_event_data)
    if not success:
        logger.error(f"Failed to publish atlas tile created event for ID: {db_tile.id}")

    return db_tile


# ============ Grid CRUD Operations ============


@app.get("/grids", response_model=list[GridResponse])
def get_grids(db: SqlAlchemySession = Depends(get_db)):
    """Get all grids"""
    return db.query(Grid).all()


@app.post("/grids", response_model=GridResponse, status_code=status.HTTP_201_CREATED)
def create_grid(grid: GridCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new grid by publishing to RabbitMQ"""
    # Create grid in DB to get an ID
    db_grid = Grid(**grid.model_dump())
    db.add(db_grid)
    db.commit()
    db.refresh(db_grid)

    # Prepare data for event publishing
    grid_event_data = {"id": db_grid.id, **grid.model_dump()}

    # Publish the event to RabbitMQ
    success = publish_grid_created(grid_event_data)
    if not success:
        logger.error(f"Failed to publish grid created event for ID: {db_grid.id}")

    return db_grid


@app.get("/grids/{grid_id}", response_model=GridResponse)
def get_grid(grid_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get a single grid by ID"""
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")
    return grid


@app.put("/grids/{grid_id}", response_model=GridResponse)
def update_grid(grid_id: int, grid: GridUpdateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Update a grid by publishing to RabbitMQ"""
    # Check if grid exists
    db_grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not db_grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    # Prepare update data
    update_data = grid.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"id": grid_id, **update_data}

    # Publish the event to RabbitMQ
    success = publish_grid_updated(event_data)
    if not success:
        logger.error(f"Failed to publish grid updated event for ID: {grid_id}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_grid, key, value)

    db.commit()
    db.refresh(db_grid)
    return db_grid


@app.delete("/grids/{grid_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grid(grid_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Delete a grid by publishing to RabbitMQ"""
    # Check if grid exists
    db_grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not db_grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    # Publish the deletion event to RabbitMQ
    success = publish_grid_deleted(grid_id)
    if not success:
        logger.error(f"Failed to publish grid deleted event for ID: {grid_id}")

    # For immediate feedback, also delete from the database
    db.delete(db_grid)
    db.commit()

    return None


@app.get("/acquisitions/{acquisition_id}/grids", response_model=list[GridResponse])
def get_acquisition_grids(acquisition_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get all grids for a specific acquisition"""
    return db.query(Grid).filter(Grid.acquisition_id == acquisition_id).all()


@app.post("/acquisitions/{acquisition_id}/grids", response_model=GridResponse, status_code=status.HTTP_201_CREATED)
def create_acquisition_grid(acquisition_id: int, grid: GridCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new grid for a specific acquisition by publishing to RabbitMQ"""
    # Check if acquisition exists
    acquisition = db.query(Acquisition).filter(Acquisition.id == acquisition_id).first()
    if not acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    # Create grid data with acquisition_id
    grid_data = grid.model_dump()
    grid_data["acquisition_id"] = acquisition_id

    # Create grid in DB to get an ID
    db_grid = Grid(**grid_data)
    db.add(db_grid)
    db.commit()
    db.refresh(db_grid)

    # Prepare data for event publishing
    grid_event_data = {"id": db_grid.id, **grid_data}

    # Publish the event to RabbitMQ
    success = publish_grid_created(grid_event_data)
    if not success:
        logger.error(f"Failed to publish grid created event for ID: {db_grid.id}")

    return db_grid


# ============ GridSquare CRUD Operations ============


@app.get("/gridsquares", response_model=list[GridSquareResponse])
def get_gridsquares(db: SqlAlchemySession = Depends(get_db)):
    """Get all grid squares"""
    return db.query(GridSquare).all()


@app.post("/gridsquares", response_model=GridSquareResponse, status_code=status.HTTP_201_CREATED)
def create_gridsquare(gridsquare: GridSquareCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new grid square by publishing to RabbitMQ"""
    # Create grid square in DB to get an ID
    db_gridsquare = GridSquare(**gridsquare.model_dump())
    db.add(db_gridsquare)
    db.commit()
    db.refresh(db_gridsquare)

    # Prepare data for event publishing
    gridsquare_event_data = {"id": db_gridsquare.id, **gridsquare.model_dump()}

    # Publish the event to RabbitMQ
    success = publish_gridsquare_created(gridsquare_event_data)
    if not success:
        logger.error(f"Failed to publish grid square created event for ID: {db_gridsquare.id}")

    return db_gridsquare


@app.get("/gridsquares/{gridsquare_id}", response_model=GridSquareResponse)
def get_gridsquare(gridsquare_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get a single grid square by ID"""
    gridsquare = db.query(GridSquare).filter(GridSquare.id == gridsquare_id).first()
    if not gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")
    return gridsquare


@app.put("/gridsquares/{gridsquare_id}", response_model=GridSquareResponse)
def update_gridsquare(gridsquare_id: int, gridsquare: GridSquareUpdateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Update a grid square by publishing to RabbitMQ"""
    # Check if grid square exists
    db_gridsquare = db.query(GridSquare).filter(GridSquare.id == gridsquare_id).first()
    if not db_gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    # Prepare update data
    update_data = gridsquare.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"id": gridsquare_id, **update_data}

    # Publish the event to RabbitMQ
    success = publish_gridsquare_updated(event_data)
    if not success:
        logger.error(f"Failed to publish grid square updated event for ID: {gridsquare_id}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_gridsquare, key, value)

    db.commit()
    db.refresh(db_gridsquare)
    return db_gridsquare


@app.delete("/gridsquares/{gridsquare_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gridsquare(gridsquare_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Delete a grid square by publishing to RabbitMQ"""
    # Check if grid square exists
    db_gridsquare = db.query(GridSquare).filter(GridSquare.id == gridsquare_id).first()
    if not db_gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    # Publish the deletion event to RabbitMQ
    success = publish_gridsquare_deleted(gridsquare_id)
    if not success:
        logger.error(f"Failed to publish grid square deleted event for ID: {gridsquare_id}")

    # For immediate feedback, also delete from the database
    db.delete(db_gridsquare)
    db.commit()

    return None


@app.get("/grids/{grid_id}/gridsquares", response_model=list[GridSquareResponse])
def get_grid_gridsquares(grid_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get all grid squares for a specific grid"""
    return db.query(GridSquare).filter(GridSquare.grid_id == grid_id).all()


@app.post("/grids/{grid_id}/gridsquares", response_model=GridSquareResponse, status_code=status.HTTP_201_CREATED)
def create_grid_gridsquare(grid_id: int, gridsquare: GridSquareCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new grid square for a specific grid by publishing to RabbitMQ"""
    # Check if grid exists
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    # Create grid square data with grid_id
    gridsquare_data = gridsquare.model_dump()
    gridsquare_data["grid_id"] = grid_id

    # Create grid square in DB to get an ID
    db_gridsquare = GridSquare(**gridsquare_data)
    db.add(db_gridsquare)
    db.commit()
    db.refresh(db_gridsquare)

    # Prepare data for event publishing
    gridsquare_event_data = {"id": db_gridsquare.id, **gridsquare_data}

    # Publish the event to RabbitMQ
    success = publish_gridsquare_created(gridsquare_event_data)
    if not success:
        logger.error(f"Failed to publish grid square created event for ID: {db_gridsquare.id}")

    return db_gridsquare


# ============ FoilHole CRUD Operations ============


@app.get("/foilholes", response_model=list[FoilHoleResponse])
def get_foilholes(db: SqlAlchemySession = Depends(get_db)):
    """Get all foil holes"""
    return db.query(FoilHole).all()


@app.post("/foilholes", response_model=FoilHoleResponse, status_code=status.HTTP_201_CREATED)
def create_foilhole(foilhole: FoilHoleCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new foil hole by publishing to RabbitMQ"""
    # Create foil hole in DB to get an ID
    db_foilhole = FoilHole(**foilhole.model_dump())
    db.add(db_foilhole)
    db.commit()
    db.refresh(db_foilhole)

    # Prepare data for event publishing
    foilhole_event_data = {"id": db_foilhole.id, **foilhole.model_dump()}

    # Publish the event to RabbitMQ
    success = publish_foilhole_created(foilhole_event_data)
    if not success:
        logger.error(f"Failed to publish foil hole created event for ID: {db_foilhole.id}")

    return db_foilhole


@app.get("/foilholes/{foilhole_id}", response_model=FoilHoleResponse)
def get_foilhole(foilhole_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get a single foil hole by ID"""
    foilhole = db.query(FoilHole).filter(FoilHole.id == foilhole_id).first()
    if not foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")
    return foilhole


@app.put("/foilholes/{foilhole_id}", response_model=FoilHoleResponse)
def update_foilhole(foilhole_id: int, foilhole: FoilHoleUpdateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Update a foil hole by publishing to RabbitMQ"""
    # Check if foil hole exists
    db_foilhole = db.query(FoilHole).filter(FoilHole.id == foilhole_id).first()
    if not db_foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    # Prepare update data
    update_data = foilhole.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"id": foilhole_id, **update_data}

    # Publish the event to RabbitMQ
    success = publish_foilhole_updated(event_data)
    if not success:
        logger.error(f"Failed to publish foil hole updated event for ID: {foilhole_id}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_foilhole, key, value)

    db.commit()
    db.refresh(db_foilhole)
    return db_foilhole


@app.delete("/foilholes/{foilhole_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_foilhole(foilhole_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Delete a foil hole by publishing to RabbitMQ"""
    # Check if foil hole exists
    db_foilhole = db.query(FoilHole).filter(FoilHole.id == foilhole_id).first()
    if not db_foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    # Publish the deletion event to RabbitMQ
    success = publish_foilhole_deleted(foilhole_id)
    if not success:
        logger.error(f"Failed to publish foil hole deleted event for ID: {foilhole_id}")

    # For immediate feedback, also delete from the database
    db.delete(db_foilhole)
    db.commit()

    return None


@app.get("/gridsquares/{gridsquare_id}/foilholes", response_model=list[FoilHoleResponse])
def get_gridsquare_foilholes(gridsquare_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get all foil holes for a specific grid square"""
    return db.query(FoilHole).filter(FoilHole.gridsquare_id == gridsquare_id).all()


@app.post(
    "/gridsquares/{gridsquare_id}/foilholes", response_model=FoilHoleResponse, status_code=status.HTTP_201_CREATED
)
def create_gridsquare_foilhole(
    gridsquare_id: int, foilhole: FoilHoleCreateRequest, db: SqlAlchemySession = Depends(get_db)
):
    """Create a new foil hole for a specific grid square by publishing to RabbitMQ"""
    # Check if grid square exists
    gridsquare = db.query(GridSquare).filter(GridSquare.id == gridsquare_id).first()
    if not gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    # Create foil hole data with grid square ID
    foilhole_data = foilhole.model_dump()
    foilhole_data["gridsquare_id"] = gridsquare_id

    # Create foil hole in DB to get an ID
    db_foilhole = FoilHole(**foilhole_data)
    db.add(db_foilhole)
    db.commit()
    db.refresh(db_foilhole)

    # Prepare data for event publishing
    foilhole_event_data = {"id": db_foilhole.id, **foilhole_data}

    # Publish the event to RabbitMQ
    success = publish_foilhole_created(foilhole_event_data)
    if not success:
        logger.error(f"Failed to publish foil hole created event for ID: {db_foilhole.id}")

    return db_foilhole


# ============ Micrograph CRUD Operations ============


@app.get("/micrographs", response_model=list[MicrographResponse])
def get_micrographs(db: SqlAlchemySession = Depends(get_db)):
    """Get all micrographs"""
    return db.query(Micrograph).all()


@app.post("/micrographs", response_model=MicrographResponse, status_code=status.HTTP_201_CREATED)
def create_micrograph(micrograph: MicrographCreateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Create a new micrograph by publishing to RabbitMQ"""
    # Create micrograph in DB to get an ID
    db_micrograph = Micrograph(**micrograph.model_dump())
    db.add(db_micrograph)
    db.commit()
    db.refresh(db_micrograph)

    # Prepare data for event publishing
    micrograph_event_data = {"id": db_micrograph.id, **micrograph.model_dump()}

    # Publish the event to RabbitMQ
    success = publish_micrograph_created(micrograph_event_data)
    if not success:
        logger.error(f"Failed to publish micrograph created event for ID: {db_micrograph.id}")

    return db_micrograph


@app.get("/micrographs/{micrograph_id}", response_model=MicrographResponse)
def get_micrograph(micrograph_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get a single micrograph by ID"""
    micrograph = db.query(Micrograph).filter(Micrograph.id == micrograph_id).first()
    if not micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")
    return micrograph


@app.put("/micrographs/{micrograph_id}", response_model=MicrographResponse)
def update_micrograph(micrograph_id: int, micrograph: MicrographUpdateRequest, db: SqlAlchemySession = Depends(get_db)):
    """Update a micrograph by publishing to RabbitMQ"""
    # Check if micrograph exists
    db_micrograph = db.query(Micrograph).filter(Micrograph.id == micrograph_id).first()
    if not db_micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")

    # Prepare update data
    update_data = micrograph.model_dump(exclude_unset=True)

    # Create event payload
    event_data = {"id": micrograph_id, **update_data}

    # Publish the event to RabbitMQ
    success = publish_micrograph_updated(event_data)
    if not success:
        logger.error(f"Failed to publish micrograph updated event for ID: {micrograph_id}")

    # For immediate feedback, update the object in database too
    for key, value in update_data.items():
        setattr(db_micrograph, key, value)

    db.commit()
    db.refresh(db_micrograph)
    return db_micrograph


@app.delete("/micrographs/{micrograph_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_micrograph(micrograph_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Delete a micrograph by publishing to RabbitMQ"""
    # Check if micrograph exists
    db_micrograph = db.query(Micrograph).filter(Micrograph.id == micrograph_id).first()
    if not db_micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")

    # Publish the deletion event to RabbitMQ
    success = publish_micrograph_deleted(micrograph_id)
    if not success:
        logger.error(f"Failed to publish micrograph deleted event for ID: {micrograph_id}")

    # For immediate feedback, also delete from the database
    db.delete(db_micrograph)
    db.commit()

    return None


@app.get("/foilholes/{foilhole_id}/micrographs", response_model=list[MicrographResponse])
def get_foilhole_micrographs(foilhole_id: int, db: SqlAlchemySession = Depends(get_db)):
    """Get all micrographs for a specific foil hole"""
    return db.query(Micrograph).filter(Micrograph.foilhole_id == foilhole_id).all()


@app.post(
    "/foilholes/{foilhole_id}/micrographs", response_model=MicrographResponse, status_code=status.HTTP_201_CREATED
)
def create_foilhole_micrograph(
    foilhole_id: int, micrograph: MicrographCreateRequest, db: SqlAlchemySession = Depends(get_db)
):
    """Create a new micrograph for a specific foil hole by publishing to RabbitMQ"""
    # Check if foil hole exists
    foilhole = db.query(FoilHole).filter(FoilHole.id == foilhole_id).first()
    if not foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    # Create micrograph data with foil hole ID
    micrograph_data = micrograph.model_dump()
    micrograph_data["foilhole_id"] = foilhole_id

    # Create micrograph in DB to get an ID
    db_micrograph = Micrograph(**micrograph_data)
    db.add(db_micrograph)
    db.commit()
    db.refresh(db_micrograph)

    # Prepare data for event publishing
    micrograph_event_data = {"id": db_micrograph.id, **micrograph_data}

    # Publish the event to RabbitMQ
    success = publish_micrograph_created(micrograph_event_data)
    if not success:
        logger.error(f"Failed to publish micrograph created event for ID: {db_micrograph.id}")

    return db_micrograph
