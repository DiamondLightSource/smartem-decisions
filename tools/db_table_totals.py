#!/usr/bin/env python3
"""
Database table totals script for smartem-decisions.
Connects to PostgreSQL database and outputs row counts for each table.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlmodel import Session, func, select

# Add src to path so we can import from smartem_decisions
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from smartem_decisions.model.database import (
    Acquisition,
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
    QualityPredictionModelWeight,
)
from smartem_decisions.utils import setup_postgres_connection


def get_table_totals():
    """Connect to database and get row counts for all tables."""

    # Load environment variables from .env file
    load_dotenv()

    # Create database connection with minimal logging
    try:
        engine = setup_postgres_connection()
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)

    # Define all tables and their corresponding SQLModel classes
    tables = [
        ("acquisition", Acquisition),
        ("atlas", Atlas),
        ("atlastile", AtlasTile),
        ("atlastilegridsquareposition", AtlasTileGridSquarePosition),
        ("grid", Grid),
        ("gridsquare", GridSquare),
        ("foilhole", FoilHole),
        ("micrograph", Micrograph),
        ("qualitypredictionmodel", QualityPredictionModel),
        ("qualitypredictionmodelparameter", QualityPredictionModelParameter),
        ("qualitypredictionmodelweight", QualityPredictionModelWeight),
        ("qualityprediction", QualityPrediction),
    ]

    print("Database Table Row Counts")
    print("=" * 40)

    total_rows = 0

    with Session(engine) as session:
        for table_name, model_class in tables:
            try:
                # Use SQLModel exec with func.count to avoid loading all rows
                count = session.exec(select(func.count()).select_from(model_class)).one()
                print(f"{table_name:<35} {count:>8,}")
                total_rows += count
            except Exception as e:
                print(f"{table_name:<35} {'ERROR':>8} - {e}")

    print("=" * 40)
    print(f"{'TOTAL':<35} {total_rows:>8,}")


if __name__ == "__main__":
    get_table_totals()
