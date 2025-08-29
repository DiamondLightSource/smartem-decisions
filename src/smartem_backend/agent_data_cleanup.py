"""
Data retention and cleanup utilities for agent communication system.

Provides functions to manage data lifecycle for scientific data compliance:
- Cleanup old agent connections and stale data
- Archive completed sessions with configurable retention policies
- Maintain audit trails while managing storage growth
- Support regulatory compliance for scientific research data
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, text
from sqlmodel import Session, select

from smartem_backend.model.database import (
    AgentConnection,
    AgentInstruction,
    AgentInstructionAcknowledgement,
    AgentSession,
)
from smartem_backend.utils import setup_postgres_connection

logger = logging.getLogger(__name__)


class AgentDataRetentionPolicy:
    """Configuration for agent data retention policies."""

    def __init__(
        self,
        connection_cleanup_hours: int = 24,
        instruction_retention_days: int = 30,
        completed_session_retention_days: int = 90,
        acknowledgement_retention_days: int = 365,
        batch_size: int = 1000,
    ):
        """
        Initialize retention policy configuration.

        Args:
            connection_cleanup_hours: Hours to keep stale connections before cleanup
            instruction_retention_days: Days to retain instruction history
            completed_session_retention_days: Days to retain completed session data
            acknowledgement_retention_days: Days to retain acknowledgement audit trail
            batch_size: Number of records to process in each cleanup batch
        """
        self.connection_cleanup_hours = connection_cleanup_hours
        self.instruction_retention_days = instruction_retention_days
        self.completed_session_retention_days = completed_session_retention_days
        self.acknowledgement_retention_days = acknowledgement_retention_days
        self.batch_size = batch_size

    @classmethod
    def scientific_compliance(cls) -> "AgentDataRetentionPolicy":
        """
        Return a conservative retention policy suitable for scientific research compliance.

        Scientific research often requires longer retention periods for reproducibility
        and audit requirements.
        """
        return cls(
            connection_cleanup_hours=48,
            instruction_retention_days=365,
            completed_session_retention_days=730,  # 2 years
            acknowledgement_retention_days=2555,  # 7 years (common compliance requirement)
            batch_size=500,
        )

    @classmethod
    def development(cls) -> "AgentDataRetentionPolicy":
        """Return a shorter retention policy suitable for development environments."""
        return cls(
            connection_cleanup_hours=4,
            instruction_retention_days=7,
            completed_session_retention_days=14,
            acknowledgement_retention_days=30,
            batch_size=1000,
        )


class AgentDataCleanupService:
    """Service for managing agent communication data lifecycle and cleanup."""

    def __init__(self, session: Session, policy: AgentDataRetentionPolicy | None = None):
        """
        Initialize cleanup service.

        Args:
            session: Database session for cleanup operations
            policy: Retention policy configuration (defaults to scientific compliance)
        """
        self.session = session
        self.policy = policy or AgentDataRetentionPolicy.scientific_compliance()

    def cleanup_stale_connections(self) -> dict[str, int]:
        """
        Clean up stale agent connections that haven't had heartbeats recently.

        Returns:
            Dictionary with cleanup statistics
        """
        cutoff_time = datetime.now() - timedelta(hours=self.policy.connection_cleanup_hours)

        # Find stale connections
        stale_query = select(AgentConnection).where(
            and_(
                AgentConnection.status == "active",
                AgentConnection.last_heartbeat_at < cutoff_time,
            )
        )

        stale_connections = self.session.exec(stale_query).all()
        cleaned_count = 0

        for conn in stale_connections:
            # Mark as closed rather than deleting for audit trail
            conn.status = "timeout"
            conn.closed_at = datetime.now()
            conn.close_reason = f"Stale connection cleanup after {self.policy.connection_cleanup_hours}h"
            cleaned_count += 1

            if cleaned_count % self.policy.batch_size == 0:
                self.session.commit()
                logger.info(f"Marked {cleaned_count} stale connections as closed")

        self.session.commit()

        logger.info(f"Cleanup completed: {cleaned_count} stale connections marked as closed")
        return {
            "stale_connections_closed": cleaned_count,
            "cutoff_time": cutoff_time.isoformat(),
        }

    def cleanup_old_instructions(self) -> dict[str, int]:
        """
        Clean up old instruction records beyond retention period.

        Maintains acknowledgement audit trail while removing instruction payload data.
        """
        cutoff_time = datetime.now() - timedelta(days=self.policy.instruction_retention_days)

        # Find old instructions that can be archived
        old_instructions_query = select(AgentInstruction).where(
            and_(
                AgentInstruction.created_at < cutoff_time,
                AgentInstruction.status.in_(["completed", "failed", "expired"]),
            )
        )

        old_instructions = self.session.exec(old_instructions_query).all()
        archived_count = 0
        deleted_count = 0

        for instruction in old_instructions:
            # Check if this instruction has acknowledgements (preserve audit trail)
            ack_query = select(AgentInstructionAcknowledgement).where(
                AgentInstructionAcknowledgement.instruction_id == instruction.instruction_id
            )
            has_acknowledgements = self.session.exec(ack_query).first() is not None

            if has_acknowledgements:
                # Archive: clear sensitive payload but keep metadata for audit trail
                instruction.payload = {"archived": True, "archived_at": datetime.now().isoformat()}
                instruction.metadata = {
                    **(instruction.metadata or {}),
                    "archived": True,
                    "original_payload_size": len(str(instruction.payload)),
                }
                archived_count += 1
            else:
                # Safe to delete instructions without acknowledgements
                self.session.delete(instruction)
                deleted_count += 1

            if (archived_count + deleted_count) % self.policy.batch_size == 0:
                self.session.commit()
                logger.info(f"Processed {archived_count + deleted_count} old instructions")

        self.session.commit()

        logger.info(f"Instruction cleanup completed: {archived_count} archived, {deleted_count} deleted")
        return {
            "instructions_archived": archived_count,
            "instructions_deleted": deleted_count,
            "cutoff_time": cutoff_time.isoformat(),
        }

    def cleanup_completed_sessions(self) -> dict[str, int]:
        """
        Clean up old completed sessions beyond retention period.

        Maintains session metadata but removes detailed experimental parameters.
        """
        cutoff_time = datetime.now() - timedelta(days=self.policy.completed_session_retention_days)

        # Find old completed sessions
        old_sessions_query = select(AgentSession).where(
            and_(
                AgentSession.ended_at.isnot(None),
                AgentSession.ended_at < cutoff_time,
                AgentSession.status.in_(["completed", "terminated", "error"]),
            )
        )

        old_sessions = self.session.exec(old_sessions_query).all()
        archived_count = 0

        for session in old_sessions:
            # Archive sensitive experimental parameters
            if session.experimental_parameters:
                archived_params = {
                    "archived": True,
                    "archived_at": datetime.now().isoformat(),
                    "parameter_count": len(session.experimental_parameters),
                }
                session.experimental_parameters = archived_params
                archived_count += 1

            if archived_count % self.policy.batch_size == 0:
                self.session.commit()
                logger.info(f"Archived {archived_count} completed sessions")

        self.session.commit()

        logger.info(f"Session cleanup completed: {archived_count} sessions archived")
        return {
            "sessions_archived": archived_count,
            "cutoff_time": cutoff_time.isoformat(),
        }

    def cleanup_old_acknowledgements(self) -> dict[str, int]:
        """
        Clean up very old acknowledgement records beyond regulatory retention period.

        This should be used carefully as it affects audit trail completeness.
        """
        cutoff_time = datetime.now() - timedelta(days=self.policy.acknowledgement_retention_days)

        # Count acknowledgements to be deleted
        count_query = select(AgentInstructionAcknowledgement).where(
            AgentInstructionAcknowledgement.created_at < cutoff_time
        )
        old_acknowledgements = self.session.exec(count_query).all()

        deleted_count = 0
        for ack in old_acknowledgements:
            self.session.delete(ack)
            deleted_count += 1

            if deleted_count % self.policy.batch_size == 0:
                self.session.commit()
                logger.info(f"Deleted {deleted_count} old acknowledgements")

        self.session.commit()

        logger.warning(
            f"Acknowledgement cleanup completed: {deleted_count} records deleted (affects audit trail completeness)"
        )
        return {
            "acknowledgements_deleted": deleted_count,
            "cutoff_time": cutoff_time.isoformat(),
        }

    def run_full_cleanup(self) -> dict[str, any]:
        """
        Run complete cleanup process across all agent communication data.

        Returns:
            Dictionary with comprehensive cleanup statistics
        """
        logger.info("Starting full agent data cleanup process")
        start_time = datetime.now()

        results = {}
        try:
            # Run cleanup in order of increasing importance/sensitivity
            results["connections"] = self.cleanup_stale_connections()
            results["instructions"] = self.cleanup_old_instructions()
            results["sessions"] = self.cleanup_completed_sessions()

            # Only cleanup acknowledgements if explicitly configured (affects audit trail)
            if self.policy.acknowledgement_retention_days < 2555:  # Less than 7 years
                logger.warning("Cleaning up acknowledgements - this affects scientific audit trail")
                results["acknowledgements"] = self.cleanup_old_acknowledgements()

        except Exception as e:
            logger.error(f"Error during cleanup process: {e}")
            self.session.rollback()
            raise

        end_time = datetime.now()
        duration = end_time - start_time

        results["summary"] = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration.total_seconds(),
            "policy": {
                "connection_cleanup_hours": self.policy.connection_cleanup_hours,
                "instruction_retention_days": self.policy.instruction_retention_days,
                "session_retention_days": self.policy.completed_session_retention_days,
                "acknowledgement_retention_days": self.policy.acknowledgement_retention_days,
            },
        }

        logger.info(f"Full cleanup completed in {duration.total_seconds():.2f} seconds")
        return results

    def get_data_usage_statistics(self) -> dict[str, any]:
        """
        Get current data usage statistics for agent communication tables.

        Returns:
            Dictionary with storage and record count statistics
        """
        stats = {}

        # Get record counts
        stats["record_counts"] = {
            "sessions": len(self.session.exec(select(AgentSession)).all()),
            "instructions": len(self.session.exec(select(AgentInstruction)).all()),
            "connections": len(self.session.exec(select(AgentConnection)).all()),
            "acknowledgements": len(self.session.exec(select(AgentInstructionAcknowledgement)).all()),
        }

        # Get table sizes using PostgreSQL system tables
        try:
            size_query = text("""
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables
                WHERE tablename IN ('agentsession', 'agentinstruction', 'agentconnection',
                                    'agentinstructionacknowledgement')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
            """)

            result = self.session.execute(size_query)
            table_sizes = []
            total_bytes = 0

            for row in result:
                table_info = {
                    "table": row[1],
                    "size_human": row[2],
                    "size_bytes": row[3],
                }
                table_sizes.append(table_info)
                total_bytes += row[3]

            stats["table_sizes"] = table_sizes
            stats["total_size_bytes"] = total_bytes

        except Exception as e:
            logger.error(f"Could not retrieve table size statistics: {e}")
            stats["table_sizes"] = "unavailable"

        # Get oldest records
        try:
            oldest_session = self.session.exec(select(AgentSession).order_by(AgentSession.created_at).limit(1)).first()
            oldest_instruction = self.session.exec(
                select(AgentInstruction).order_by(AgentInstruction.created_at).limit(1)
            ).first()

            stats["oldest_records"] = {
                "session": oldest_session.created_at.isoformat() if oldest_session else None,
                "instruction": oldest_instruction.created_at.isoformat() if oldest_instruction else None,
            }
        except Exception as e:
            logger.error(f"Could not retrieve oldest record statistics: {e}")
            stats["oldest_records"] = "unavailable"

        return stats


def main():
    """CLI entry point for agent data cleanup operations."""
    import argparse

    parser = argparse.ArgumentParser(description="Agent communication data cleanup utility")
    parser.add_argument(
        "--policy",
        choices=["scientific", "development"],
        default="scientific",
        help="Retention policy to use",
    )
    parser.add_argument(
        "--operation",
        choices=["cleanup", "stats", "connections", "instructions", "sessions"],
        default="stats",
        help="Operation to perform",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned up without making changes",
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Create database session
    engine = setup_postgres_connection()
    with Session(engine) as session:
        # Select policy
        if args.policy == "development":
            policy = AgentDataRetentionPolicy.development()
        else:
            policy = AgentDataRetentionPolicy.scientific_compliance()

        cleanup_service = AgentDataCleanupService(session, policy)

        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")

        # Execute requested operation
        if args.operation == "stats":
            stats = cleanup_service.get_data_usage_statistics()
            print("Agent Communication Data Statistics:")
            print(f"Record counts: {stats['record_counts']}")
            if "table_sizes" in stats and stats["table_sizes"] != "unavailable":
                print("Table sizes:")
                for table in stats["table_sizes"]:
                    print(f"  {table['table']}: {table['size_human']}")
            if "oldest_records" in stats and stats["oldest_records"] != "unavailable":
                print(f"Oldest records: {stats['oldest_records']}")

        elif args.operation == "cleanup":
            if args.dry_run:
                logger.info("Would run full cleanup with policy: %s", args.policy)
            else:
                results = cleanup_service.run_full_cleanup()
                print("Cleanup Results:")
                for category, result in results.items():
                    print(f"{category}: {result}")

        elif args.operation == "connections":
            if args.dry_run:
                logger.info("Would cleanup stale connections")
            else:
                result = cleanup_service.cleanup_stale_connections()
                print(f"Connection cleanup: {result}")

        elif args.operation == "instructions":
            if args.dry_run:
                logger.info("Would cleanup old instructions")
            else:
                result = cleanup_service.cleanup_old_instructions()
                print(f"Instruction cleanup: {result}")

        elif args.operation == "sessions":
            if args.dry_run:
                logger.info("Would cleanup completed sessions")
            else:
                result = cleanup_service.cleanup_completed_sessions()
                print(f"Session cleanup: {result}")


if __name__ == "__main__":
    main()
