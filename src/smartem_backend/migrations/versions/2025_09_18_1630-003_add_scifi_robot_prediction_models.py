"""Add SciFi robot prediction models test data

This migration adds test data to the qualitypredictionmodel table using
science fiction robot characters for development and testing purposes.

The models added are:
- R2-D2: A sassy trash can on wheels who speaks only in beeps
- Claptrap: An overly enthusiastic one-wheeled model
- WALL-E: A lonely garbage-compacting model
- Bender: A beer-guzzling, cigar-smoking model

Revision ID: 003
Revises: 002
Create Date: 2025-09-18 16:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Insert SciFi robot prediction model test data."""

    # Define the robot model data
    robot_models_data = [
        {
            "name": "R2-D2",
            "description": (
                "A sassy trash can on wheels who speaks only in beeps but somehow "
                "always has the last word in every argument."
            ),
        },
        {
            "name": "Claptrap",
            "description": (
                "An overly enthusiastic one-wheeled model which never stops talking "
                "and considers stairs to be it's greatest nemesis in the universe."
            ),
        },
        {
            "name": "WALL-E",
            "description": (
                "A lonely garbage-compacting model which falls in love and accidentally "
                "saves humanity while pursuing it's passion for collecting shiny objects."
            ),
        },
        {
            "name": "Bender",
            "description": (
                "A beer-guzzling, cigar-smoking model which dreams of becoming a folk "
                "singer but settles for petty theft and making sarcastic comments about humans."
            ),
        },
    ]

    # Get connection and insert data
    connection = op.get_bind()

    # Insert each robot model if it doesn't already exist
    for robot in robot_models_data:
        # Check if model already exists to avoid constraint violations
        result = connection.execute(
            sa.text("SELECT name FROM qualitypredictionmodel WHERE name = :name"), {"name": robot["name"]}
        )

        if not result.fetchone():
            # Insert the new model
            connection.execute(
                sa.text("INSERT INTO qualitypredictionmodel (name, description) VALUES (:name, :description)"),
                {"name": robot["name"], "description": robot["description"]},
            )


def downgrade() -> None:
    """Remove SciFi robot prediction model test data."""

    # Define robot model names to remove
    robot_names = ["R2-D2", "Claptrap", "WALL-E", "Bender"]

    # Get connection and remove data
    connection = op.get_bind()

    # Remove each robot model
    for name in robot_names:
        connection.execute(sa.text("DELETE FROM qualitypredictionmodel WHERE name = :name"), {"name": name})
