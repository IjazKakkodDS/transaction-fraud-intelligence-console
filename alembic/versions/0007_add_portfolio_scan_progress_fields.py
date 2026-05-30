"""Add portfolio scan progress fields

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "portfolio_scans",
        sa.Column(
            "processed_rows",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "portfolio_scans",
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "portfolio_scans",
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "portfolio_scans",
        sa.Column("chunk_size", sa.Integer(), nullable=True),
    )

    op.create_index(
        "ix_scan_results_scan_score_row",
        "portfolio_scan_results",
        ["scan_id", sa.text("risk_score DESC"), "row_number"],
    )
    op.create_index(
        "ix_scan_results_scan_priority_score",
        "portfolio_scan_results",
        ["scan_id", "operational_priority", sa.text("risk_score DESC")],
    )
    op.create_index(
        "ix_scan_results_scan_validation_row",
        "portfolio_scan_results",
        ["scan_id", "validation_status", "row_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_scan_results_scan_validation_row", table_name="portfolio_scan_results")
    op.drop_index("ix_scan_results_scan_priority_score", table_name="portfolio_scan_results")
    op.drop_index("ix_scan_results_scan_score_row", table_name="portfolio_scan_results")
    op.drop_column("portfolio_scans", "chunk_size")
    op.drop_column("portfolio_scans", "cancelled_at")
    op.drop_column("portfolio_scans", "started_at")
    op.drop_column("portfolio_scans", "processed_rows")
