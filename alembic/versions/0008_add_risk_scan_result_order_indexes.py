"""Add NULLS LAST indexes for risk scan result ordering

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-01
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_scan_results_scan_score_row_nullslast
            ON portfolio_scan_results (scan_id, risk_score DESC NULLS LAST, row_number ASC)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_scan_results_scan_priority_score_row_nullslast
            ON portfolio_scan_results (
                scan_id,
                operational_priority,
                risk_score DESC NULLS LAST,
                row_number ASC
            )
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_scan_results_scan_priority_score_row_nullslast"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_scan_results_scan_score_row_nullslast"
        )
