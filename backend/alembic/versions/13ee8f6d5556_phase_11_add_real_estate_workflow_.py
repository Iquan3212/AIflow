"""phase 11 add real estate workflow trigger types

Revision ID: 13ee8f6d5556
Revises: b99f349d873c
Create Date: 2026-09-16 02:44:58.115995

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13ee8f6d5556'
down_revision: Union[str, Sequence[str], None] = 'b99f349d873c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_VALUES = (
    "lead_status_changed",
    "lead_qualified",
    "appointment_confirmed",
    "appointment_completed",
    "appointment_no_show",
    "booking_initiated",
    "booking_confirmed",
    "booking_cancelled",
    "booking_completed",
)


def upgrade() -> None:
    """Upgrade schema."""
    # ADD VALUE cannot run inside the same transaction that later uses the
    # new value, but running each ADD VALUE in its own committed statement
    # (no other DDL/DML touching workflow_trigger_type in this migration)
    # is safe on Postgres 12+ (confirmed: PostgreSQL 18 here). Each is
    # IF NOT EXISTS so a partial-then-retried run of this migration is
    # itself idempotent.
    for value in _NEW_VALUES:
        op.execute(f"ALTER TYPE workflow_trigger_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no DROP VALUE for an enum type - removing one requires
    # recreating the whole type (and every column using it) from scratch,
    # which is far riskier than leaving unused enum values in place.
    # Deliberately a no-op: no Workflow row can be created with these
    # values by application code from a build prior to this migration
    # (that validation lives in workflows/config.py, not the DB type), so
    # leaving them defined after a downgrade is harmless.
    pass
