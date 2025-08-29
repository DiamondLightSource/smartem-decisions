"""Optimize agent communication primary keys

This migration optimizes the agent communication tables by converting
backend-originated entities to use BIGSERIAL primary keys while keeping
agent-originated entities with UUID primary keys:

- agentsession: UUID -> BIGSERIAL (backend creates sessions)
- agentinstruction: UUID -> BIGSERIAL (backend creates instructions)
- agentconnection: STRING -> BIGSERIAL (backend tracks connections)
- agentinstructionacknowledgement: UUID (unchanged, agent creates)

This follows the pattern where backend-originated data uses native PostgreSQL
primary keys for better performance and scalability, while agent-originated
data keeps UUIDs for distributed creation safety.

Revision ID: 006
Revises: 005
Create Date: 2025-08-29 14:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add new BIGSERIAL primary key columns alongside existing ones

    # AgentSession: Add new id column
    op.add_column("agentsession", sa.Column("id", sa.BigInteger(), nullable=True))
    op.execute("CREATE SEQUENCE agentsession_id_seq")
    op.execute("ALTER TABLE agentsession ALTER COLUMN id SET DEFAULT nextval('agentsession_id_seq')")
    op.execute("SELECT setval('agentsession_id_seq', COALESCE(MAX(length(session_id)), 0) + 1) FROM agentsession")
    op.execute("UPDATE agentsession SET id = nextval('agentsession_id_seq') WHERE id IS NULL")
    op.alter_column("agentsession", "id", nullable=False)

    # AgentInstruction: Add new id column
    op.add_column("agentinstruction", sa.Column("id", sa.BigInteger(), nullable=True))
    op.execute("CREATE SEQUENCE agentinstruction_id_seq")
    op.execute("ALTER TABLE agentinstruction ALTER COLUMN id SET DEFAULT nextval('agentinstruction_id_seq')")
    op.execute("SELECT setval('agentinstruction_id_seq', 1)")
    op.execute("UPDATE agentinstruction SET id = nextval('agentinstruction_id_seq') WHERE id IS NULL")
    op.alter_column("agentinstruction", "id", nullable=False)

    # AgentConnection: Add new id column
    op.add_column("agentconnection", sa.Column("id", sa.BigInteger(), nullable=True))
    op.execute("CREATE SEQUENCE agentconnection_id_seq")
    op.execute("ALTER TABLE agentconnection ALTER COLUMN id SET DEFAULT nextval('agentconnection_id_seq')")
    op.execute("SELECT setval('agentconnection_id_seq', 1)")
    op.execute("UPDATE agentconnection SET id = nextval('agentconnection_id_seq') WHERE id IS NULL")
    op.alter_column("agentconnection", "id", nullable=False)

    # Step 2: Drop foreign key constraints that reference old primary keys
    op.drop_constraint("agentinstruction_session_id_fkey", "agentinstruction", type_="foreignkey")
    op.drop_constraint("agentconnection_session_id_fkey", "agentconnection", type_="foreignkey")
    op.drop_constraint(
        "agentinstructionacknowledgement_instruction_id_fkey", "agentinstructionacknowledgement", type_="foreignkey"
    )

    # Step 3: Drop old primary key constraints
    op.drop_constraint("agentsession_pkey", "agentsession", type_="primary")
    op.drop_constraint("agentinstruction_pkey", "agentinstruction", type_="primary")
    op.drop_constraint("agentconnection_pkey", "agentconnection", type_="primary")

    # Step 4: Create new primary key constraints on the id columns
    op.create_primary_key("agentsession_pkey", "agentsession", ["id"])
    op.create_primary_key("agentinstruction_pkey", "agentinstruction", ["id"])
    op.create_primary_key("agentconnection_pkey", "agentconnection", ["id"])

    # Step 5: Create unique constraints on the old primary key columns for backward compatibility
    op.create_unique_constraint("uq_agentsession_session_id", "agentsession", ["session_id"])
    op.create_unique_constraint("uq_agentinstruction_instruction_id", "agentinstruction", ["instruction_id"])
    op.create_unique_constraint("uq_agentconnection_connection_id", "agentconnection", ["connection_id"])

    # Step 6: Recreate foreign key constraints
    op.create_foreign_key(
        "agentinstruction_session_id_fkey",
        "agentinstruction",
        "agentsession",
        ["session_id"],
        ["session_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "agentconnection_session_id_fkey",
        "agentconnection",
        "agentsession",
        ["session_id"],
        ["session_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "agentinstructionacknowledgement_instruction_id_fkey",
        "agentinstructionacknowledgement",
        "agentinstruction",
        ["instruction_id"],
        ["instruction_id"],
        ondelete="CASCADE",
    )

    # Step 7: Add indexes for the new primary keys (PostgreSQL creates these automatically, but explicit is better)
    op.create_index("idx_agentsession_id", "agentsession", ["id"], unique=False)
    op.create_index("idx_agentinstruction_id", "agentinstruction", ["id"], unique=False)
    op.create_index("idx_agentconnection_id", "agentconnection", ["id"], unique=False)


def downgrade() -> None:
    # Step 1: Drop new indexes
    op.drop_index("idx_agentconnection_id", table_name="agentconnection")
    op.drop_index("idx_agentinstruction_id", table_name="agentinstruction")
    op.drop_index("idx_agentsession_id", table_name="agentsession")

    # Step 2: Drop foreign key constraints
    op.drop_constraint(
        "agentinstructionacknowledgement_instruction_id_fkey", "agentinstructionacknowledgement", type_="foreignkey"
    )
    op.drop_constraint("agentconnection_session_id_fkey", "agentconnection", type_="foreignkey")
    op.drop_constraint("agentinstruction_session_id_fkey", "agentinstruction", type_="foreignkey")

    # Step 3: Drop unique constraints on old primary key columns
    op.drop_constraint("uq_agentconnection_connection_id", "agentconnection", type_="unique")
    op.drop_constraint("uq_agentinstruction_instruction_id", "agentinstruction", type_="unique")
    op.drop_constraint("uq_agentsession_session_id", "agentsession", type_="unique")

    # Step 4: Drop new primary key constraints
    op.drop_constraint("agentconnection_pkey", "agentconnection", type_="primary")
    op.drop_constraint("agentinstruction_pkey", "agentinstruction", type_="primary")
    op.drop_constraint("agentsession_pkey", "agentsession", type_="primary")

    # Step 5: Restore old primary key constraints
    op.create_primary_key("agentsession_pkey", "agentsession", ["session_id"])
    op.create_primary_key("agentinstruction_pkey", "agentinstruction", ["instruction_id"])
    op.create_primary_key("agentconnection_pkey", "agentconnection", ["connection_id"])

    # Step 6: Restore foreign key constraints
    op.create_foreign_key(
        "agentinstruction_session_id_fkey",
        "agentinstruction",
        "agentsession",
        ["session_id"],
        ["session_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "agentconnection_session_id_fkey",
        "agentconnection",
        "agentsession",
        ["session_id"],
        ["session_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "agentinstructionacknowledgement_instruction_id_fkey",
        "agentinstructionacknowledgement",
        "agentinstruction",
        ["instruction_id"],
        ["instruction_id"],
        ondelete="CASCADE",
    )

    # Step 7: Drop the new id columns and sequences
    op.drop_column("agentconnection", "id")
    op.drop_column("agentinstruction", "id")
    op.drop_column("agentsession", "id")

    op.execute("DROP SEQUENCE IF EXISTS agentconnection_id_seq CASCADE")
    op.execute("DROP SEQUENCE IF EXISTS agentinstruction_id_seq CASCADE")
    op.execute("DROP SEQUENCE IF EXISTS agentsession_id_seq CASCADE")
