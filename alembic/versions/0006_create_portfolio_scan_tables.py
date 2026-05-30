"""Create portfolio_scans and portfolio_scan_results tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-14

Creates two tables for the Portfolio Risk Scan feature (Phase 12):
  portfolio_scans        -- one row per uploaded batch scan job
  portfolio_scan_results -- one row per transaction row within a scan

Schema notes
------------
scan_id
  UUID string (VARCHAR 36) used as the external reference key in all
  /risk-scan/{scan_id} API paths. Unique-constrained and indexed.
  Referenced via FK from portfolio_scan_results.

total_rows
  Count of data rows in the uploaded CSV, excluding the header row.
  A file with a header and 120 data rows has total_rows = 120.

risk_summary
  Stored as TEXT containing a JSON-encoded object: top risk patterns,
  country distribution, payment method distribution, merchant category
  distribution. Same JSON-as-TEXT pattern used in the investigations table.

validation_status
  VALID   -- row passed validation and was scored
  INVALID -- row failed validation (missing required field or bad type)
  SKIPPED -- row has a duplicate transaction_id within the same upload

validation_errors
  JSON-encoded array of error strings. NULL for VALID rows.
  SKIPPED rows contain: ["Duplicate transaction_id in uploaded file"]

promoted
  False until an analyst explicitly promotes the result via
  POST /risk-scan/{scan_id}/promote/{result_id}. Only VALID rows
  are promotable.

Foreign key
  portfolio_scan_results.scan_id references portfolio_scans.scan_id.
  ON DELETE CASCADE removes all result rows if the parent scan is deleted.

Downgrade
---------
Drops all indexes, the FK constraint, portfolio_scan_results (child), then
portfolio_scans (parent). No data recovery is possible after a downgrade.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Table 1: portfolio_scans
    # One row per uploaded CSV batch. Stores portfolio-level metadata and
    # summary aggregates. Created before portfolio_scan_results so the FK
    # reference can be established in the same migration.
    # -------------------------------------------------------------------------
    op.create_table(
        "portfolio_scans",

        # Primary key
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),

        # External reference key — used in all /risk-scan/{scan_id} API paths.
        # Unique constraint added separately below so it appears in pg_constraint.
        sa.Column("scan_id", sa.String(36), nullable=False),

        # Upload metadata
        sa.Column("filename", sa.String(255), nullable=True),

        # Processing state: PENDING / PROCESSING / COMPLETE / FAILED.
        # PENDING and PROCESSING are reserved for future async upgrade.
        # Sync MVP always writes COMPLETE or FAILED.
        sa.Column("status", sa.String(20), nullable=False, server_default="COMPLETE"),

        # Row counts — total_rows excludes the CSV header row
        sa.Column("total_rows",   sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("valid_rows",   sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),

        # Risk tier counts (Low / Medium / High / Critical)
        sa.Column("low_count",      sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("medium_count",   sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("high_count",     sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("critical_count", sa.Integer(), nullable=False, server_default=sa.text("0")),

        # Operational priority counts (P0/P1/P2/P3 — maps 1:1 with tier counts above)
        sa.Column("p0_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("p1_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("p2_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("p3_count", sa.Integer(), nullable=False, server_default=sa.text("0")),

        # Exposure totals — computed from VALID rows only
        sa.Column("total_amount",    sa.Numeric(16, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("critical_amount", sa.Numeric(16, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("high_amount",     sa.Numeric(16, 4), nullable=False, server_default=sa.text("0")),

        # JSON-encoded summary: top risk patterns, country/payment/category distributions
        sa.Column("risk_summary", sa.Text(), nullable=True),

        # Audit timestamps
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),

        # Populated only when status = FAILED
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_unique_constraint(
        "uq_portfolio_scans_scan_id",
        "portfolio_scans",
        ["scan_id"],
    )

    # Index on scan_id — primary lookup key for all /risk-scan/{scan_id} endpoints
    op.create_index(
        "ix_portfolio_scans_scan_id",
        "portfolio_scans",
        ["scan_id"],
    )

    # Index on created_at — supports newest-first ordering of scan history
    op.create_index(
        "ix_portfolio_scans_created_at",
        "portfolio_scans",
        ["created_at"],
    )

    # -------------------------------------------------------------------------
    # Table 2: portfolio_scan_results
    # One row per transaction row within a scan, including INVALID and SKIPPED
    # rows for complete audit coverage.
    # -------------------------------------------------------------------------
    op.create_table(
        "portfolio_scan_results",

        # Primary key — used as result_id in POST /risk-scan/{scan_id}/promote/{result_id}
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),

        # Parent scan reference — FK to portfolio_scans.scan_id added below
        sa.Column("scan_id", sa.String(36), nullable=False),

        # 1-based data row index from the original CSV (excluding the header row)
        sa.Column("row_number", sa.Integer(), nullable=False),

        # Raw transaction fields — as submitted in the CSV
        sa.Column("transaction_id",    sa.String(64),     nullable=True),
        sa.Column("amount",            sa.Numeric(12, 4), nullable=True),
        sa.Column("timestamp",         sa.String(32),     nullable=True),
        sa.Column("country",           sa.String(2),      nullable=True),
        sa.Column("payment_method",    sa.String(64),     nullable=True),
        sa.Column("merchant_category", sa.String(64),     nullable=True),
        sa.Column("device_id",         sa.String(128),    nullable=True),

        # Scoring outputs — NULL for INVALID and SKIPPED rows
        sa.Column("rule_flag",            sa.SmallInteger(), nullable=True),  # 0 or 1
        sa.Column("model_prediction",     sa.SmallInteger(), nullable=True),  # 0 or 1
        sa.Column("risk_score",           sa.Numeric(6, 4),  nullable=True),  # 0.0000 – 1.0000
        sa.Column("decision",             sa.String(10),     nullable=True),  # APPROVE / REVIEW / BLOCK
        sa.Column("risk_tier",            sa.String(10),     nullable=True),  # Low / Medium / High / Critical
        sa.Column("operational_priority", sa.String(4),      nullable=True),  # P0 / P1 / P2 / P3
        sa.Column("reasons",              sa.Text(),         nullable=True),  # Pipe-delimited

        # Validation outcome
        sa.Column("validation_status", sa.String(10), nullable=False),  # VALID / INVALID / SKIPPED
        sa.Column("validation_errors", sa.Text(),     nullable=True),   # JSON array; NULL if VALID

        # Promotion tracking
        sa.Column("promoted",         sa.Boolean(),              nullable=False, server_default=sa.text("false")),
        sa.Column("promoted_case_id", sa.Integer(),              nullable=True),
        sa.Column("promoted_at",      sa.TIMESTAMP(timezone=True), nullable=True),

        # Audit timestamp
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # FK: portfolio_scan_results.scan_id -> portfolio_scans.scan_id (ON DELETE CASCADE)
    op.create_foreign_key(
        "fk_scan_results_scan_id",
        "portfolio_scan_results",
        "portfolio_scans",
        ["scan_id"],
        ["scan_id"],
        ondelete="CASCADE",
    )

    # Index on scan_id — primary access pattern: all results for a given scan
    op.create_index(
        "ix_portfolio_scan_results_scan_id",
        "portfolio_scan_results",
        ["scan_id"],
    )

    # Index on transaction_id — supports deduplication lookups across scans
    op.create_index(
        "ix_portfolio_scan_results_transaction_id",
        "portfolio_scan_results",
        ["transaction_id"],
    )

    # Index on operational_priority — supports tier-filtered result views (P0, P1, P2, P3)
    op.create_index(
        "ix_portfolio_scan_results_priority",
        "portfolio_scan_results",
        ["operational_priority"],
    )

    # Index on decision — supports APPROVE / REVIEW / BLOCK filter
    op.create_index(
        "ix_portfolio_scan_results_decision",
        "portfolio_scan_results",
        ["decision"],
    )

    # Index on validation_status — supports VALID / INVALID / SKIPPED filter
    op.create_index(
        "ix_portfolio_scan_results_validation_status",
        "portfolio_scan_results",
        ["validation_status"],
    )

    # Index on promoted — supports unreviewed promotion queue filter
    op.create_index(
        "ix_portfolio_scan_results_promoted",
        "portfolio_scan_results",
        ["promoted"],
    )


def downgrade() -> None:
    # Drop portfolio_scan_results indexes (reverse creation order)
    op.drop_index("ix_portfolio_scan_results_promoted",          table_name="portfolio_scan_results")
    op.drop_index("ix_portfolio_scan_results_validation_status", table_name="portfolio_scan_results")
    op.drop_index("ix_portfolio_scan_results_decision",          table_name="portfolio_scan_results")
    op.drop_index("ix_portfolio_scan_results_priority",          table_name="portfolio_scan_results")
    op.drop_index("ix_portfolio_scan_results_transaction_id",    table_name="portfolio_scan_results")
    op.drop_index("ix_portfolio_scan_results_scan_id",           table_name="portfolio_scan_results")

    # Drop FK before dropping the child table
    op.drop_constraint("fk_scan_results_scan_id", "portfolio_scan_results", type_="foreignkey")

    # Drop child table first (FK dependency requires this order)
    op.drop_table("portfolio_scan_results")

    # Drop portfolio_scans indexes then unique constraint then parent table
    op.drop_index("ix_portfolio_scans_created_at", table_name="portfolio_scans")
    op.drop_index("ix_portfolio_scans_scan_id",    table_name="portfolio_scans")
    op.drop_constraint("uq_portfolio_scans_scan_id", "portfolio_scans", type_="unique")
    op.drop_table("portfolio_scans")
