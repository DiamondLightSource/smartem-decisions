import typer
from sqlmodel import Session

from smartem_backend.model.database import QualityPredictionModel
from smartem_backend.utils import setup_postgres_connection


def register(name: str, description: str) -> None:
    engine = setup_postgres_connection()
    with Session(engine) as sess:
        sess.add(QualityPredictionModel(name=name, description=description))
        sess.commit()
    return None


def run() -> None:
    typer.run(register)
    return None
