import os
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import sessionmaker, Session as SqlAlchemyORMSession
from sqlalchemy import create_engine
from typing import List

from src.smartem_decisions.model.http_response import (
    SessionResponse,
    GridResponse,
    GridSquareResponse,
    FoilHoleResponse,
    MicrographResponse,
)

from src.smartem_decisions.model.database import Session, Grid, GridSquare, FoilHole, Micrograph

load_dotenv()
assert os.getenv("POSTGRES_USER") is not None, "Could not get env var POSTGRES_USER"
assert os.getenv("POSTGRES_PASSWORD") is not None, "Could not get env var POSTGRES_PASSWORD"
assert os.getenv("POSTGRES_PORT") is not None, "Could not get env var POSTGRES_PORT"
assert os.getenv("POSTGRES_DB") is not None, "Could not get env var POSTGRES_DB"
engine = create_engine(
    f"postgresql+psycopg2://{os.getenv("POSTGRES_USER")}:{os.getenv("POSTGRES_PASSWORD")}@localhost:{os.getenv("POSTGRES_PORT")}/{os.getenv("POSTGRES_DB")}",
    echo=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# TODO Fill this in
#   Ref: https://fastapi.tiangolo.com/tutorial/metadata/#metadata-for-api
# description = """
# ChimichangApp API helps you do awesome stuff. 🚀
#
# ## Items
#
# You can **read items**.
#
# ## Users
#
# You will be able to:
#
# * **Create users** (_not implemented_).
# * **Read users** (_not implemented_).
# """
app = FastAPI(
    # title="ChimichangApp",
    # description=description,
    # summary="Deadpool's favorite app. Nuff said.",
    # version="0.0.1",
    # terms_of_service="http://example.com/terms/",
    # contact={
    #     "name": "Deadpoolio the Amazing",
    #     "url": "http://x-force.example.com/contact/",
    #     "email": "dp@x-force.example.com",
    # },
    # license_info={
    #     "name": "Apache 2.0",
    #     "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    # },
    redoc_url=None,
)


# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/sessions", response_model=List[SessionResponse])
def get_sessions(db: SqlAlchemyORMSession = Depends(get_db)):
    return db.query(Session).all()


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: int, db: SqlAlchemyORMSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/grids", response_model=List[GridResponse])
def get_grids(db: SqlAlchemyORMSession = Depends(get_db)):
    return db.query(Grid).all()


@app.get("/grids/{grid_id}", response_model=GridResponse)
def get_grid(grid_id: int, db: SqlAlchemyORMSession = Depends(get_db)):
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")
    return grid


@app.get("/sessions/{session_id}/grids", response_model=List[GridResponse])
def get_session_grids(session_id: int, db: SqlAlchemyORMSession = Depends(get_db)):
    return db.query(Grid).filter(Grid.session_id == session_id).all()


@app.get("/gridsquares", response_model=List[GridSquareResponse])
def get_gridsquares(db: SqlAlchemyORMSession = Depends(get_db)):
    return db.query(GridSquare).all()


@app.get("/gridsquares/{gridsquare_id}", response_model=GridSquareResponse)
def get_gridsquare(gridsquare_id: int, db: SqlAlchemyORMSession = Depends(get_db)):
    gridsquare = db.query(GridSquare).filter(GridSquare.id == gridsquare_id).first()
    if not gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")
    return gridsquare


@app.get("/grids/{grid_id}/gridsquares", response_model=List[GridSquareResponse])
def get_grid_gridsquares(grid_id: int, db: SqlAlchemyORMSession = Depends(get_db)):
    return db.query(GridSquare).filter(GridSquare.grid_id == grid_id).all()


@app.get("/foilholes", response_model=List[FoilHoleResponse])
def get_foilholes(db: SqlAlchemyORMSession = Depends(get_db)):
    return db.query(FoilHole).all()


@app.get("/foilholes/{foilhole_id}", response_model=FoilHoleResponse)
def get_foilhole(foilhole_id: int, db: SqlAlchemyORMSession = Depends(get_db)):
    foilhole = db.query(FoilHole).filter(FoilHole.id == foilhole_id).first()
    if not foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")
    return foilhole


@app.get("/gridsquares/{gridsquare_id}/foilholes", response_model=List[FoilHoleResponse])
def get_gridsquare_foilholes(gridsquare_id: int, db: SqlAlchemyORMSession = Depends(get_db)):
    return db.query(FoilHole).filter(FoilHole.gridsquare_id == gridsquare_id).all()


@app.get("/micrographs", response_model=List[MicrographResponse])
def get_micrographs(db: SqlAlchemyORMSession = Depends(get_db)):
    return db.query(Micrograph).all()


@app.get("/micrographs/{micrograph_id}", response_model=MicrographResponse)
def get_micrograph(micrograph_id: int, db: SqlAlchemyORMSession = Depends(get_db)):
    micrograph = db.query(Micrograph).filter(Micrograph.id == micrograph_id).first()
    if not micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")
    return micrograph


@app.get("/foilholes/{foilhole_id}/micrographs", response_model=List[MicrographResponse])
def get_foilhole_micrographs(foilhole_id: int, db: SqlAlchemyORMSession = Depends(get_db)):
    return db.query(Micrograph).filter(Micrograph.foilhole_id == foilhole_id).all()
