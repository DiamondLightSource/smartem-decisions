"""Add micrograph motion-corrected image and snapshot paths

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-08 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("micrograph", sa.Column("motion_corrected_image_path", sa.String(), nullable=True))
    op.add_column("micrograph", sa.Column("motion_corrected_snapshot_path", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("micrograph", "motion_corrected_snapshot_path")
    op.drop_column("micrograph", "motion_corrected_image_path")
