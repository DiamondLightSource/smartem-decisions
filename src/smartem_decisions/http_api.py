from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import sessionmaker, Session as SqlAlchemySession

from src.smartem_decisions.utils import setup_postgres_connection
from src.smartem_decisions.model.http_response import (
    AcquisitionResponse,
    GridResponse,
    GridSquareResponse,
    FoilHoleResponse,
    MicrographResponse,
)

from src.smartem_decisions.model.database import (
    Acquisition,
    Grid,
    GridSquare,
    FoilHole,
    Micrograph,
)

db_engine = setup_postgres_connection()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

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


@app.get("/acquisitions", response_model=list[AcquisitionResponse])
def get_acquisitions(db: SqlAlchemySession = Depends(get_db)):
    return db.query(Acquisition).all()


@app.get("/acquisitions/{acquisition_id}", response_model=AcquisitionResponse)
def get_acquisition(acquisition_id: int, db: SqlAlchemySession = Depends(get_db)):
    # Note: we can safely ignore the warnings from PyCharm/VSCode akin `.filter(Acquisition.id == acquisition_id)`.
    # This is a common situation with SQLAlchemy and FastAPI where the type checker has some confusion about what's being
    # passed to the filter method. The code `Acquisition.id == acquisition_id` is perfectly valid SQLAlchemy syntax for
    # creating a filter condition. It's comparing a column (`Acquisition.id`) with a value (`acquisition_id`) to generate
    # a `SQL WHERE` clause. This works correctly at runtime because SQLAlchemy overloads the `==` operator for its column
    # objects to return a comparison expression rather than a boolean. The type checker is expecting a more specific
    # SQLAlchemy type, but the actual runtime behavior is exactly what we want. Since the code works fine in practice,
    # this is just a limitation in how PyCharm's type system understands SQLAlchemy's expression language.
    session = db.query(Acquisition).filter(Acquisition.id == acquisition_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/grids", response_model=list[GridResponse])
def get_grids(db: SqlAlchemySession = Depends(get_db)):
    return db.query(Grid).all()


@app.get("/grids/{grid_id}", response_model=GridResponse)
def get_grid(grid_id: int, db: SqlAlchemySession = Depends(get_db)):
    grid = db.query(Grid).filter(Grid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")
    return grid


@app.get("/acquisitions/{acquisition_id}/grids", response_model=list[GridResponse])
def get_acquisition_grids(acquisition_id: int, db: SqlAlchemySession = Depends(get_db)):
    return db.query(Grid).filter(Grid.session_id == acquisition_id).all()


@app.get("/gridsquares", response_model=list[GridSquareResponse])
def get_gridsquares(db: SqlAlchemySession = Depends(get_db)):
    return db.query(GridSquare).all()


@app.get("/gridsquares/{gridsquare_id}", response_model=GridSquareResponse)
def get_gridsquare(gridsquare_id: int, db: SqlAlchemySession = Depends(get_db)):
    gridsquare = db.query(GridSquare).filter(GridSquare.id == gridsquare_id).first()
    if not gridsquare:
        raise HTTPException(status_code=404, detail="Grid Square not found")
    return gridsquare


@app.get("/grids/{grid_id}/gridsquares", response_model=list[GridSquareResponse])
def get_grid_gridsquares(grid_id: int, db: SqlAlchemySession = Depends(get_db)):
    return db.query(GridSquare).filter(GridSquare.grid_id == grid_id).all()


@app.get("/foilholes", response_model=list[FoilHoleResponse])
def get_foilholes(db: SqlAlchemySession = Depends(get_db)):
    return db.query(FoilHole).all()


@app.get("/foilholes/{foilhole_id}", response_model=FoilHoleResponse)
def get_foilhole(foilhole_id: int, db: SqlAlchemySession = Depends(get_db)):
    foilhole = db.query(FoilHole).filter(FoilHole.id == foilhole_id).first()
    if not foilhole:
        raise HTTPException(status_code=404, detail="Foil Hole not found")
    return foilhole


@app.get("/gridsquares/{gridsquare_id}/foilholes", response_model=list[FoilHoleResponse])
def get_gridsquare_foilholes(gridsquare_id: int, db: SqlAlchemySession = Depends(get_db)):
    return db.query(FoilHole).filter(FoilHole.gridsquare_id == gridsquare_id).all()


@app.get("/micrographs", response_model=list[MicrographResponse])
def get_micrographs(db: SqlAlchemySession = Depends(get_db)):
    return db.query(Micrograph).all()


@app.get("/micrographs/{micrograph_id}", response_model=MicrographResponse)
def get_micrograph(micrograph_id: int, db: SqlAlchemySession = Depends(get_db)):
    micrograph = db.query(Micrograph).filter(Micrograph.id == micrograph_id).first()
    if not micrograph:
        raise HTTPException(status_code=404, detail="Micrograph not found")
    return micrograph


@app.get("/foilholes/{foilhole_id}/micrographs", response_model=list[MicrographResponse])
def get_foilhole_micrographs(foilhole_id: int, db: SqlAlchemySession = Depends(get_db)):
    return db.query(Micrograph).filter(Micrograph.foilhole_id == foilhole_id).all()
