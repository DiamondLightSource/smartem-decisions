"""add foilhole groups and prediction weight tracking

Adds the FoilHoleGroup tables (group, membership, group-level quality
predictions) plus two tracking columns on qualitypredictionmodelweight
(prediction_value, quality_score).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-20 00:01:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "foilholegroup",
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"]),
        sa.PrimaryKeyConstraint("uuid"),
    )

    op.create_table(
        "foilholegroupmembership",
        sa.Column("group_uuid", sa.String(), nullable=False),
        sa.Column("foilhole_uuid", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["group_uuid"], ["foilholegroup.uuid"]),
        sa.ForeignKeyConstraint(["foilhole_uuid"], ["foilhole.uuid"]),
        sa.PrimaryKeyConstraint("group_uuid", "foilhole_uuid"),
    )

    op.create_table(
        "qualitygroupprediction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("group_uuid", sa.String(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("prediction_model_name", sa.String(), nullable=False),
        sa.Column("metric_name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["group_uuid"], ["foilholegroup.uuid"]),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"]),
        sa.ForeignKeyConstraint(["prediction_model_name"], ["qualitypredictionmodel.name"]),
        sa.ForeignKeyConstraint(["metric_name"], ["qualitymetric.name"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "currentqualitygroupprediction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_uuid", sa.String(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("prediction_model_name", sa.String(), nullable=False),
        sa.Column("metric_name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["group_uuid"], ["foilholegroup.uuid"]),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"]),
        sa.ForeignKeyConstraint(["prediction_model_name"], ["qualitypredictionmodel.name"]),
        sa.ForeignKeyConstraint(["metric_name"], ["qualitymetric.name"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("qualitypredictionmodelweight", sa.Column("prediction_value", sa.Float(), nullable=True))
    op.add_column("qualitypredictionmodelweight", sa.Column("quality_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("qualitypredictionmodelweight", "quality_score")
    op.drop_column("qualitypredictionmodelweight", "prediction_value")
    op.drop_table("currentqualitygroupprediction")
    op.drop_table("qualitygroupprediction")
    op.drop_table("foilholegroupmembership")
    op.drop_table("foilholegroup")
