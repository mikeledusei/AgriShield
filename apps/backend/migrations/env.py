"""Run migrations against the configured SQLAlchemy database."""
from logging.config import fileConfig
from alembic import context
from database.connection import engine, Base
from database import models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
if engine is None:
    raise RuntimeError('DATABASE_URL is required for migrations')
if context.is_offline_mode():
    context.configure(url=str(engine.url), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
