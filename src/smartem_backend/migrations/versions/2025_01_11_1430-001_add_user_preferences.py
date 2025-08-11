"""Add user preferences table

Revision ID: 001
Revises:
Create Date: 2025-01-11 14:30:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_preferences table
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("preference_key", sa.String(255), nullable=False),
        sa.Column("preference_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "preference_key", name="uq_user_preference_key"),
    )

    # Create indexes for efficient queries
    op.create_index("idx_user_preferences_user_id", "user_preferences", ["user_id"])
    op.create_index("idx_user_preferences_key", "user_preferences", ["preference_key"])


def downgrade() -> None:
    op.drop_index("idx_user_preferences_key", table_name="user_preferences")
    op.drop_index("idx_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
