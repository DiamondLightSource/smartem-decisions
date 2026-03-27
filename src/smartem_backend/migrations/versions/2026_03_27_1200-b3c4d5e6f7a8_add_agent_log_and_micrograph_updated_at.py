"""Add agent_log table and micrograph.updated_at column

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-27 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agentlog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("logger_name", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agentlog_agent_id", "agentlog", ["agent_id"])
    op.create_index("ix_agentlog_session_id", "agentlog", ["session_id"])
    op.create_index("ix_agentlog_timestamp", "agentlog", ["timestamp"])
    op.create_index("ix_agentlog_level", "agentlog", ["level"])
    op.create_index("ix_agentlog_agent_id_id", "agentlog", ["agent_id", "id"])

    op.add_column("micrograph", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_micrograph_updated_at", "micrograph", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_micrograph_updated_at", table_name="micrograph")
    op.drop_column("micrograph", "updated_at")

    op.drop_index("ix_agentlog_agent_id_id", table_name="agentlog")
    op.drop_index("ix_agentlog_level", table_name="agentlog")
    op.drop_index("ix_agentlog_timestamp", table_name="agentlog")
    op.drop_index("ix_agentlog_session_id", table_name="agentlog")
    op.drop_index("ix_agentlog_agent_id", table_name="agentlog")
    op.drop_table("agentlog")
