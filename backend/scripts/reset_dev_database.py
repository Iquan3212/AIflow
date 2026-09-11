"""
Flushes ALL application data from the configured database, preserving
schema/migrations/extensions - for local development/demo use only.

Safety: this script refuses to run unless DATABASE_URL's hostname looks
like a Neon dev branch this project already uses, and it never touches
`alembic_version` or any schema object (no DROP TABLE, no DROP EXTENSION).
It only empties the 27 application data tables via TRUNCATE ... CASCADE,
which preserves table structure, columns, indexes, and constraints
exactly as-is - only rows are removed.

Run: ./venv/bin/python scripts/reset_dev_database.py --yes-i-am-sure
"""

import sys

from app.database import SessionLocal, engine
from app.config import get_settings
from sqlalchemy import text

DATA_TABLES = [
    "agencies", "ai_drafts", "appointments", "approval_requests",
    "business_hours", "buyer_sessions", "buyers", "calendar_credentials",
    "channel_credentials", "channel_webhook_events", "chatbot_configs",
    "conversations", "email_logs", "gmail_credentials",
    "gmail_pending_actions", "knowledge_chunks", "knowledge_documents",
    "leads", "messages", "notification_preferences",
    "scheduling_settings", "support_tickets", "user_sessions", "users",
    "workflow_runs", "workflow_step_runs", "workflows",
]


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
