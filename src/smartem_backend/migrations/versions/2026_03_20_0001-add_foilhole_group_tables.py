"""add foilhole group tables and foilholegroup model level

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
    # Extend the modellevel enum with the new FOILHOLEGROUP value
    op.execute("ALTER TYPE modellevel ADD VALUE IF NOT EXISTS 'foilholegroup'")

    op.create_table(
        "foilholegroup",
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index("ix_foilholegroup_grid_uuid", "foilholegroup", ["grid_uuid"])

    op.create_table(
        "foilholegroupmembership",
        sa.Column("group_uuid", sa.String(), nullable=False),
        sa.Column("foilhole_uuid", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["group_uuid"], ["foilholegroup.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["foilhole_uuid"], ["foilhole.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_uuid", "foilhole_uuid"),
    )

    op.create_table(
        "currentqualitygroupprediction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_uuid", sa.String(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("prediction_model_name", sa.String(), nullable=False),
        sa.Column("metric_name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["group_uuid"], ["foilholegroup.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prediction_model_name"], ["qualitypredictionmodel.name"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["metric_name"], ["qualitymetric.name"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_currentqualitygroupprediction_group_uuid",
        "currentqualitygroupprediction",
        ["group_uuid"],
    )
    op.create_index(
        "ix_currentqualitygroupprediction_grid_uuid",
        "currentqualitygroupprediction",
        ["grid_uuid"],
    )


def downgrade() -> None:
    op.drop_index("ix_currentqualitygroupprediction_grid_uuid", table_name="currentqualitygroupprediction")
    op.drop_index("ix_currentqualitygroupprediction_group_uuid", table_name="currentqualitygroupprediction")
    op.drop_table("currentqualitygroupprediction")
    op.drop_table("foilholegroupmembership")
    op.drop_index("ix_foilholegroup_grid_uuid", table_name="foilholegroup")
    op.drop_table("foilholegroup")
    # Note: PostgreSQL does not support removing values from an enum type,
    # so the 'foilholegroup' enum value cannot be removed during downgrade.
