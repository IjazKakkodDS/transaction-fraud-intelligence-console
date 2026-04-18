"""Create workflow_events table

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-18

Creates the workflow_events table — the audit trail for n8n automation
actions performed against fraud cases. Each row represents one workflow
callback received by POST /workflow/audit-event.

Schema notes
------------
payload
  Stored as TEXT containing a JSON-encoded object. The application layer
  serialises before write and deserialises after read.

created_at
  Stored as TIMESTAMP WITH TIME ZONE, set by the database default so the
  server clock is authoritative.

Downgrade
---------
Drops the workflow_events table entirely. No data recovery is possible
after a downgrade.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_events",

        # Primary key
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),

        # Case reference — every event is tied to a predictions row
        sa.Column("case_id", sa.Integer(), nullable=False),

        # Workflow identity
        sa.Column("workflow_name", sa.String(128), nullable=False),
        sa.Column("workflow_action", sa.String(64), nullable=False),

        # Outcome
        sa.Column("status", sa.String(20), nullable=False, server_default="SUCCESS"),
        sa.Column("escalation_priority", sa.String(20), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),

        # Full n8n output — JSON-encoded object
        sa.Column("payload", sa.Text(), nullable=True),

        # Originating system
        sa.Column("source", sa.String(32), nullable=False, server_default="n8n"),

        # Audit timestamp
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Index on case_id — the primary access pattern is filtering by case.
    op.create_index(
        "ix_workflow_events_case_id",
        "workflow_events",
        ["case_id"],
    )

    # Index on created_at — supports latest-first ordering efficiently.
    op.create_index(
        "ix_workflow_events_created_at",
        "workflow_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_events_created_at", table_name="workflow_events")
    op.drop_index("ix_workflow_events_case_id", table_name="workflow_events")
    op.drop_table("workflow_events")
