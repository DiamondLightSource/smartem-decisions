from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import sessionmaker, Session as SqlAlchemySession

from src.smartem_decisions._version import __version__
from src.smartem_decisions.utils import setup_postgres_connection
from src.smartem_decisions.model.http_response import (
    AcquisitionResponse,
    AtlasResponse,
    AtlasTileResponse,
    GridResponse,
    GridSquareResponse,
    FoilHoleResponse,
    MicrographResponse,
)
from src.smartem_decisions.model.http_request import (
    AcquisitionCreate, AcquisitionUpdate,
    AtlasCreate, AtlasUpdate,
    AtlasTileCreate, AtlasTileUpdate,
    GridCreate, GridUpdate,
    GridSquareCreate, GridSquareUpdate,
    FoilHoleCreate, FoilHoleUpdate,
    MicrographCreate, MicrographUpdate,
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


# ============ Acquisition CRUD Operations ============

@app.get("/acquisitions", response_model=list[AcquisitionResponse])
def get_acquisitions(db: SqlAlchemySession = Depends(get_db)):
    return db.query(Acquisition).all()


@app.post("/acquisitions", response_model=AcquisitionResponse, status_code=status.HTTP_201_CREATED)
def create_acquisition(acquisition: AcquisitionCreate, db: SqlAlchemySession = Depends(get_db)):
    db_acquisition = Acquisition(**acquisition.model_dump())
    db.add(db_acquisition)
    db.commit()
    db.refresh(db_acquisition)
    return db_acquisition


@app.get("/acquisitions/{acquisition_id}", response_model=AcquisitionResponse)
def get_acquisition(acquisition_id: int, db: SqlAlchemySession = Depends(get_db)):
    acquisition = db.query(Acquisition).filter(Acquisition.id == acquisition_id).first()
    if not acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")
    return acquisition


@app.put("/acquisitions/{acquisition_id}", response_model=AcquisitionResponse)
def update_acquisition(acquisition_id: int, acquisition: AcquisitionUpdate, db: SqlAlchemySession = Depends(get_db)):
    db_acquisition = db.query(Acquisition).filter(Acquisition.id == acquisition_id).first()
    if not db_acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    update_data = acquisition.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_acquisition, key, value)

    db.commit()
    db.refresh(db_acquisition)
    return db_acquisition


@app.delete("/acquisitions/{acquisition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_acquisition(acquisition_id: int, db: SqlAlchemySession = Depends(get_db)):
    db_acquisition = db.query(Acquisition).filter(Acquisition.id == acquisition_id).first()
    if not db_acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    db.delete(db_acquisition)
    db.commit()
    return None


# ============ Atlas CRUD Operations ============

@app.get("/atlases", response_model=list[AtlasResponse])
def get_atlases(db: SqlAlchemySession = Depends(get_db)):
    return db.query(Atlas).all()


@app.post("/atlases", response_model=AtlasResponse, status_code=status.HTTP_201_CREATED)
def create_atlas(atlas: AtlasCreate, db: SqlAlchemySession = Depends(get_db)):
    # Extract tiles for later
    tiles_data = None
    if atlas.tiles:
        tiles_data = [tile.model_dump() for tile in atlas.tiles]
        atlas_dict = atlas.model_dump(exclude={"tiles"})
    else:
        atlas_dict = atlas.model_dump()

    db_atlas = Atlas(**atlas_dict)
    db.add(db_atlas)
    db.commit()
    db.refresh(db_atlas)

    # Add tiles if provided
    if tiles_data:
        for tile_data in tiles_data:
            tile_data["atlas_id"] = db_atlas.id
            db_tile = AtlasTile(**tile_data)
            db.add(db_tile)
        db.commit()
        db.refresh(db_atlas)

    return db_atlas


@app.get("/atlases/{atlas_id}", response_model=AtlasResponse)
def get_atlas(atlas_id: int, db: SqlAlchemySession = Depends(get_db)):
    atlas = db.query(Atlas).filter(Atlas.id == atlas_id).first()
    if not atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")
    return atlas


@app.put("/atlases/{atlas_id}", response_model=AtlasResponse)
def update_atlas(atlas_id: int, atlas: AtlasUpdate, db: SqlAlchemySession = Depends(get_db)):
    db_atlas = db.query(Atlas).filter(Atlas.id == atlas_id).first()
    if not db_atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    update_data = atlas.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_atlas, key, value)

    db.commit()
    db.refresh(db_atlas)
    return db_atlas


@app.delete("/atlases/{atlas_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_atlas(atlas_id: int, db: SqlAlchemySession = Depends(get_db)):
    db_atlas = db.query(Atlas).filter(Atlas.id == atlas_id).first()
    if not db_atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    db.delete(db_atlas)
    db.commit()
    return None


@app.get("/grids/{grid_id}/atlas", response_model=AtlasResponse)
def get_grid_atlas(grid_id: int, db: SqlAlchemySession = Depends(get_db)):
    atlas = db.query(Atlas).filter(Atlas.grid_id == grid_id).first()
    if not atlas:
        raise HTTPException(status_code=404, detail="Atlas not found for this grid")
    return atlas


@app.post("/grids/{grid_id}/atlas", response_model=AtlasResponse, status_code=status.HTTP_201_CREATED)
def create_grid_atlas(grid_id: int, atlas: AtlasCreate, db: SqlAlchemySession = Depends(get_db)):
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

    db_atlas = Atlas(**atlas_dict)
    db.add(db_atlas)
    db.commit()
    db.refresh(db_atlas)

    # Add tiles if provided
    if tiles_data:
        for tile_data in tiles_data:
            tile_data["atlas_id"] = db_atlas.id
            db_tile = AtlasTile(**tile_data)
            db.add(db_tile)
        db.commit()
        db.refresh(db_atlas)

    return db_atlas


# ============ Atlas Tile CRUD Operations ============

@app.get("/atlas-tiles", response_model=list[AtlasTileResponse])
def get_atlas_tiles(db: SqlAlchemySession = Depends(get_db)):
    return db.query(AtlasTile).all()


@app.post("/atlas-tiles", response_model=AtlasTileResponse, status_code=status.HTTP_201_CREATED)
def create_atlas_tile(tile: AtlasTileCreate, db: SqlAlchemySession = Depends(get_db)):
    db_tile = AtlasTile(**tile.model_dump())
    db.add(db_tile)
    db.commit()
    db.refresh(db_tile)
    return db_tile


@app.get("/atlas-tiles/{tile_id}", response_model=AtlasTileResponse)
def get_atlas_tile(tile_id: int, db: SqlAlchemySession = Depends(get_db)):
    tile = db.query(AtlasTile).filter(AtlasTile.id == tile_id).first()
    if not tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")
    return tile


@app.put("/atlas-tiles/{tile_id}", response_model=AtlasTileResponse)
def update_atlas_tile(tile_id: int, tile: AtlasTileUpdate, db: SqlAlchemySession = Depends(get_db)):
    db_tile = db.query(AtlasTile).filter(AtlasTile.id == tile_id).first()
    if not db_tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")

    update_data = tile.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tile, key, value)

    db.commit()
    db.refresh(db_tile)
    return db_tile


@app.delete("/atlas-tiles/{tile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_atlas_tile(tile_id: int, db: SqlAlchemySession = Depends(get_db)):
    db_tile = db.query(AtlasTile).filter(AtlasTile.id == tile_id).first()
    if not db_tile:
        raise HTTPException(status_code=404, detail="Atlas tile not found")

    db.delete(db_tile)
    db.commit()
    return None


@app.get("/atlases/{atlas_id}/tiles", response_model=list[AtlasTileResponse])
def get_atlas_tiles_by_atlas(atlas_id: int, db: SqlAlchemySession = Depends(get_db)):
    tiles = db.query(AtlasTile).filter(AtlasTile.atlas_id == atlas_id).all()
    return tiles


@app.post("/atlases/{atlas_id}/tiles", response_model=AtlasTileResponse, status_code=status.HTTP_201_CREATED)
def create_atlas_tile_for_atlas(atlas_id: int, tile: AtlasTileCreate, db: SqlAlchemySession = Depends(get_db)):
    # Verify atlas exists
    atlas = db.query(Atlas).filter(Atlas.id == atlas_id).first()
    if not atlas:
        raise HTTPException(status_code=404, detail="Atlas not found")

    tile_data = tile.model_dump()
    tile_data["atlas_id"] = atlas_id
    db_tile = AtlasTile(**tile_data)

    db.add(db_tile)
    db.commit()
    db.refresh(db_tile)
    return db_tile


# ============ Grid CRUD Operations ============

@app.get("/grids", response_model=list[GridResponse])
def get_grids(db: SqlAlchemySession = Depends(get_db)):
    return db.query(Grid).all()


@app.post("/grids", response_model=GridResponse, status_code=status.HTTP_201_CREATED)
def create_grid(grid: GridCreate, db: SqlAlchemySession = Depends(get_db)):
    db_grid = Grid(**grid.model_dump())
    db.add(db_grid)
    db.commit()
    db.refresh(db_grid)
    return db_grid


@app.get("/grids/{grid_id}", response_model=GridResponse)
def get_grid(grid_id: int, db: SqlAlchemySession = Depends(get_db)):
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")
    return grid


@app.put("/grids/{grid_id}", response_model=GridResponse)
def update_grid(grid_id: int, grid: GridUpdate, db: SqlAlchemySession = Depends(get_db)):
    db_grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not db_grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    update_data = grid.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_grid, key, value)

    db.commit()
    db.refresh(db_grid)
    return db_grid


@app.delete("/grids/{grid_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grid(grid_id: int, db: SqlAlchemySession = Depends(get_db)):
    db_grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not db_grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    db.delete(db_grid)
    db.commit()
    return None


@app.get("/acquisitions/{acquisition_id}/grids", response_model=list[GridResponse])
def get_acquisition_grids(acquisition_id: int, db: SqlAlchemySession = Depends(get_db)):
    # Changed from session_id to acquisition_id
    return db.query(Grid).filter(Grid.acquisition_id == acquisition_id).all()


@app.post("/acquisitions/{acquisition_id}/grids", response_model=GridResponse, status_code=status.HTTP_201_CREATED)
def create_acquisition_grid(acquisition_id: int, grid: GridCreate, db: SqlAlchemySession = Depends(get_db)):
    # Check if acquisition exists
    acquisition = db.query(Acquisition).filter(Acquisition.id == acquisition_id).first()
    if not acquisition:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    # Create grid with acquisition_id (changed from session_id)
    grid_data = grid.model_dump()
    grid_data["acquisition_id"] = acquisition_id
    db_grid = Grid(**grid_data)

    db.add(db_grid)
    db.commit()
    db.refresh(db_grid)
    return db_grid


# ============ GridSquare CRUD Operations ============

@app.get("/gridsquares", response_model=list[GridSquareResponse])
def get_gridsquares(db: SqlAlchemySession = Depends(get_db)):
    return db.query(GridSquare).all()


@app.post("/gridsquares", response_model=GridSquareResponse, status_code=status.HTTP_201_CREATED)
def create_gridsquare(gridsquare: GridSquareCreate, db: SqlAlchemySession = Depends(get_db)):
    db_gridsquare = GridSquare(**gridsquare.model_dump())
    db.add(db_gridsquare)
    db.commit()
    db.refresh(db_gridsquare)
    return db_gridsquare


@app.get("/gridsquares/{gridsquare_id}", response_model=GridSquareResponse)
def get_gridsquare(gridsquare_id: int, db: SqlAlchemySession = Depends(get_db)):
    gridsquare = db.query(GridSquare).filter(GridSquare.id == gridsquare_id).first()
    if not gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")
    return gridsquare


@app.put("/gridsquares/{gridsquare_id}", response_model=GridSquareResponse)
def update_gridsquare(gridsquare_id: int, gridsquare: GridSquareUpdate, db: SqlAlchemySession = Depends(get_db)):
    db_gridsquare = db.query(GridSquare).filter(GridSquare.id == gridsquare_id).first()
    if not db_gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    update_data = gridsquare.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_gridsquare, key, value)

    db.commit()
    db.refresh(db_gridsquare)
    return db_gridsquare


@app.delete("/gridsquares/{gridsquare_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gridsquare(gridsquare_id: int, db: SqlAlchemySession = Depends(get_db)):
    db_gridsquare = db.query(GridSquare).filter(GridSquare.id == gridsquare_id).first()
    if not db_gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    db.delete(db_gridsquare)
    db.commit()
    return None


@app.get("/grids/{grid_id}/gridsquares", response_model=list[GridSquareResponse])
def get_grid_gridsquares(grid_id: int, db: SqlAlchemySession = Depends(get_db)):
    return db.query(GridSquare).filter(GridSquare.grid_id == grid_id).all()


@app.post("/grids/{grid_id}/gridsquares", response_model=GridSquareResponse, status_code=status.HTTP_201_CREATED)
def create_grid_gridsquare(grid_id: int, gridsquare: GridSquareCreate, db: SqlAlchemySession = Depends(get_db)):
    # Check if grid exists
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    # Create gridsquare with grid_id
    gridsquare_data = gridsquare.model_dump()
    gridsquare_data["grid_id"] = grid_id
    db_gridsquare = GridSquare(**gridsquare_data)

    db.add(db_gridsquare)
    db.commit()
    db.refresh(db_gridsquare)
    return db_gridsquare


# ============ FoilHole CRUD Operations ============

@app.get("/foilholes", response_model=list[FoilHoleResponse])
def get_foilholes(db: SqlAlchemySession = Depends(get_db)):
    return db.query(FoilHole).all()


@app.post("/foilholes", response_model=FoilHoleResponse, status_code=status.HTTP_201_CREATED)
def create_foilhole(foilhole: FoilHoleCreate, db: SqlAlchemySession = Depends(get_db)):
    db_foilhole = FoilHole(**foilhole.model_dump())
    db.add(db_foilhole)
    db.commit()
    db.refresh(db_foilhole)
    return db_foilhole


@app.get("/foilholes/{foilhole_id}", response_model=FoilHoleResponse)
def get_foilhole(foilhole_id: int, db: SqlAlchemySession = Depends(get_db)):
    foilhole = db.query(FoilHole).filter(FoilHole.id == foilhole_id).first()
    if not foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")
    return foilhole


@app.put("/foilholes/{foilhole_id}", response_model=FoilHoleResponse)
def update_foilhole(foilhole_id: int, foilhole: FoilHoleUpdate, db: SqlAlchemySession = Depends(get_db)):
    db_foilhole = db.query(FoilHole).filter(FoilHole.id == foilhole_id).first()
    if not db_foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    update_data = foilhole.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_foilhole, key, value)

    db.commit()
    db.refresh(db_foilhole)
    return db_foilhole


@app.delete("/foilholes/{foilhole_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_foilhole(foilhole_id: int, db: SqlAlchemySession = Depends(get_db)):
    db_foilhole = db.query(FoilHole).filter(FoilHole.id == foilhole_id).first()
    if not db_foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    db.delete(db_foilhole)
    db.commit()
    return None


@app.get("/gridsquares/{gridsquare_id}/foilholes", response_model=list[FoilHoleResponse])
def get_gridsquare_foilholes(gridsquare_id: int, db: SqlAlchemySession = Depends(get_db)):
    return db.query(FoilHole).filter(FoilHole.gridsquare_id == gridsquare_id).all()


@app.post("/gridsquares/{gridsquare_id}/foilholes", response_model=FoilHoleResponse,
          status_code=status.HTTP_201_CREATED)
def create_gridsquare_foilhole(gridsquare_id: int, foilhole: FoilHoleCreate, db: SqlAlchemySession = Depends(get_db)):
    # Check if gridsquare exists
    gridsquare = db.query(GridSquare).filter(GridSquare.id == gridsquare_id).first()
    if not gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")

    # Create foilhole with gridsquare_id
    foilhole_data = foilhole.model_dump()
    foilhole_data["gridsquare_id"] = gridsquare_id
    db_foilhole = FoilHole(**foilhole_data)

    db.add(db_foilhole)
    db.commit()
    db.refresh(db_foilhole)
    return db_foilhole


# ============ Micrograph CRUD Operations ============

@app.get("/micrographs", response_model=list[MicrographResponse])
def get_micrographs(db: SqlAlchemySession = Depends(get_db)):
    return db.query(Micrograph).all()


@app.post("/micrographs", response_model=MicrographResponse, status_code=status.HTTP_201_CREATED)
def create_micrograph(micrograph: MicrographCreate, db: SqlAlchemySession = Depends(get_db)):
    db_micrograph = Micrograph(**micrograph.model_dump())
    db.add(db_micrograph)
    db.commit()
    db.refresh(db_micrograph)
    return db_micrograph


@app.get("/micrographs/{micrograph_id}", response_model=MicrographResponse)
def get_micrograph(micrograph_id: int, db: SqlAlchemySession = Depends(get_db)):
    micrograph = db.query(Micrograph).filter(Micrograph.id == micrograph_id).first()
    if not micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")
    return micrograph


@app.put("/micrographs/{micrograph_id}", response_model=MicrographResponse)
def update_micrograph(micrograph_id: int, micrograph: MicrographUpdate, db: SqlAlchemySession = Depends(get_db)):
    db_micrograph = db.query(Micrograph).filter(Micrograph.id == micrograph_id).first()
    if not db_micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")

    update_data = micrograph.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_micrograph, key, value)

    db.commit()
    db.refresh(db_micrograph)
    return db_micrograph


@app.delete("/micrographs/{micrograph_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_micrograph(micrograph_id: int, db: SqlAlchemySession = Depends(get_db)):
    db_micrograph = db.query(Micrograph).filter(Micrograph.id == micrograph_id).first()
    if not db_micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")

    db.delete(db_micrograph)
    db.commit()
    return None


@app.get("/foilholes/{foilhole_id}/micrographs", response_model=list[MicrographResponse])
def get_foilhole_micrographs(foilhole_id: int, db: SqlAlchemySession = Depends(get_db)):
    return db.query(Micrograph).filter(Micrograph.foilhole_id == foilhole_id).all()


@app.post("/foilholes/{foilhole_id}/micrographs", response_model=MicrographResponse,
          status_code=status.HTTP_201_CREATED)
def create_foilhole_micrograph(foilhole_id: int, micrograph: MicrographCreate, db: SqlAlchemySession = Depends(get_db)):
    # Check if foilhole exists
    foilhole = db.query(FoilHole).filter(FoilHole.id == foilhole_id).first()
    if not foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")

    # Create micrograph with foilhole_id
    micrograph_data = micrograph.model_dump()
    micrograph_data["foilhole_id"] = foilhole_id
    db_micrograph = Micrograph(**micrograph_data)

    db.add(db_micrograph)
    db.commit()
    db.refresh(db_micrograph)
    return db_micrograph
