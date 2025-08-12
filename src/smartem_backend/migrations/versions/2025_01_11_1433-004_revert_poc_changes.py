"""Revert all POC migration changes

This migration removes all changes introduced by the first three POC migrations:
- Removes user_preferences table (from 001)
- Removes performance indexes (from 002)
- Removes seeded configuration data (from 003)

These were test migrations to demonstrate the migration system capabilities.

Revision ID: 004
Revises: 003
Create Date: 2025-01-11 14:33:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Remove seeded system configuration data (reverse of 003)
    op.execute(
        "DELETE FROM user_preferences WHERE user_id = 'system' AND preference_key IN "
        "('default_acquisition_settings', 'quality_thresholds', 'ui_defaults')"
    )

    # Step 2: Remove performance indexes (reverse of 002)
    op.drop_index("idx_micrograph_acquisition_datetime", table_name="micrograph")
    op.drop_index("idx_gridsquare_acquisition_datetime_status", table_name="gridsquare")

    # Step 3: Remove user_preferences table (reverse of 001)
    op.drop_index("idx_user_preferences_key", table_name="user_preferences")
    op.drop_index("idx_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")


def downgrade() -> None:
    # This would essentially re-apply all the POC migrations
    # For simplicity, we'll just raise an error since this is a cleanup migration
    raise NotImplementedError(
        "Cannot rollback the POC cleanup migration. "
        "Use 'alembic downgrade 001' to restore POC state, "
        "or 'alembic downgrade base' to start fresh."
    )
