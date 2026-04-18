"""Create investigations table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-18

Creates the investigations table — the persistence target for Phase 3
agentic investigation reports. Each row represents one completed (or failed)
investigation run against a predictions row.

Schema notes
------------
investigated_at
  Stored as TIMESTAMP WITH TIME ZONE. The investigation service writes an
  ISO-8601 string; Postgres parses it automatically.

rules_triggered, feature_breakdown, risk_factors, mitigating_factors,
playbooks_referenced, policies_referenced
  Stored as TEXT containing a JSON-encoded array or object. The application
  layer is responsible for serialising before write and deserialising after
  read. No JSON column type is used here to keep the schema portable.

merchant_seen_before
  Boolean — True/False/None (NULL when the tool has not yet run).

recommendation, confidence
  Constrained to known enum values by the application layer. No DB-level
  CHECK constraint is added here to allow values to be added without a
  migration.

Downgrade
---------
Drops the investigations table entirely, leaving the schema in its 0002 state.
No data recovery is possible after a downgrade.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigations",

        # Primary key
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),

        # Investigation identity
        sa.Column("investigation_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),

        # Pipeline metadata
        sa.Column("agent_version", sa.String(32), nullable=False),
        sa.Column("investigated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),   # IN_PROGRESS | COMPLETE | FAILED

        # Deterministic findings — populated by tool calls; nullable until tools run
        sa.Column("transaction_count_30d", sa.Integer(), nullable=True),
        sa.Column("amount_percentile", sa.Numeric(5, 2), nullable=True),
        sa.Column("merchant_seen_before", sa.Boolean(), nullable=True),
        sa.Column("rules_triggered", sa.Text(), nullable=True),       # JSON array
        sa.Column("feature_breakdown", sa.Text(), nullable=True),      # JSON object

        # LLM-produced fields — nullable until LLM reasoning runs
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("risk_factors", sa.Text(), nullable=True),           # JSON array
        sa.Column("mitigating_factors", sa.Text(), nullable=True),     # JSON array
        sa.Column("recommendation", sa.String(20), nullable=True),     # CONFIRM_FRAUD | FALSE_POSITIVE | ESCALATE
        sa.Column("recommendation_rationale", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(10), nullable=True),         # HIGH | MEDIUM | LOW
        sa.Column("confidence_rationale", sa.Text(), nullable=True),

        # Retrieval provenance
        sa.Column("playbooks_referenced", sa.Text(), nullable=True),   # JSON array
        sa.Column("policies_referenced", sa.Text(), nullable=True),    # JSON array

        # Error state — populated only when status=FAILED
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_unique_constraint(
        "uq_investigations_investigation_id",
        "investigations",
        ["investigation_id"],
    )

    # Index on case_id to support lookups by case (GET /cases/{id}/investigation).
    op.create_index(
        "ix_investigations_case_id",
        "investigations",
        ["case_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_investigations_case_id", table_name="investigations")
    op.drop_constraint("uq_investigations_investigation_id", "investigations", type_="unique")
    op.drop_table("investigations")
