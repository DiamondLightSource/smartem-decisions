from logging.config import fileConfig

from alembic import context
from sqlalchemy import TypeDecorator

from smartem_backend.model.database import SQLModel
from smartem_backend.utils import setup_postgres_connection

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLModel metadata for autogenerate support
target_metadata = SQLModel.metadata


def get_url():
    """Get database URL from existing connection setup"""
    engine = setup_postgres_connection()
    return str(engine.url)


def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    """
    Compare types for autogenerate, ignoring TypeDecorator wrappers.

    TypeDecorators like ModelLevelType wrap base SQL types (VARCHAR) without
    changing the actual database schema. We ignore these differences to prevent
    false positives in schema drift detection.

    Returns:
        False if types are considered the same (no migration needed)
        True if types are different (migration needed)
        None to use default comparison logic
    """
    # If the metadata type is a TypeDecorator, unwrap it and compare the impl types
    if isinstance(metadata_type, TypeDecorator):
        # TypeDecorators wrap base SQL types - we should consider them equal
        # to their underlying implementation type to avoid false schema drift
        return False

    # Use default comparison for other cases
    return None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_type,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Use existing connection setup
    connectable = setup_postgres_connection()

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=compare_type)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
