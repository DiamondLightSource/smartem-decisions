"""add gridsquare groups

Adds the GridSquareGroup tables (group, membership, group-level quality
predictions) mirroring the existing FoilHoleGroup mechanism, so a single
prediction can be applied to an arbitrary set of grid squares at once.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-16 11:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gridsquaregroup",
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"]),
        sa.PrimaryKeyConstraint("uuid"),
    )

    op.create_table(
        "gridsquaregroupmembership",
        sa.Column("group_uuid", sa.String(), nullable=False),
        sa.Column("gridsquare_uuid", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["group_uuid"], ["gridsquaregroup.uuid"]),
        sa.ForeignKeyConstraint(["gridsquare_uuid"], ["gridsquare.uuid"]),
        sa.PrimaryKeyConstraint("group_uuid", "gridsquare_uuid"),
    )

    op.create_table(
        "qualitygridsquaregroupprediction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("group_uuid", sa.String(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("prediction_model_name", sa.String(), nullable=False),
        sa.Column("metric_name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["group_uuid"], ["gridsquaregroup.uuid"]),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"]),
        sa.ForeignKeyConstraint(["prediction_model_name"], ["qualitypredictionmodel.name"]),
        sa.ForeignKeyConstraint(["metric_name"], ["qualitymetric.name"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "currentqualitygridsquaregroupprediction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_uuid", sa.String(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("prediction_model_name", sa.String(), nullable=False),
        sa.Column("metric_name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["group_uuid"], ["gridsquaregroup.uuid"]),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"]),
        sa.ForeignKeyConstraint(["prediction_model_name"], ["qualitypredictionmodel.name"]),
        sa.ForeignKeyConstraint(["metric_name"], ["qualitymetric.name"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("currentqualitygridsquaregroupprediction")
    op.drop_table("qualitygridsquaregroupprediction")
    op.drop_table("gridsquaregroupmembership")
    op.drop_table("gridsquaregroup")
