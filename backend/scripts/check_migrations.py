"""Purpose: Fail when the migrations and the models have drifted apart.

Dependencies: Alembic's schema comparison and app.models.
Used by: CI, after `alembic upgrade head`.

Applying the migrations proves they run. It does not prove they produce the
schema the models describe — a column added to a model but not to a migration
passes every test that builds its schema from the models. This compares the
migrated database against the metadata and reports the difference.

    .venv/bin/python scripts/check_migrations.py
"""

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app import models  # noqa: E402,F401  (registers every table)
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402

#: Alembic reports these even when nothing is wrong.
IGNORED_KINDS = {"remove_index"}


def describe(difference: object) -> str:
    return str(difference)


async def main() -> int:
    engine = create_async_engine(get_settings().async_database_url)

    async with engine.connect() as connection:
        differences = await connection.run_sync(
            lambda sync_connection: compare_metadata(
                MigrationContext.configure(sync_connection), Base.metadata
            )
        )

    await engine.dispose()

    meaningful = [
        difference
        for difference in differences
        if not (isinstance(difference, tuple) and difference[0] in IGNORED_KINDS)
    ]

    if meaningful:
        print("Migrations and models disagree:\n")
        for difference in meaningful:
            print(f"  - {describe(difference)}")
        print(
            "\nAdd a migration for the change, or correct the model. "
            "The deployed database is built by migrations, not by the models."
        )
        return 1

    print("Migrations match the models.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
