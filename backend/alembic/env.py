import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context
from dotenv import load_dotenv

# Add backend/ to path so "from app.xxx" imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load .env from the backend/ directory into os.environ BEFORE anything else
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(_env_path)

from app.database import Base
from app import models  # noqa: F401 — registers all models with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ─── Build the migration URL ──────────────────────────────────────────────────
# Use the direct (non-pooler) URL — pooler connections break DDL migrations.
_raw_url = os.getenv("DATABASE_DIRECT_URL") or os.getenv("DATABASE_URL")
if not _raw_url:
    raise RuntimeError(
        "No database URL found. Set DATABASE_DIRECT_URL or DATABASE_URL in backend/.env"
    )

# SQLAlchemy needs the psycopg3 dialect prefix
_migration_url = (
    _raw_url
    .replace("postgresql://", "postgresql+psycopg://", 1)
    .replace("postgres://", "postgresql+psycopg://", 1)
)


def run_migrations_offline() -> None:
    context.configure(
        url=_migration_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Build engine directly so we control the URL (not read from alembic.ini)
    connectable = create_engine(_migration_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
