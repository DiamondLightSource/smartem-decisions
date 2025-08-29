"""Add agent communication tables for SmartEM Decisions

This migration adds the complete agent communication infrastructure:
- agentsession: Tracks microscopy sessions and experimental context
- agentinstruction: Stores instructions sent to agents with full lifecycle tracking
- agentconnection: Tracks active SSE connections for health monitoring
- agentinstructionacknowledgement: Audit trail for instruction processing

These tables support the backend-to-agent communication system for
real-time microscope control and scientific data provenance.

Revision ID: 005
Revises: 004
Create Date: 2025-08-29 10:30:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create agentsession table
    op.create_table(
        "agentsession",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("acquisition_uuid", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("experimental_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
        sa.ForeignKeyConstraint(["acquisition_uuid"], ["acquisition.uuid"], ondelete="CASCADE"),
    )

    # Create agentinstruction table
    op.create_table(
        "agentinstruction",
        sa.Column(
            "instruction_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("instruction_type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("priority", sa.String(), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("instruction_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("instruction_id"),
        sa.ForeignKeyConstraint(["session_id"], ["agentsession.session_id"], ondelete="CASCADE"),
    )

    # Create agentconnection table
    op.create_table(
        "agentconnection",
        sa.Column("connection_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("connection_type", sa.String(), nullable=False, server_default="sse"),
        sa.Column("client_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("close_reason", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("connection_id"),
        sa.ForeignKeyConstraint(["session_id"], ["agentsession.session_id"], ondelete="CASCADE"),
    )

    # Create agentinstructionacknowledgement table
    op.create_table(
        "agentinstructionacknowledgement",
        sa.Column(
            "acknowledgement_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("instruction_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("result", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("acknowledgement_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("acknowledgement_id"),
        sa.ForeignKeyConstraint(["instruction_id"], ["agentinstruction.instruction_id"], ondelete="CASCADE"),
    )

    # Create performance indexes for agent communication tables

    # AgentSession indexes
    op.create_index("idx_agent_session_agent_id", "agentsession", ["agent_id"])
    op.create_index("idx_agent_session_acquisition_uuid", "agentsession", ["acquisition_uuid"])
    op.create_index("idx_agent_session_status", "agentsession", ["status"])
    op.create_index("idx_agent_session_created_at", "agentsession", ["created_at"])
    op.create_index("idx_agent_session_last_activity", "agentsession", ["last_activity_at"])

    # AgentInstruction indexes
    op.create_index("idx_agent_instruction_session_id", "agentinstruction", ["session_id"])
    op.create_index("idx_agent_instruction_agent_id", "agentinstruction", ["agent_id"])
    op.create_index("idx_agent_instruction_type", "agentinstruction", ["instruction_type"])
    op.create_index("idx_agent_instruction_status", "agentinstruction", ["status"])
    op.create_index("idx_agent_instruction_created_at", "agentinstruction", ["created_at"])
    op.create_index("idx_agent_instruction_sent_at", "agentinstruction", ["sent_at"])
    op.create_index("idx_agent_instruction_acknowledged_at", "agentinstruction", ["acknowledged_at"])
    op.create_index("idx_agent_instruction_expires_at", "agentinstruction", ["expires_at"])
    op.create_index("idx_agent_instruction_sequence", "agentinstruction", ["sequence_number"])
    op.create_index("idx_agent_instruction_priority", "agentinstruction", ["priority"])

    # AgentConnection indexes
    op.create_index("idx_agent_connection_session_id", "agentconnection", ["session_id"])
    op.create_index("idx_agent_connection_agent_id", "agentconnection", ["agent_id"])
    op.create_index("idx_agent_connection_status", "agentconnection", ["status"])
    op.create_index("idx_agent_connection_created_at", "agentconnection", ["created_at"])
    op.create_index("idx_agent_connection_heartbeat", "agentconnection", ["last_heartbeat_at"])

    # AgentInstructionAcknowledgement indexes
    op.create_index("idx_agent_ack_instruction_id", "agentinstructionacknowledgement", ["instruction_id"])
    op.create_index("idx_agent_ack_agent_id", "agentinstructionacknowledgement", ["agent_id"])
    op.create_index("idx_agent_ack_session_id", "agentinstructionacknowledgement", ["session_id"])
    op.create_index("idx_agent_ack_status", "agentinstructionacknowledgement", ["status"])
    op.create_index("idx_agent_ack_created_at", "agentinstructionacknowledgement", ["created_at"])
    op.create_index("idx_agent_ack_processed_at", "agentinstructionacknowledgement", ["processed_at"])

    # Create composite indexes for common query patterns
    op.create_index("idx_agent_session_agent_status", "agentsession", ["agent_id", "status"])
    op.create_index("idx_agent_instruction_session_status", "agentinstruction", ["session_id", "status"])
    op.create_index("idx_agent_instruction_agent_created", "agentinstruction", ["agent_id", "created_at"])
    op.create_index("idx_agent_connection_agent_status", "agentconnection", ["agent_id", "status"])


def downgrade() -> None:
    # Remove composite indexes
    op.drop_index("idx_agent_connection_agent_status", table_name="agentconnection")
    op.drop_index("idx_agent_instruction_agent_created", table_name="agentinstruction")
    op.drop_index("idx_agent_instruction_session_status", table_name="agentinstruction")
    op.drop_index("idx_agent_session_agent_status", table_name="agentsession")

    # Remove AgentInstructionAcknowledgement indexes
    op.drop_index("idx_agent_ack_processed_at", table_name="agentinstructionacknowledgement")
    op.drop_index("idx_agent_ack_created_at", table_name="agentinstructionacknowledgement")
    op.drop_index("idx_agent_ack_status", table_name="agentinstructionacknowledgement")
    op.drop_index("idx_agent_ack_session_id", table_name="agentinstructionacknowledgement")
    op.drop_index("idx_agent_ack_agent_id", table_name="agentinstructionacknowledgement")
    op.drop_index("idx_agent_ack_instruction_id", table_name="agentinstructionacknowledgement")

    # Remove AgentConnection indexes
    op.drop_index("idx_agent_connection_heartbeat", table_name="agentconnection")
    op.drop_index("idx_agent_connection_created_at", table_name="agentconnection")
    op.drop_index("idx_agent_connection_status", table_name="agentconnection")
    op.drop_index("idx_agent_connection_agent_id", table_name="agentconnection")
    op.drop_index("idx_agent_connection_session_id", table_name="agentconnection")

    # Remove AgentInstruction indexes
    op.drop_index("idx_agent_instruction_priority", table_name="agentinstruction")
    op.drop_index("idx_agent_instruction_sequence", table_name="agentinstruction")
    op.drop_index("idx_agent_instruction_expires_at", table_name="agentinstruction")
    op.drop_index("idx_agent_instruction_acknowledged_at", table_name="agentinstruction")
    op.drop_index("idx_agent_instruction_sent_at", table_name="agentinstruction")
    op.drop_index("idx_agent_instruction_created_at", table_name="agentinstruction")
    op.drop_index("idx_agent_instruction_status", table_name="agentinstruction")
    op.drop_index("idx_agent_instruction_type", table_name="agentinstruction")
    op.drop_index("idx_agent_instruction_agent_id", table_name="agentinstruction")
    op.drop_index("idx_agent_instruction_session_id", table_name="agentinstruction")

    # Remove AgentSession indexes
    op.drop_index("idx_agent_session_last_activity", table_name="agentsession")
    op.drop_index("idx_agent_session_created_at", table_name="agentsession")
    op.drop_index("idx_agent_session_status", table_name="agentsession")
    op.drop_index("idx_agent_session_acquisition_uuid", table_name="agentsession")
    op.drop_index("idx_agent_session_agent_id", table_name="agentsession")

    # Drop tables in reverse order of dependencies
    op.drop_table("agentinstructionacknowledgement")
    op.drop_table("agentconnection")
    op.drop_table("agentinstruction")
    op.drop_table("agentsession")
