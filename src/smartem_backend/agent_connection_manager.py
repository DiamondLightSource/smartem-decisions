#!/usr/bin/env python3
"""
Agent Connection Management Service

Handles connection health monitoring, instruction expiration, and cleanup
for the SmartEM backend-to-agent communication system.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_
from sqlmodel import Session

from smartem_backend.model.database import AgentConnection, AgentInstruction, AgentSession
from smartem_backend.mq_publisher import publish_agent_instruction_expired
from smartem_backend.utils import get_db_engine


class AgentConnectionManager:
    """
    Manages agent connections, health monitoring, and instruction lifecycle.

    Responsibilities:
    - Monitor connection health and detect stale connections
    - Handle instruction expiration and retry logic
    - Clean up inactive sessions and connections
    - Provide connection statistics and monitoring
    """

    def __init__(self, db_engine=None, check_interval: int = 30):
        """
        Initialize the connection manager.

        Args:
            db_engine: Database engine (defaults to global engine)
            check_interval: How often to run cleanup tasks (seconds)
        """
        self.db_engine = db_engine or get_db_engine()
        self.check_interval = check_interval
        self.logger = logging.getLogger("AgentConnectionManager")
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the connection manager background tasks."""
        if self._running:
            self.logger.warning("Connection manager already running")
            return

        self._running = True
        self.logger.info(f"Starting agent connection manager (check interval: {self.check_interval}s)")

        # Start background monitoring task
        self._task = asyncio.create_task(self._monitoring_loop())

    async def stop(self):
        """Stop the connection manager background tasks."""
        if not self._running:
            return

        self.logger.info("Stopping agent connection manager")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitoring_loop(self):
        """Main monitoring loop that runs cleanup tasks periodically."""
        while self._running:
            try:
                await self._run_cleanup_tasks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)

    async def _run_cleanup_tasks(self):
        """Run all cleanup and monitoring tasks."""
        await asyncio.gather(
            self._cleanup_stale_connections(),
            self._handle_expired_instructions(),
            self._update_session_activity(),
            return_exceptions=True,
        )

    async def _cleanup_stale_connections(self):
        """Clean up connections that haven't received heartbeats recently."""
        try:
            with Session(self.db_engine) as session:
                # Consider connections stale if no heartbeat for 2 minutes
                stale_threshold = datetime.now() - timedelta(minutes=2)

                stale_connections = (
                    session.query(AgentConnection)
                    .filter(
                        and_(AgentConnection.status == "active", AgentConnection.last_heartbeat_at < stale_threshold)
                    )
                    .all()
                )

                for conn in stale_connections:
                    self.logger.info(f"Marking stale connection {conn.connection_id} as closed")
                    conn.status = "closed"
                    conn.closed_at = datetime.now()
                    conn.close_reason = "stale_connection"

                if stale_connections:
                    session.commit()
                    self.logger.info(f"Cleaned up {len(stale_connections)} stale connections")

        except Exception as e:
            self.logger.error(f"Error cleaning up stale connections: {e}")

    async def _handle_expired_instructions(self):
        """Handle instructions that have expired and need retry or failure logic."""
        try:
            with Session(self.db_engine) as session:
                # Find instructions that have expired
                now = datetime.now()
                expired_instructions = (
                    session.query(AgentInstruction)
                    .filter(
                        and_(
                            AgentInstruction.status.in_(["pending", "sent"]),
                            AgentInstruction.expires_at.is_not(None),
                            AgentInstruction.expires_at <= now,
                        )
                    )
                    .all()
                )

                for instruction in expired_instructions:
                    self.logger.info(
                        f"Processing expired instruction {instruction.instruction_id} "
                        f"(retry {instruction.retry_count}/{instruction.max_retries})"
                    )

                    # Publish expiration event for processing
                    success = publish_agent_instruction_expired(
                        instruction_id=instruction.instruction_id,
                        session_id=instruction.session_id,
                        agent_id=instruction.agent_id,
                        expires_at=instruction.expires_at,
                        retry_count=instruction.retry_count + 1,
                    )

                    if success:
                        # Update retry count immediately
                        instruction.retry_count += 1

                        if instruction.retry_count >= instruction.max_retries:
                            instruction.status = "expired"
                            self.logger.info(
                                f"Instruction {instruction.instruction_id} marked as expired "
                                f"after {instruction.retry_count} retries"
                            )
                        else:
                            # Reset for retry with new expiration time
                            instruction.status = "pending"
                            instruction.expires_at = now + timedelta(minutes=5)  # 5-minute retry window
                            self.logger.info(
                                f"Instruction {instruction.instruction_id} reset for retry "
                                f"({instruction.retry_count}/{instruction.max_retries})"
                            )
                    else:
                        self.logger.error(
                            f"Failed to publish expiration event for instruction {instruction.instruction_id}"
                        )

                if expired_instructions:
                    session.commit()
                    self.logger.info(f"Processed {len(expired_instructions)} expired instructions")

        except Exception as e:
            self.logger.error(f"Error handling expired instructions: {e}")

    async def _update_session_activity(self):
        """Update session activity and mark inactive sessions."""
        try:
            with Session(self.db_engine) as session:
                # Mark sessions inactive if no activity for 1 hour
                inactive_threshold = datetime.now() - timedelta(hours=1)

                inactive_sessions = (
                    session.query(AgentSession)
                    .filter(and_(AgentSession.status == "active", AgentSession.last_activity_at < inactive_threshold))
                    .all()
                )

                for agent_session in inactive_sessions:
                    self.logger.info(f"Marking session {agent_session.session_id} as inactive")
                    agent_session.status = "inactive"

                if inactive_sessions:
                    session.commit()
                    self.logger.info(f"Marked {len(inactive_sessions)} sessions as inactive")

        except Exception as e:
            self.logger.error(f"Error updating session activity: {e}")

    def get_connection_stats(self) -> dict[str, Any]:
        """Get current connection and session statistics."""
        try:
            with Session(self.db_engine) as session:
                # Active connections
                active_connections = session.query(AgentConnection).filter(AgentConnection.status == "active").count()

                # Active sessions
                active_sessions = session.query(AgentSession).filter(AgentSession.status == "active").count()

                # Pending instructions
                pending_instructions = (
                    session.query(AgentInstruction).filter(AgentInstruction.status == "pending").count()
                )

                # Sent but not acknowledged instructions
                sent_instructions = session.query(AgentInstruction).filter(AgentInstruction.status == "sent").count()

                return {
                    "active_connections": active_connections,
                    "active_sessions": active_sessions,
                    "pending_instructions": pending_instructions,
                    "sent_instructions": sent_instructions,
                    "total_instructions_pending": pending_instructions + sent_instructions,
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            self.logger.error(f"Error getting connection stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def create_session(
        self,
        agent_id: str,
        acquisition_uuid: str | None = None,
        name: str | None = None,
        description: str | None = None,
        experimental_parameters: dict | None = None,
    ) -> str:
        """
        Create a new agent session.

        Args:
            agent_id: Unique identifier for the agent
            acquisition_uuid: Associated acquisition UUID (optional)
            name: Session name (optional)
            description: Session description (optional)
            experimental_parameters: Experimental parameters (optional)

        Returns:
            str: Created session ID
        """
        session_id = str(uuid.uuid4())

        try:
            with Session(self.db_engine) as db_session:
                agent_session = AgentSession(
                    session_id=session_id,
                    agent_id=agent_id,
                    acquisition_uuid=acquisition_uuid,
                    name=name or f"Session-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                    description=description,
                    experimental_parameters=experimental_parameters or {},
                    status="active",
                    created_at=datetime.now(),
                    last_activity_at=datetime.now(),
                )
                db_session.add(agent_session)
                db_session.commit()

                self.logger.info(f"Created session {session_id} for agent {agent_id}")
                return session_id

        except Exception as e:
            self.logger.error(f"Error creating session: {e}")
            raise

    def close_session(self, session_id: str) -> bool:
        """
        Close an agent session and clean up associated connections.

        Args:
            session_id: Session ID to close

        Returns:
            bool: True if session was closed successfully
        """
        try:
            with Session(self.db_engine) as session:
                # Mark session as ended
                agent_session = session.query(AgentSession).filter(AgentSession.session_id == session_id).first()
                if agent_session:
                    agent_session.status = "ended"
                    agent_session.ended_at = datetime.now()

                # Close associated connections
                connections = session.query(AgentConnection).filter(AgentConnection.session_id == session_id).all()

                for conn in connections:
                    if conn.status == "active":
                        conn.status = "closed"
                        conn.closed_at = datetime.now()
                        conn.close_reason = "session_closed"

                session.commit()
                self.logger.info(f"Closed session {session_id} and {len(connections)} connections")
                return True

        except Exception as e:
            self.logger.error(f"Error closing session {session_id}: {e}")
            return False


# Global connection manager instance
_connection_manager: AgentConnectionManager | None = None


def get_connection_manager() -> AgentConnectionManager:
    """Get the global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = AgentConnectionManager()
    return _connection_manager


async def start_connection_manager():
    """Start the global connection manager."""
    manager = get_connection_manager()
    await manager.start()


async def stop_connection_manager():
    """Stop the global connection manager."""
    manager = get_connection_manager()
    await manager.stop()
