"""Make workflow_events.case_id nullable

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-19

Alters workflow_events.case_id to allow NULL so that global workflow events
(e.g. daily fraud ops summaries) can be persisted without referencing a
specific predictions row. Case-specific events still pass a case_id; the
application layer validates it when provided.

Downgrade
---------
Restores NOT NULL on case_id. Any existing rows with case_id = NULL will
cause the downgrade to fail — clean those rows first if needed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "workflow_events",
        "case_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "workflow_events",
        "case_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
