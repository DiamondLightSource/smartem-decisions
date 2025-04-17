from pydantic import BaseModel, Field
from datetime import datetime

# Acquisition models
class AcquisitionBase(BaseModel):
    name: str
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None

class AcquisitionCreate(AcquisitionBase):
    pass

class AcquisitionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None


# Grid models
class GridBase(BaseModel):
    name: str
    session_id: int
    description: str | None = None
    atlas_image_path: str | None = None
    status: str | None = None

class GridCreate(GridBase):
    pass

class GridUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    atlas_image_path: str | None = None
    status: str | None = None
    session_id: int | None = None


# GridSquare models
class GridSquareBase(BaseModel):
    grid_id: int
    name: str
    x_position: float
    y_position: float
    image_path: str | None = None
    status: str | None = None

class GridSquareCreate(GridSquareBase):
    pass

class GridSquareUpdate(BaseModel):
    name: str | None = None
    x_position: float | None = None
    y_position: float | None = None
    image_path: str | None = None
    status: str | None = None
    grid_id: str | None = None


# FoilHole models
class FoilHoleBase(BaseModel):
    gridsquare_id: int
    name: str
    x_position: float
    y_position: float
    diameter: float | None = None
    image_path: str | None = None
    status: str | None = None

class FoilHoleCreate(FoilHoleBase):
    pass

class FoilHoleUpdate(BaseModel):
    name: str | None = None
    x_position: float | None = None
    y_position: float | None = None
    diameter: float | None = None
    image_path: str | None = None
    status: str | None = None
    gridsquare_id: int | None = None


# Micrograph models
class MicrographBase(BaseModel):
    foilhole_id: int
    name: str
    image_path: str
    ctf_image_path: str | None = None
    defocus: float | None = None
    astigmatism: float | None = None
    resolution: float | None = None
    status: str | None = None

class MicrographCreate(MicrographBase):
    pass

class MicrographUpdate(BaseModel):
    name: str | None = None
    image_path: str | None = None
    ctf_image_path: str | None = None
    defocus: float | None = None
    astigmatism: float | None = None
    resolution: float | None = None
    status: str | None = None
    foilhole_id: int | None = None
