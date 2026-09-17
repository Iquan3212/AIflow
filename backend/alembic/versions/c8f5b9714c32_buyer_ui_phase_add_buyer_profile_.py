"""buyer ui phase add buyer profile preferences and notification prefs

Revision ID: c8f5b9714c32
Revises: 13ee8f6d5556
Create Date: 2026-09-18 00:20:20.279795

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f5b9714c32'
down_revision: Union[str, Sequence[str], None] = '13ee8f6d5556'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("buyers", sa.Column("preferred_city", sa.String(length=255), nullable=True))
    op.add_column("buyers", sa.Column("preferred_locality", sa.String(length=255), nullable=True))
    op.add_column("buyers", sa.Column("preferred_bhk", sa.Integer(), nullable=True))
    op.add_column("buyers", sa.Column("budget_min", sa.Numeric(14, 2), nullable=True))
    op.add_column("buyers", sa.Column("budget_max", sa.Numeric(14, 2), nullable=True))
    op.add_column("buyers", sa.Column("preferred_property_type", sa.String(length=32), nullable=True))
    op.add_column("buyers", sa.Column("preferred_furnishing", sa.String(length=32), nullable=True))
    op.add_column(
        "buyers",
        sa.Column("notify_site_visit_updates", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "buyers",
        sa.Column("notify_inquiry_updates", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "buyers",
        sa.Column("notify_booking_updates", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "buyers",
        sa.Column("notify_property_alerts", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("buyers", "notify_property_alerts")
    op.drop_column("buyers", "notify_booking_updates")
    op.drop_column("buyers", "notify_inquiry_updates")
    op.drop_column("buyers", "notify_site_visit_updates")
    op.drop_column("buyers", "preferred_furnishing")
    op.drop_column("buyers", "preferred_property_type")
    op.drop_column("buyers", "budget_max")
    op.drop_column("buyers", "budget_min")
    op.drop_column("buyers", "preferred_bhk")
    op.drop_column("buyers", "preferred_locality")
    op.drop_column("buyers", "preferred_city")
