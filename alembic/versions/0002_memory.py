"""self-learning memory tables (lessons + episodes)

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Portable JSON column (JSONB on Postgres), matching workflows.persistence.orm.
JSONColumn = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "workflow_lessons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags_json", JSONColumn, nullable=False, server_default="[]"),
        sa.Column("reward", sa.Float(), nullable=False, server_default="0"),
        sa.Column("embedding_json", JSONColumn, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "workflow_episodes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_id", sa.String(64), nullable=False, index=True),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("iterations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_files_json", JSONColumn, nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding_json", JSONColumn, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("workflow_episodes")
    op.drop_table("workflow_lessons")
