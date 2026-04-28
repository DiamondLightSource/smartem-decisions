"""Add can_train, can_infer, can_update flags to qualitypredictionmodel

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-04-28 11:19:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "qualitypredictionmodel",
        sa.Column("can_train", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "qualitypredictionmodel",
        sa.Column("can_infer", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "qualitypredictionmodel",
        sa.Column("can_update", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("qualitypredictionmodel", "can_update")
    op.drop_column("qualitypredictionmodel", "can_infer")
    op.drop_column("qualitypredictionmodel", "can_train")
