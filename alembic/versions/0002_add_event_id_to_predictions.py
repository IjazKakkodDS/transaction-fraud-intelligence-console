"""Add event_id column with UNIQUE constraint to predictions table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-18

Adds an idempotency key to the predictions table. The scoring consumer stores
the event_id of the originating TransactionRawEvent (stable across Kafka
re-deliveries) so that duplicate message processing is caught at the DB layer
rather than relying solely on at-most-once delivery guarantees.

NULL semantics and backfill behavior
-------------------------------------
The column is nullable. Two categories of rows will always have event_id = NULL:

  1. Pre-existing rows written before this migration runs — no backfill is
     performed; they remain NULL permanently and are unaffected by the constraint.
  2. Future rows written by the synchronous POST /predict path — that path has
     no originating Kafka event and passes event_id=None to log_prediction().

In SQL, NULL is not equal to NULL, so multiple NULL values never violate a
UNIQUE constraint. The constraint exclusively protects the async consumer
path, where every insert carries a non-NULL event_id from the Kafka message.

Downgrade
---------
Drops the unique index then removes the column, leaving the table in its
0001 state.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("event_id", sa.String(64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_predictions_event_id",
        "predictions",
        ["event_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_predictions_event_id", "predictions", type_="unique")
    op.drop_column("predictions", "event_id")
