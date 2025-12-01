"""Add missing workflows.user_id column

Revision ID: 82b5e0195490
Revises: 2f00b84163ac
Create Date: 2025-11-30 21:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Inspector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "82b5e0195490"
down_revision: str | None = "2f00b84163ac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_fk(inspector: Inspector, table_name: str, constraint_name: str) -> bool:
    return any(fk["name"] == constraint_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "workflows", "user_id"):
        with op.batch_alter_table("workflows") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "user_id",
                    sa.String(length=36),
                    nullable=True,
                    comment="Creator ID (nullable to support unauthenticated users)",
                )
            )
            if "users" in inspector.get_table_names() and not _has_fk(
                inspector, "workflows", "fk_workflows_user_id"
            ):
                batch_op.create_foreign_key(
                    "fk_workflows_user_id",
                    "users",
                    ["user_id"],
                    ["id"],
                    ondelete="SET NULL",
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_fk(inspector, "workflows", "fk_workflows_user_id"):
        with op.batch_alter_table("workflows") as batch_op:
            batch_op.drop_constraint("fk_workflows_user_id", type_="foreignkey")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "workflows", "user_id"):
        with op.batch_alter_table("workflows") as batch_op:
            batch_op.drop_column("user_id")
