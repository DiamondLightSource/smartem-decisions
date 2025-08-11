"""Seed system configuration data

Revision ID: 003
Revises: 002
Create Date: 2025-01-11 14:32:00.000000

"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create a temporary table reference for data operations
    user_preferences_table = table(
        "user_preferences",
        column("id", Integer),
        column("user_id", String),
        column("preference_key", String),
        column("preference_value", sa.JSON),
        column("created_at", DateTime),
        column("updated_at", DateTime),
    )

    # Insert default system configuration preferences
    op.bulk_insert(
        user_preferences_table,
        [
            {
                "user_id": "system",
                "preference_key": "default_acquisition_settings",
                "preference_value": {
                    "clustering_mode": "auto",
                    "clustering_radius": "2.0",
                    "default_magnification": 165000,
                    "default_pixel_size": 0.8,
                },
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
            {
                "user_id": "system",
                "preference_key": "quality_thresholds",
                "preference_value": {"min_foilhole_quality": 0.3, "min_ctf_resolution": 4.0, "max_total_motion": 50.0},
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
            {
                "user_id": "system",
                "preference_key": "ui_defaults",
                "preference_value": {
                    "grid_view_columns": ["name", "status", "scan_start_time"],
                    "default_page_size": 50,
                    "auto_refresh_interval": 30,
                },
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
        ],
    )


def downgrade() -> None:
    # Remove the seeded system configuration data
    op.execute(
        "DELETE FROM user_preferences WHERE user_id = 'system' AND preference_key IN "
        "('default_acquisition_settings', 'quality_thresholds', 'ui_defaults')"
    )
