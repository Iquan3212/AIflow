"""
Flushes ALL application data from the configured database, preserving
schema/migrations/extensions - for local development/demo use only.

Safety: this script refuses to run unless DATABASE_URL's hostname looks
like a Neon dev branch this project already uses, and it never touches
`alembic_version` or any schema object (no DROP TABLE, no DROP EXTENSION).
It only empties every application data table via TRUNCATE ... CASCADE,
which preserves table structure, columns, indexes, and constraints
exactly as-is - only rows are removed.

The table list is derived from app.models' own SQLAlchemy metadata
(Base.metadata.tables), not a hand-maintained list - a hardcoded list
silently went stale across several phases (billing, buyer marketplace,
AI Workforce observability, team invites all added new tables this
script never learned about, so a "reset" was leaving a dozen tables'
worth of stale data - including every property, project, subscription,
and payment - completely untouched). Deriving it from metadata means a
future model addition can never cause the same silent gap again.

Run: PYTHONPATH=. ./venv/bin/python scripts/reset_dev_database.py --yes-i-am-sure
"""

import sys

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401 - import registers every table on Base.metadata
from app.config import get_settings
from sqlalchemy import text

DATA_TABLES = sorted(Base.metadata.tables.keys())


def main():
    if "--yes-i-am-sure" not in sys.argv:
        print("Refusing to run without --yes-i-am-sure (this deletes ALL application data).")
        sys.exit(1)

    settings = get_settings()
    url = str(engine.url)
    if "neon.tech" not in url:
        print(f"DATABASE_URL host doesn't look like this project's known Neon dev branch: {engine.url.host}")
        print("Refusing to run - update this check if you're sure this is a dev/demo database.")
        sys.exit(1)

    db = SessionLocal()
    try:
        before = {t: db.execute(text(f'SELECT count(*) FROM "{t}"')).scalar() for t in DATA_TABLES}
        quoted = ", ".join(f'"{t}"' for t in DATA_TABLES)
        db.execute(text(f"TRUNCATE TABLE {quoted} CASCADE"))
        db.commit()
        after = {t: db.execute(text(f'SELECT count(*) FROM "{t}"')).scalar() for t in DATA_TABLES}
    finally:
        db.close()

    print(f"Flushed {len(DATA_TABLES)} tables. Row counts before -> after:")
    for t in DATA_TABLES:
        print(f"  {t}: {before[t]} -> {after[t]}")

    assert all(v == 0 for v in after.values()), "Some tables were not fully cleared!"
    print("\nAll application data tables confirmed empty. Schema/migrations/extensions untouched.")


if __name__ == "__main__":
    main()
