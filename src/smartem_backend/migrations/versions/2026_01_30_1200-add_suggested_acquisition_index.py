"""add suggested_acquisition_index to overall_quality_prediction

Revision ID: a1b2c3d4e5f6
Revises: 87f8c5e11906
Create Date: 2026-01-30 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "87f8c5e11906"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "overallqualityprediction",
        sa.Column("suggested_acquisition_index", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE overallqualityprediction SET suggested_acquisition_index = 0 WHERE suggested_acquisition_index IS NULL")
    op.alter_column("overallqualityprediction", "suggested_acquisition_index", nullable=False)


def downgrade() -> None:
    op.drop_column("overallqualityprediction", "suggested_acquisition_index")
