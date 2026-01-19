"""Add missing workflows metadata columns (project_id/source/source_id).

The initial workflows table migration (230439fc292d) omitted columns that the
current ORM model expects. This breaks basic reads (SELECT workflows.project_id...).

KISS: add the missing columns in a forward-only migration and keep constraints
best-effort for SQLite (batch_alter_table).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Inspector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a1c2b3d4e5f"
down_revision: str | None = "82b5e0195490"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector: Inspector, table_name: str, index_name: str) -> bool:
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table_name))


def _has_fk(inspector: Inspector, table_name: str, constraint_name: str) -> bool:
    return any(fk.get("name") == constraint_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    with op.batch_alter_table("workflows") as batch_op:
        if not _has_column(inspector, "workflows", "project_id"):
            batch_op.add_column(
                sa.Column(
                    "project_id",
                    sa.String(length=36),
                    nullable=True,
                    comment="关联的项目 ID（nullable；demo/test 环境可无项目）",
                )
            )

        if not _has_column(inspector, "workflows", "source"):
            # Non-null with a safe default so existing rows remain readable.
            batch_op.add_column(
                sa.Column(
                    "source",
                    sa.String(length=50),
                    nullable=False,
                    server_default="feagent",
                    comment="工作流来源（feagent/e2e_test/user等）",
                )
            )

        if not _has_column(inspector, "workflows", "source_id"):
            batch_op.add_column(
                sa.Column(
                    "source_id",
                    sa.String(length=255),
                    nullable=True,
                    comment="原始来源的ID（可选）",
                )
            )

    # Create indexes / FKs best-effort.
    inspector = sa.inspect(bind)

    if not _has_index(inspector, "workflows", "idx_workflows_project_id"):
        op.create_index("idx_workflows_project_id", "workflows", ["project_id"], unique=False)

    # If the projects table exists, add a FK to match the ORM contract.
    inspector = sa.inspect(bind)
    if "projects" in inspector.get_table_names() and not _has_fk(
        inspector, "workflows", "fk_workflows_project_id"
    ):
        with op.batch_alter_table("workflows") as batch_op:
            batch_op.create_foreign_key(
                "fk_workflows_project_id",
                "projects",
                ["project_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_fk(inspector, "workflows", "fk_workflows_project_id"):
        with op.batch_alter_table("workflows") as batch_op:
            batch_op.drop_constraint("fk_workflows_project_id", type_="foreignkey")

    if _has_index(inspector, "workflows", "idx_workflows_project_id"):
        op.drop_index("idx_workflows_project_id", table_name="workflows")

    inspector = sa.inspect(bind)
    with op.batch_alter_table("workflows") as batch_op:
        if _has_column(inspector, "workflows", "source_id"):
            batch_op.drop_column("source_id")
        if _has_column(inspector, "workflows", "source"):
            batch_op.drop_column("source")
        if _has_column(inspector, "workflows", "project_id"):
            batch_op.drop_column("project_id")
