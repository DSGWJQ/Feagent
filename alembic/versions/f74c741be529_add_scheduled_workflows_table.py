"""add scheduled workflows table

Revision ID: f74c741be529
Revises: f8c9d4a1b2e3
Create Date: 2025-11-25 16:24:58.173043

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f74c741be529"
down_revision: str | None = "f8c9d4a1b2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduled_workflows",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("cron_expression", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_execution_at", sa.DateTime(), nullable=True),
        sa.Column("last_execution_status", sa.String(length=20), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_scheduled_workflows_workflow_id",
        "scheduled_workflows",
        ["workflow_id"],
    )
    op.create_index(
        "idx_scheduled_workflows_status",
        "scheduled_workflows",
        ["status"],
    )
    op.create_index(
        "idx_scheduled_workflows_created_at",
        "scheduled_workflows",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_scheduled_workflows_created_at", table_name="scheduled_workflows")
    op.drop_index("idx_scheduled_workflows_status", table_name="scheduled_workflows")
    op.drop_index("idx_scheduled_workflows_workflow_id", table_name="scheduled_workflows")
    op.drop_table("scheduled_workflows")
