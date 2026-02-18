import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# Import models directly without triggering src/__init__.py (which imports tasks/pipeline)
# This avoids the textstat import chain during migrations
import importlib.util
_models_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "packages",
    "shared-python",
    "vip_shared",
    "db",
    "models.py",
)
_spec = importlib.util.spec_from_file_location("models", _models_path)
_models = importlib.util.module_from_spec(_spec)
sys.modules["_alembic_models"] = _models
_spec.loader.exec_module(_models)
SQLModel = _models.SQLModel


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def get_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        raise RuntimeError("Alembic config section missing")

    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _ensure_alembic_version_column_capacity(connection)
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


def _ensure_alembic_version_column_capacity(connection) -> None:
    """
    Backward-compatibility guard:
    some environments have alembic_version.version_num as VARCHAR(32),
    which breaks longer revision IDs.
    """
    try:
        length_query = text(
            """
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'alembic_version'
              AND column_name = 'version_num'
              AND table_schema = current_schema()
            """
        )
        max_len = connection.execute(length_query).scalar_one_or_none()
        if isinstance(max_len, int) and max_len < 64:
            connection.execute(
                text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")
            )
    except Exception:
        # Keep migrations best-effort across fresh databases or restricted metadata access.
        pass


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
