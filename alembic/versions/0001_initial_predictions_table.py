"""Initial predictions table

Revision ID: 0001
Revises:
Create Date: 2026-04-13

Creates the predictions table — the single persistence target for the
fraud triage system in Phase 1.

Schema mirrors src/db/postgres_logger.py exactly.
Any future column additions must go through a new Alembic revision.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "predictions",

        # Primary key
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),

        # Transaction identity
        sa.Column("transaction_id", sa.String(64), nullable=True),

        # NUMERIC(12, 4) — exact decimal storage, no floating-point drift.
        sa.Column("amount", sa.Numeric(12, 4), nullable=True),

        # Stored as an ISO-8601 string, matching the existing application behaviour.
        sa.Column("timestamp", sa.String(32), nullable=True),

        # Scoring outputs
        sa.Column("rule_flag", sa.SmallInteger(), nullable=True),        # 0 or 1
        sa.Column("model_prediction", sa.SmallInteger(), nullable=True), # 0 or 1
        sa.Column("risk_score", sa.Numeric(6, 4), nullable=True),        # 0.0000 – 1.0000
        sa.Column("decision", sa.String(10), nullable=True),             # APPROVE / REVIEW / BLOCK

        # Pipe-delimited reason strings, e.g. "High transaction amount|Night transaction"
        sa.Column("reasons", sa.Text(), nullable=True),

        # Analyst review fields — always nullable, populated after manual review
        sa.Column("analyst_status", sa.String(20), nullable=True),       # CONFIRMED_FRAUD / FALSE_POSITIVE / APPROVED
        sa.Column("analyst_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.String(32), nullable=True),          # ISO-8601 string
    )

    # Indexes to support the most frequent query patterns:
    #   - GET /review-queue  filters on decision
    #   - GET /stats         counts by decision, rule_flag, model_prediction
    #   - GET /case/{id}     fetches by primary key (covered by PK index already)
    op.create_index("ix_predictions_decision", "predictions", ["decision"])
    op.create_index("ix_predictions_transaction_id", "predictions", ["transaction_id"])


def downgrade() -> None:
    op.drop_index("ix_predictions_transaction_id", table_name="predictions")
    op.drop_index("ix_predictions_decision", table_name="predictions")
    op.drop_table("predictions")
