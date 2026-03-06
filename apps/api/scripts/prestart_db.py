from __future__ import annotations

import os
from sqlalchemy import create_engine, text


def _normalized_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def main() -> None:
    url = _normalized_database_url()
    engine = create_engine(url, future=True)

    with engine.begin() as conn:
        # Legacy compatibility: old environments can have VARCHAR(32) here.
        version_len = conn.execute(
            text(
                """
                SELECT character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'alembic_version'
                  AND column_name = 'version_num'
                  AND table_schema = current_schema()
                """
            )
        ).scalar_one_or_none()

        if isinstance(version_len, int) and version_len < 64:
            conn.execute(
                text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")
            )
            print("prestart_db: widened alembic_version.version_num to VARCHAR(64)")

        # Defensive self-heal for environments where app code expects the column.
        # Phase 16: keep historical data but stop forcing default mode on new rows.
        conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS comparison_jobs
                ADD COLUMN IF NOT EXISTS output_mode VARCHAR(20)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS comparison_jobs
                ALTER COLUMN output_mode DROP DEFAULT
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS comparison_jobs
                ALTER COLUMN output_mode DROP NOT NULL
                """
            )
        )
        print("prestart_db: ensured comparison_jobs.output_mode")

        # Auth schema compatibility: OTP verify path reads these user fields.
        conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS users
                ADD COLUMN IF NOT EXISTS role VARCHAR(20)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS users
                ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP NULL
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS users
                ADD COLUMN IF NOT EXISTS last_login_ip VARCHAR(45) NULL
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS users
                ADD COLUMN IF NOT EXISTS login_method VARCHAR(50) NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE users
                SET role = 'member'
                WHERE role IS NULL OR role = ''
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS users
                ALTER COLUMN role SET DEFAULT 'member'
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS users
                ALTER COLUMN role SET NOT NULL
                """
            )
        )
        print("prestart_db: ensured users auth columns (role/login metadata)")


if __name__ == "__main__":
    main()
