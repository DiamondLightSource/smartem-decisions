# Database Migrations

This guide explains how to use database migrations in the smartem-decisions project.

## Overview

We use [Alembic](https://alembic.sqlalchemy.org/) for database schema versioning and migrations. Alembic integrates with our SQLModel-based database models to provide:

- **Schema versioning**: Track database changes over time
- **Automated migration generation**: Generate migrations from model changes
- **Rollback support**: Safely revert database changes
- **Environment-specific deployments**: Apply migrations across development, staging, and production

## Prerequisites

Ensure you have the backend dependencies installed:

```bash
pip install -e .[backend]
```

This includes Alembic as a dependency.

## Basic Usage

### Running Migrations

Apply all pending migrations to bring your database up to the latest schema:

```bash
alembic upgrade head
```

### Checking Migration Status

See the current database version:

```bash
alembic current
```

View migration history:

```bash
alembic history --verbose
```

### Rolling Back Migrations

Downgrade to a specific revision:

```bash
alembic downgrade <revision_id>
```

Rollback one migration:

```bash
alembic downgrade -1
```

## Creating New Migrations

### Auto-generating Migrations

When you modify SQLModel classes in `src/smartem_backend/model/database.py`, generate a migration automatically:

```bash
alembic revision --autogenerate -m "Add new field to Grid model"
```

**Important**: Always review auto-generated migrations before applying them. Alembic may not detect all changes (like column renames or complex constraints).

### Manual Migrations

For data migrations or complex schema changes, create an empty migration:

```bash
alembic revision -m "Seed initial user data"
```

Edit the generated file in `src/smartem_backend/migrations/versions/` to add your custom logic.

## Migration Examples

### Structure Changes

```python
def upgrade() -> None:
    op.create_table('user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('preference_key', sa.String(255), nullable=False),
        sa.Column('preference_value', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('user_preferences')
```

### Index Changes

```python
def upgrade() -> None:
    op.create_index(
        'idx_gridsquare_acquisition_datetime_status',
        'gridsquare',
        ['acquisition_datetime', 'status'],
        postgresql_using='btree'
    )

def downgrade() -> None:
    op.drop_index('idx_gridsquare_acquisition_datetime_status')
```

### Data Changes

```python
from sqlalchemy.sql import table, column

def upgrade() -> None:
    user_preferences = table('user_preferences',
        column('user_id', sa.String),
        column('preference_key', sa.String),
        column('preference_value', sa.JSON)
    )
    
    op.bulk_insert(user_preferences, [
        {
            'user_id': 'system',
            'preference_key': 'default_settings',
            'preference_value': {'theme': 'light', 'page_size': 50}
        }
    ])

def downgrade() -> None:
    op.execute("DELETE FROM user_preferences WHERE user_id = 'system'")
```

## Best Practices

### Migration Safety

1. **Always backup production data** before running migrations
2. **Test migrations** on a copy of production data first
3. **Review auto-generated migrations** carefully before applying
4. **Write reversible migrations** with proper downgrade logic

### Schema Changes

1. **Add columns as nullable first**, then make them non-nullable in a separate migration if needed
2. **Use separate migrations** for structure and data changes
3. **Include appropriate indexes** for performance-critical fields
4. **Document breaking changes** in migration comments

### Development Workflow

1. **Create feature branch** for database changes
2. **Generate migration** after modifying models
3. **Test migration** locally (up and down)
4. **Review migration code** before committing
5. **Coordinate with team** for schema changes affecting multiple developers

## Deployment

### Production Deployment

```bash
# 1. Backup database
pg_dump smartem_production > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Apply migrations
alembic upgrade head

# 3. Verify application works
# 4. Clean up old backups (optional)
```

### Staging Environment

```bash
# Apply migrations to staging first
alembic upgrade head

# Test application functionality
# Run integration tests
```

## Troubleshooting

### Common Issues

**Migration conflicts**: When multiple developers create migrations simultaneously:
```bash
# Resolve by creating a merge migration
alembic merge <rev1> <rev2> -m "Merge migrations"
```

**Failed migration**: If a migration fails partway through:
```bash
# Check current state
alembic current

# Fix data/schema issues manually
# Mark migration as complete (if safe)
alembic stamp <revision_id>
```

**Model out of sync**: When models don't match database:
```bash
# Generate migration to sync
alembic revision --autogenerate -m "Sync models with database"
```

### Database Connection Issues

The migration system uses your existing database connection configuration from `smartem_backend.utils.setup_postgres_connection()`.

Ensure your environment variables are set:
- Database connection parameters
- PostgreSQL credentials
- Network access to database server

## Files and Structure

```
├── alembic.ini                              # Alembic configuration
├── src/smartem_backend/migrations/
│   ├── env.py                              # Migration environment
│   ├── script.py.mako                      # Migration template
│   └── versions/                           # Individual migration files
│       ├── 001_add_user_preferences.py
│       ├── 002_add_acquisition_time_index.py
│       └── 003_seed_system_config.py
```

## Further Reading

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
