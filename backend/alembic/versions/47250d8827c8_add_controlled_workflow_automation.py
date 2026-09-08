"""add controlled workflow automation

Revision ID: 47250d8827c8
Revises: e121ea483fc7
Create Date: 2026-09-08 20:16:49.696511

Hand-fixed after autogenerate for two reasons:

1. Autogenerate flagged `ix_knowledge_chunks_embedding_cosine` (the HNSW
   index from the Phase 4 migration, created via raw op.execute() since
   it's not expressible in plain SQLAlchemy column metadata) as "removed"
   - a false positive with no relation to this migration at all. That
   drop/recreate pair has been removed entirely from both upgrade() and
   downgrade() below; this migration never touches knowledge_chunks.
2. `workflow_step_runs.approval_request_id` and `approval_requests.
   workflow_step_run_id` are a genuine circular FK (each table references
   the other) - Postgres can't create either table first with both FKs
   inline. Fixed the standard way: create workflow_step_runs WITHOUT the
   approval_request_id FK constraint (the column exists, just unconstrained
   at first), create approval_requests (whose FK to workflow_step_runs is
   fine, since that table already exists), then add the deferred FK
   constraint from workflow_step_runs to approval_requests as a separate
   ALTER TABLE. downgrade() reverses this in the opposite order.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47250d8827c8'
down_revision: Union[str, Sequence[str], None] = 'e121ea483fc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('workflows',
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('business_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('active', 'paused', 'disabled', name='workflow_status'), nullable=False),
        sa.Column('trigger_type', sa.Enum(
            'lead_created', 'appointment_created', 'appointment_rescheduled',
            'appointment_cancelled', 'support_escalated', name='workflow_trigger_type',
        ), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=False),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workflows_business_id'), 'workflows', ['business_id'], unique=False)
    op.create_index(op.f('ix_workflows_trigger_type'), 'workflows', ['trigger_type'], unique=False)

    op.create_table('workflow_runs',
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('workflow_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('business_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('status', sa.Enum(
            'pending', 'running', 'waiting_approval', 'succeeded', 'failed', 'cancelled',
            name='workflow_run_status',
        ), nullable=False),
        sa.Column('trigger_event_id', sa.String(length=255), nullable=False),
        sa.Column('trigger_data', sa.JSON(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workflow_id', 'trigger_event_id', name='uq_workflow_run_idempotency'),
    )
    op.create_index(op.f('ix_workflow_runs_business_id'), 'workflow_runs', ['business_id'], unique=False)
    op.create_index(op.f('ix_workflow_runs_workflow_id'), 'workflow_runs', ['workflow_id'], unique=False)

    # approval_request_id has no FK constraint yet - approval_requests
    # doesn't exist until after this table does (circular FK - see the
    # module docstring above).
    op.create_table('workflow_step_runs',
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('workflow_run_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.Enum(
            'pending', 'running', 'waiting_approval', 'succeeded', 'failed', 'skipped',
            name='workflow_step_status',
        ), nullable=False),
        sa.Column('input', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('approval_request_id', sa.UUID(as_uuid=False), nullable=True),
        sa.Column('gmail_pending_action_id', sa.UUID(as_uuid=False), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['gmail_pending_action_id'], ['gmail_pending_actions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workflow_run_id'], ['workflow_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workflow_run_id', 'step_index', name='uq_workflow_step_run_index'),
    )
    op.create_index(op.f('ix_workflow_step_runs_workflow_run_id'), 'workflow_step_runs', ['workflow_run_id'], unique=False)

    op.create_table('approval_requests',
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('business_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('workflow_step_run_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'cancelled', name='approval_request_status'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('decided_by_user_id', sa.UUID(as_uuid=False), nullable=True),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['decided_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workflow_step_run_id'], ['workflow_step_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workflow_step_run_id'),
    )
    op.create_index(op.f('ix_approval_requests_business_id'), 'approval_requests', ['business_id'], unique=False)

    # The deferred half of the circular FK, now that both tables exist.
    op.create_foreign_key(
        'fk_workflow_step_runs_approval_request_id', 'workflow_step_runs', 'approval_requests',
        ['approval_request_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_workflow_step_runs_approval_request_id', 'workflow_step_runs', type_='foreignkey')
    op.drop_index(op.f('ix_approval_requests_business_id'), table_name='approval_requests')
    op.drop_table('approval_requests')
    op.drop_index(op.f('ix_workflow_step_runs_workflow_run_id'), table_name='workflow_step_runs')
    op.drop_table('workflow_step_runs')
    op.drop_index(op.f('ix_workflow_runs_workflow_id'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_business_id'), table_name='workflow_runs')
    op.drop_table('workflow_runs')
    op.drop_index(op.f('ix_workflows_trigger_type'), table_name='workflows')
    op.drop_index(op.f('ix_workflows_business_id'), table_name='workflows')
    op.drop_table('workflows')
    op.execute("DROP TYPE IF EXISTS approval_request_status")
    op.execute("DROP TYPE IF EXISTS workflow_step_status")
    op.execute("DROP TYPE IF EXISTS workflow_run_status")
    op.execute("DROP TYPE IF EXISTS workflow_trigger_type")
    op.execute("DROP TYPE IF EXISTS workflow_status")
