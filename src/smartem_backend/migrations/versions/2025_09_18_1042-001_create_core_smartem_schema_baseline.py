"""Create core SmartEM schema baseline

This migration creates the foundational database schema for the SmartEM
cryo-electron microscopy workflow system, including all core entities:

- acquisition: Top-level acquisition sessions
- grid: Sample grids within acquisitions
- gridsquare: Areas of interest on grids
- foilhole: Holes within gridsquares for imaging
- micrograph: Individual microscopy images
- atlas/atlastile: Grid navigation and positioning
- quality prediction models and data
- agent communication tables: Session management, instructions, connections, acknowledgements

Revision ID: 001
Revises:
Create Date: 2025-09-18 10:42:14.253771

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
    # Create tables with enum types
    # SQLAlchemy will automatically create the enum types based on the SQLModel definitions

    # Create acquisition table
    op.create_table(
        "acquisition",
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False, server_default="Unknown"),
        sa.Column(
            "status",
            sa.Enum("PLANNED", "STARTED", "COMPLETED", "PAUSED", "ABANDONED", name="acquisitionstatus"),
            nullable=False,
            server_default="PLANNED",
        ),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("paused_time", sa.DateTime(), nullable=True),
        sa.Column("storage_path", sa.String(), nullable=True),
        sa.Column("atlas_path", sa.String(), nullable=True),
        sa.Column("clustering_mode", sa.String(), nullable=True),
        sa.Column("clustering_radius", sa.String(), nullable=True),
        sa.Column("instrument_model", sa.String(), nullable=True),
        sa.Column("instrument_id", sa.String(), nullable=True),
        sa.Column("computer_name", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("uuid"),
    )

    # Create grid table
    op.create_table(
        "grid",
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("acquisition_uuid", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "NONE",
                "SCAN_STARTED",
                "SCAN_COMPLETED",
                "GRID_SQUARES_DECISION_STARTED",
                "GRID_SQUARES_DECISION_COMPLETED",
                name="gridstatus",
            ),
            nullable=False,
            server_default="NONE",
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("data_dir", sa.String(), nullable=True),
        sa.Column("atlas_dir", sa.String(), nullable=True),
        sa.Column("scan_start_time", sa.DateTime(), nullable=True),
        sa.Column("scan_end_time", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["acquisition_uuid"], ["acquisition.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uuid"),
    )

    # Create atlas table
    op.create_table(
        "atlas",
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("atlas_id", sa.String(), nullable=False, server_default=""),
        sa.Column("grid_uuid", sa.String(), nullable=True),
        sa.Column("acquisition_date", sa.DateTime(), nullable=True),
        sa.Column("storage_folder", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uuid"),
    )

    # Create atlastile table
    op.create_table(
        "atlastile",
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("atlas_uuid", sa.String(), nullable=True),
        sa.Column("tile_id", sa.String(), nullable=False, server_default=""),
        sa.Column("position_x", sa.Integer(), nullable=True),
        sa.Column("position_y", sa.Integer(), nullable=True),
        sa.Column("size_x", sa.Integer(), nullable=True),
        sa.Column("size_y", sa.Integer(), nullable=True),
        sa.Column("file_format", sa.String(), nullable=True),
        sa.Column("base_filename", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["atlas_uuid"], ["atlas.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uuid"),
    )

    # Create gridsquare table
    op.create_table(
        "gridsquare",
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "NONE",
                "FOIL_HOLES_DECISION_STARTED",
                "FOIL_HOLES_DECISION_COMPLETED",
                name="gridsquarestatus",
            ),
            nullable=False,
            server_default="NONE",
        ),
        sa.Column("gridsquare_id", sa.String(), nullable=False, server_default=""),
        sa.Column("data_dir", sa.String(), nullable=True),
        sa.Column("atlas_node_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("rotation", sa.Float(), nullable=True),
        sa.Column("image_path", sa.String(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=True),
        sa.Column("unusable", sa.Boolean(), nullable=True),
        sa.Column("stage_position_x", sa.Float(), nullable=True),
        sa.Column("stage_position_y", sa.Float(), nullable=True),
        sa.Column("stage_position_z", sa.Float(), nullable=True),
        sa.Column("center_x", sa.Integer(), nullable=True),
        sa.Column("center_y", sa.Integer(), nullable=True),
        sa.Column("physical_x", sa.Float(), nullable=True),
        sa.Column("physical_y", sa.Float(), nullable=True),
        sa.Column("size_width", sa.Integer(), nullable=True),
        sa.Column("size_height", sa.Integer(), nullable=True),
        sa.Column("acquisition_datetime", sa.DateTime(), nullable=True),
        sa.Column("defocus", sa.Float(), nullable=True),
        sa.Column("magnification", sa.Float(), nullable=True),
        sa.Column("pixel_size", sa.Float(), nullable=True),
        sa.Column("detector_name", sa.String(), nullable=True),
        sa.Column("applied_defocus", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uuid"),
    )

    # Create atlastilegridsquareposition table
    op.create_table(
        "atlastilegridsquareposition",
        sa.Column("atlastile_uuid", sa.String(), nullable=False),
        sa.Column("gridsquare_uuid", sa.String(), nullable=False),
        sa.Column("center_x", sa.Integer(), nullable=False),
        sa.Column("center_y", sa.Integer(), nullable=False),
        sa.Column("size_width", sa.Integer(), nullable=False),
        sa.Column("size_height", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["atlastile_uuid"], ["atlastile.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gridsquare_uuid"], ["gridsquare.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("atlastile_uuid", "gridsquare_uuid"),
    )

    # Create foilhole table
    op.create_table(
        "foilhole",
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("foilhole_id", sa.String(), nullable=False, server_default=""),
        sa.Column("gridsquare_uuid", sa.String(), nullable=True),
        sa.Column("gridsquare_id", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "NONE",
                "MICROGRAPHS_DETECTED",
                name="foilholestatus",
            ),
            nullable=False,
            server_default="NONE",
        ),
        sa.Column("center_x", sa.Float(), nullable=True),
        sa.Column("center_y", sa.Float(), nullable=True),
        sa.Column("quality", sa.Float(), nullable=True),
        sa.Column("rotation", sa.Float(), nullable=True),
        sa.Column("size_width", sa.Float(), nullable=True),
        sa.Column("size_height", sa.Float(), nullable=True),
        sa.Column("x_location", sa.Integer(), nullable=True),
        sa.Column("y_location", sa.Integer(), nullable=True),
        sa.Column("x_stage_position", sa.Float(), nullable=True),
        sa.Column("y_stage_position", sa.Float(), nullable=True),
        sa.Column("diameter", sa.Integer(), nullable=True),
        sa.Column("is_near_grid_bar", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["gridsquare_uuid"], ["gridsquare.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uuid"),
    )

    # Create micrograph table
    op.create_table(
        "micrograph",
        sa.Column("uuid", sa.String(), nullable=False),
        sa.Column("micrograph_id", sa.String(), nullable=False, server_default=""),
        sa.Column("foilhole_uuid", sa.String(), nullable=True),
        sa.Column("foilhole_id", sa.String(), nullable=False, server_default=""),
        sa.Column("location_id", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "NONE",
                "MOTION_CORRECTION_STARTED",
                "MOTION_CORRECTION_COMPLETED",
                "CTF_STARTED",
                "CTF_COMPLETED",
                "PARTICLE_PICKING_STARTED",
                "PARTICLE_PICKING_COMPLETED",
                "PARTICLE_SELECTION_STARTED",
                "PARTICLE_SELECTION_COMPLETED",
                name="micrographstatus",
            ),
            nullable=False,
            server_default="NONE",
        ),
        sa.Column("high_res_path", sa.String(), nullable=True),
        sa.Column("manifest_file", sa.String(), nullable=True),
        sa.Column("acquisition_datetime", sa.DateTime(), nullable=True),
        sa.Column("defocus", sa.Float(), nullable=True),
        sa.Column("detector_name", sa.String(), nullable=True),
        sa.Column("energy_filter", sa.Boolean(), nullable=True),
        sa.Column("phase_plate", sa.Boolean(), nullable=True),
        sa.Column("image_size_x", sa.Integer(), nullable=True),
        sa.Column("image_size_y", sa.Integer(), nullable=True),
        sa.Column("binning_x", sa.Integer(), nullable=True),
        sa.Column("binning_y", sa.Integer(), nullable=True),
        sa.Column("total_motion", sa.Float(), nullable=True),
        sa.Column("average_motion", sa.Float(), nullable=True),
        sa.Column("ctf_max_resolution_estimate", sa.Float(), nullable=True),
        sa.Column("number_of_particles_selected", sa.Integer(), nullable=True),
        sa.Column("number_of_particles_rejected", sa.Integer(), nullable=True),
        sa.Column("selection_distribution", sa.String(), nullable=True),
        sa.Column("number_of_particles_picked", sa.Integer(), nullable=True),
        sa.Column("pick_distribution", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["foilhole_uuid"], ["foilhole.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uuid"),
    )

    # Create quality prediction model table
    op.create_table(
        "qualitypredictionmodel",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("name"),
    )

    # Create quality prediction model parameter table
    op.create_table(
        "qualitypredictionmodelparameter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("prediction_model_name", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("group", sa.String(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prediction_model_name"], ["qualitypredictionmodel.name"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create quality prediction model weight table
    op.create_table(
        "qualitypredictionmodelweight",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grid_uuid", sa.String(), nullable=False),
        sa.Column("micrograph_uuid", sa.String(), nullable=True),
        sa.Column("micrograph_quality", sa.Boolean(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("origin", sa.String(), nullable=True),
        sa.Column("prediction_model_name", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["grid_uuid"], ["grid.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["micrograph_uuid"], ["micrograph.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prediction_model_name"], ["qualitypredictionmodel.name"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create quality prediction table
    op.create_table(
        "qualityprediction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("prediction_model_name", sa.String(), nullable=False),
        sa.Column("foilhole_uuid", sa.String(), nullable=True),
        sa.Column("gridsquare_uuid", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["foilhole_uuid"], ["foilhole.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gridsquare_uuid"], ["gridsquare.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prediction_model_name"], ["qualitypredictionmodel.name"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ============ Agent Communication Tables ============

    # Create agentsession table with optimized BIGSERIAL primary key
    op.create_table(
        "agentsession",
        sa.Column("id", sa.BigInteger(), nullable=False, primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False, unique=True),
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
        sa.ForeignKeyConstraint(["acquisition_uuid"], ["acquisition.uuid"], ondelete="CASCADE"),
    )

    # Create agentinstruction table with optimized BIGSERIAL primary key
    op.create_table(
        "agentinstruction",
        sa.Column("id", sa.BigInteger(), nullable=False, primary_key=True),
        sa.Column(
            "instruction_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
            unique=True,
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
        sa.ForeignKeyConstraint(["session_id"], ["agentsession.session_id"], ondelete="CASCADE"),
    )

    # Create agentconnection table with optimized BIGSERIAL primary key
    op.create_table(
        "agentconnection",
        sa.Column("id", sa.BigInteger(), nullable=False, primary_key=True),
        sa.Column("connection_id", sa.String(), nullable=False, unique=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("connection_type", sa.String(), nullable=False, server_default="sse"),
        sa.Column("client_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("close_reason", sa.String(), nullable=True),
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

    # ============ Performance Indexes ============

    # Agent communication indexes

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
    # Drop agent communication tables in reverse order of dependencies
    op.drop_table("agentinstructionacknowledgement")
    op.drop_table("agentconnection")
    op.drop_table("agentinstruction")
    op.drop_table("agentsession")

    # Drop core SmartEM tables in reverse order of dependencies
    op.drop_table("qualityprediction")
    op.drop_table("qualitypredictionmodelweight")
    op.drop_table("qualitypredictionmodelparameter")
    op.drop_table("qualitypredictionmodel")
    op.drop_table("micrograph")
    op.drop_table("foilhole")
    op.drop_table("atlastilegridsquareposition")
    op.drop_table("gridsquare")
    op.drop_table("atlastile")
    op.drop_table("atlas")
    op.drop_table("grid")
    op.drop_table("acquisition")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS micrographstatus")
    op.execute("DROP TYPE IF EXISTS foilholestatus")
    op.execute("DROP TYPE IF EXISTS gridsquarestatus")
    op.execute("DROP TYPE IF EXISTS gridstatus")
    op.execute("DROP TYPE IF EXISTS acquisitionstatus")
