"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("type", sa.String(100), nullable=False, server_default="generic"),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(50), nullable=False, server_default="normal"),
        sa.Column("current_node", sa.String(100), nullable=True),
        sa.Column("state_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("budget_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("budget_used_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_id", sa.Uuid(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("node", sa.String(100), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False, server_default="generic"),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("input_json", JSONB(), nullable=True),
        sa.Column("output_json", JSONB(), nullable=True),
        sa.Column("error_json", JSONB(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_steps_workflow_id", "workflow_steps", ["workflow_id"])

    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_id", sa.Uuid(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_id", sa.Uuid(), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("idempotency_key", sa.String(500), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(128), nullable=True),
        sa.Column("request_json", JSONB(), nullable=True),
        sa.Column("response_json", JSONB(), nullable=True),
        sa.Column("error_json", JSONB(), nullable=True),
        sa.Column("risk_level", sa.String(50), nullable=False, server_default="low"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tool_calls_workflow_id", "tool_calls", ["workflow_id"])

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_id", sa.Uuid(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_type", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=True),
        sa.Column("payload_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_events_workflow_id", "workflow_events", ["workflow_id"])

    op.create_table(
        "workflow_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_id", sa.Uuid(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("artifact_type", sa.String(100), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_artifacts_workflow_id", "workflow_artifacts", ["workflow_id"])

    op.create_table(
        "human_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_id", sa.Uuid(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_id", sa.Uuid(), nullable=True),
        sa.Column("approval_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("requested_by", sa.String(100), nullable=True),
        sa.Column("decided_by", sa.String(100), nullable=True),
        sa.Column("payload_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("decision_json", JSONB(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_human_approvals_workflow_id", "human_approvals", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_human_approvals_workflow_id", table_name="human_approvals")
    op.drop_table("human_approvals")
    op.drop_index("ix_workflow_artifacts_workflow_id", table_name="workflow_artifacts")
    op.drop_table("workflow_artifacts")
    op.drop_index("ix_workflow_events_workflow_id", table_name="workflow_events")
    op.drop_table("workflow_events")
    op.drop_index("ix_tool_calls_workflow_id", table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_index("ix_workflow_steps_workflow_id", table_name="workflow_steps")
    op.drop_table("workflow_steps")
    op.drop_table("workflows")
