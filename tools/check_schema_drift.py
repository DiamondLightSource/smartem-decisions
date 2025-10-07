#!/usr/bin/env python3
"""
Schema drift detection script for SmartEM Decisions.

This script detects when SQLModel definitions have changed but corresponding
Alembic migrations haven't been created. It uses a temporary database to
compare the current state with what would be generated from models.

Usage:
    python tools/check_schema_drift.py

Exit codes:
    0: No schema drift detected
    1: Schema drift detected or script error
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Add project root to Python path to import smartem modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from smartem_backend.model.database import *  # noqa: E402, F403, F401


def setup_test_database() -> str:
    """
    Create a temporary PostgreSQL database for testing.

    Returns:
        Database URL for the temporary database
    """
    load_dotenv(dotenv_path=project_root / ".dev.env", override=False)

    # Get PostgreSQL connection details from environment
    required_vars = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    env_vars = {}
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            print(f"Error: Environment variable {var} not set", file=sys.stderr)
            sys.exit(1)
        env_vars[var] = value

    # Generate unique temporary database name
    temp_db_name = f"schema_drift_test_{os.getpid()}"

    # Create temporary database
    admin_url = (
        f"postgresql://{env_vars['POSTGRES_USER']}:{env_vars['POSTGRES_PASSWORD']}@"
        f"{env_vars['POSTGRES_HOST']}:{env_vars['POSTGRES_PORT']}/postgres"
    )

    try:
        # Connect to PostgreSQL server to create test database
        conn = psycopg2.connect(admin_url)
        conn.autocommit = True
        try:
            with conn.cursor() as cursor:
                cursor.execute(f'CREATE DATABASE "{temp_db_name}"')
        finally:
            conn.close()

        # Return URL for the temporary database
        return (
            f"postgresql://{env_vars['POSTGRES_USER']}:{env_vars['POSTGRES_PASSWORD']}@"
            f"{env_vars['POSTGRES_HOST']}:{env_vars['POSTGRES_PORT']}/{temp_db_name}"
        )

    except psycopg2.Error as e:
        print(f"Error creating temporary database: {e}", file=sys.stderr)
        sys.exit(1)


def cleanup_test_database(db_url: str) -> None:
    """
    Drop the temporary database.

    Args:
        db_url: Database URL of the temporary database to drop
    """
    # Extract database name from URL
    db_name = db_url.split("/")[-1]
    admin_url = "/".join(db_url.split("/")[:-1]) + "/postgres"

    try:
        conn = psycopg2.connect(admin_url)
        conn.autocommit = True
        try:
            with conn.cursor() as cursor:
                # Terminate connections to the test database
                cursor.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}'")
                cursor.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        finally:
            conn.close()

    except psycopg2.Error as e:
        print(f"Warning: Could not clean up temporary database {db_name}: {e}", file=sys.stderr)


def run_existing_migrations(db_url: str) -> None:
    """
    Run existing Alembic migrations on the temporary database.

    Args:
        db_url: Database URL for the temporary database
    """
    # Set environment variable for Alembic to use our temporary database
    env = os.environ.copy()

    # Create temporary alembic.ini with our database URL
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
        alembic_ini_path = f.name

        # Read the original alembic.ini and replace the database URL
        original_ini = project_root / "alembic.ini"
        with open(original_ini) as orig_f:
            content = orig_f.read()

        # Replace the placeholder URL with our temporary database URL
        content = content.replace("driver://user:pass@localhost/dbname", db_url)
        f.write(content)

    try:
        # Run migrations
        result = subprocess.run(
            ["alembic", "-c", alembic_ini_path, "upgrade", "head"],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print("Error running existing migrations:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            sys.exit(1)

        print("✓ Existing migrations applied successfully")

    finally:
        # Clean up temporary alembic.ini
        os.unlink(alembic_ini_path)


def check_for_new_migrations(db_url: str) -> bool:
    """
    Check if autogenerate would create new migrations.

    Args:
        db_url: Database URL for the temporary database

    Returns:
        True if schema drift detected (new migrations would be created)
    """
    env = os.environ.copy()

    # Create temporary alembic.ini with our database URL
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
        alembic_ini_path = f.name

        # Read the original alembic.ini and replace the database URL
        original_ini = project_root / "alembic.ini"
        with open(original_ini) as orig_f:
            content = orig_f.read()

        # Replace the placeholder URL with our temporary database URL
        content = content.replace("driver://user:pass@localhost/dbname", db_url)
        f.write(content)

    try:
        # Run autogenerate in dry-run mode to see what would be generated
        result = subprocess.run(
            ["alembic", "-c", alembic_ini_path, "revision", "--autogenerate", "-m", "test_drift_check", "--sql"],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print("Error running autogenerate check:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return True  # Treat errors as potential drift

        # Check if any actual changes would be generated
        # Look for SQL operations that aren't just comments
        output_lines = result.stdout.split("\n")
        has_operations = False

        for line in output_lines:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("--"):
                continue
            # Look for actual SQL operations
            if any(keyword in line.upper() for keyword in ["CREATE", "ALTER", "DROP", "ADD", "MODIFY"]):
                has_operations = True
                break

        return has_operations

    finally:
        # Clean up temporary alembic.ini
        os.unlink(alembic_ini_path)


def main() -> None:
    """Main function to check for schema drift."""
    print("   Checking for database schema drift...")
    print()

    # Ensure we're in the project root
    os.chdir(project_root)

    # Create temporary database
    print("📅 Setting up temporary database...")
    db_url = setup_test_database()

    try:
        # Run existing migrations
        print("Applying existing migrations...")
        run_existing_migrations(db_url)

        # Check for drift
        print("   Checking for schema drift...")
        has_drift = check_for_new_migrations(db_url)

        if has_drift:
            print()
            print("SCHEMA DRIFT DETECTED!")
            print()
            print("Your SQLModel definitions have changed but migrations haven't been updated.")
            print("This means the database schema is out of sync with your model definitions.")
            print()
            print("To fix this:")
            print("1. Run: alembic revision --autogenerate -m 'description of changes'")
            print("2. Review the generated migration file")
            print("3. Test the migration: alembic upgrade head")
            print("4. Commit the new migration file")
            print()
            sys.exit(1)
        else:
            print("No schema drift detected - database schema is in sync!")
            print()

    finally:
        # Clean up
        print("🧹 Cleaning up temporary database...")
        cleanup_test_database(db_url)


if __name__ == "__main__":
    main()
