#!/usr/bin/env python3
"""
Setup test agent and session in database for development/testing.

This script creates an AgentSession record in the database to allow
agent connections with test agent_id and session_id values without
validation errors.

Usage:
    python tools/setup-test-agent-session.py [--agent-id AGENT_ID] [--session-id SESSION_ID]

Examples:
    python tools/setup-test-agent-session.py
    python tools/setup-test-agent-session.py --agent-id test --session-id test
    python tools/setup-test-agent-session.py --agent-id agent-1 --session-id session-123
"""

import argparse
from datetime import datetime

from sqlmodel import Session, select

from smartem_backend.model.database import AgentSession
from smartem_backend.utils import get_db_engine


def setup_agent_session(agent_id: str = "test", session_id: str = "test") -> None:
    """
    Create or update an AgentSession record in the database.

    Args:
        agent_id: The agent identifier (default: "test")
        session_id: The session identifier (default: "test")
    """
    engine = get_db_engine()

    with Session(engine) as db:
        existing_session = db.exec(select(AgentSession).where(AgentSession.session_id == session_id)).first()

        if existing_session:
            print(f"Session '{session_id}' already exists (id={existing_session.id})")
            print(f"  Agent ID: {existing_session.agent_id}")
            print(f"  Status: {existing_session.status}")
            print(f"  Created: {existing_session.created_at}")

            if existing_session.agent_id != agent_id:
                print(f"\nUpdating agent_id from '{existing_session.agent_id}' to '{agent_id}'")
                existing_session.agent_id = agent_id

            if existing_session.status != "active":
                print(f"Updating status from '{existing_session.status}' to 'active'")
                existing_session.status = "active"

            existing_session.last_activity_at = datetime.now()
            db.commit()
            db.refresh(existing_session)
            print("\nSession updated successfully")
        else:
            new_session = AgentSession(
                session_id=session_id,
                agent_id=agent_id,
                name=f"Test session for {agent_id}",
                description="Auto-generated test session for development",
                status="active",
                created_at=datetime.now(),
                started_at=datetime.now(),
                last_activity_at=datetime.now(),
            )

            db.add(new_session)
            db.commit()
            db.refresh(new_session)

            print(f"Created new session '{session_id}' (id={new_session.id})")
            print(f"  Agent ID: {new_session.agent_id}")
            print(f"  Status: {new_session.status}")
            print(f"  Created: {new_session.created_at}")

    print("\nAgent can now connect with:")
    print(f"  --agent-id {agent_id}")
    print(f"  --session-id {session_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Setup test agent and session in database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--agent-id", default="test", help="Agent identifier (default: test)")
    parser.add_argument("--session-id", default="test", help="Session identifier (default: test)")

    args = parser.parse_args()

    try:
        setup_agent_session(agent_id=args.agent_id, session_id=args.session_id)
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure the database is running and migrations are up to date:")
        print("  alembic upgrade head")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
