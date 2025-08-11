"""Add composite index for acquisition datetime queries

Revision ID: 002
Revises: 001
Create Date: 2025-01-11 14:31:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add composite index for common time-range queries on gridsquares
    op.create_index(
        "idx_gridsquare_acquisition_datetime_status",
        "gridsquare",
        ["acquisition_datetime", "status"],
        postgresql_using="btree",
    )

    # Add index on micrograph acquisition datetime for performance
    op.create_index(
        "idx_micrograph_acquisition_datetime", "micrograph", ["acquisition_datetime"], postgresql_using="btree"
    )


def downgrade() -> None:
    op.drop_index("idx_micrograph_acquisition_datetime", table_name="micrograph")
    op.drop_index("idx_gridsquare_acquisition_datetime_status", table_name="gridsquare")
