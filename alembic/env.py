import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# 1. Add your project root to the system path so Alembic can find 'app'
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 2. Import your Base and EVERY model so Alembic can read their structure
import app.models  # noqa: F401  (registers the tables on Base.metadata)
from app.config import DATABASE_URL
from app.database import Base

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging (unless the caller, such as the
# test setup, asked us to leave logging alone).
if config.config_file_name is not None and config.attributes.get(
    "configure_logger", True
):
    fileConfig(config.config_file_name)

# 3. Take the database URL from the environment (see .env.example).
# Alembic's config parser treats "%" specially, so a literal "%" must be doubled.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

# 4. Point Alembic to your model metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
