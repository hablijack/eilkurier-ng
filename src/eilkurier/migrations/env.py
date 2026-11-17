from alembic import context
from sqlalchemy import engine_from_config, pool

from eilkurier.db import Base
from eilkurier.settings import get_settings

config = context.config
config.set_main_option(
    "sqlalchemy.url", config.get_main_option("sqlalchemy.url") or get_settings().database_url
)


def run() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run()
